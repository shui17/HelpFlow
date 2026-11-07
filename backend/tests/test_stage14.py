import asyncio
import json
from pathlib import Path
import pytest
from app.config import Settings
from app.errors import AppError
from app.services.knowledge import parse_document
from app.services.rag_provider import ModelProvider, vector


@pytest.mark.parametrize("value", [[], [0, 0], [float('nan')], [float('inf')], [True], ['1'], None])
def test_reject_invalid_vector(value):
    with pytest.raises(ValueError):
        vector(value)


def test_normalized_vector():
    assert vector([3, 4]) == [0.6, 0.8]


def test_faq_metadata_and_determinism():
    files = list((Path(__file__).parents[2] / 'knowledge').glob('*.md'))
    assert len(files) >= 5
    for path in files:
        doc = parse_document(path)
        assert doc == parse_document(path)
        assert all(0 < len(c) <= 800 for c in doc['chunks'])


def test_unapproved_document_rejected(tmp_path):
    path = tmp_path / 'private.md'
    path.write_text('---\nid: private\ntitle: 私有\nversion: 1\nstatus: approved\naudience: internal\n---\n私有内容', encoding='utf-8')
    with pytest.raises(ValueError, match='公开'):
        parse_document(path)


def test_missing_credentials():
    provider = ModelProvider(Settings(_env_file=None))
    with pytest.raises(AppError) as caught:
        provider.configured('generation')
    assert caught.value.status == 503


@pytest.mark.parametrize('payload', [
    {'status':'ok','draft':'答案','citations':['invented']},
    {'status':'ok','draft':'答案','citations':[]},
    {'status':'ok','draft':'a'*2001,'citations':['valid']},
    {'status':'ok','draft':'','citations':['valid']},
    None,
])
def test_invalid_citation_or_draft_rejected(payload):
    provider = ModelProvider(Settings(_env_file=None))
    async def fake(*args):
        return {'choices':[{'message':{'content':json.dumps(payload)}}]}
    provider.post = fake
    with pytest.raises(AppError):
        asyncio.run(provider.generate({}, [{'chunk_id':'valid'}]))


def test_sources_come_from_retrieval():
    provider = ModelProvider(Settings(_env_file=None))
    async def fake(*args):
        return {'choices':[{'message':{'content':json.dumps({'status':'ok','draft':'请核对邮箱。','citations':['valid','valid']})}}]}
    provider.post = fake
    source = {'chunk_id':'valid','title':'真实来源'}
    result = asyncio.run(provider.generate({}, [source]))
    assert result['sources'] == [source]


def test_insufficient_evidence_has_no_draft():
    provider = ModelProvider(Settings(_env_file=None))
    async def fake(*args):
        return {'choices':[{'message':{'content':'{"status":"insufficient_evidence","draft":"不可采用"}'}}]}
    provider.post = fake
    result = asyncio.run(provider.generate({}, []))
    assert result == {'status':'insufficient_evidence','draft':'','sources':[]}


@pytest.mark.parametrize('failure', ['timeout', 'upstream_error', 'bad_json'])
def test_provider_failure_sanitized_without_retry(monkeypatch, failure):
    import httpx
    from app.services import rag_provider
    original_client = httpx.AsyncClient
    calls = []
    async def handler(request):
        calls.append(request)
        if failure == 'timeout':
            raise httpx.ReadTimeout('sensitive-upstream-text')
        return httpx.Response(503 if failure == 'upstream_error' else 200, content=b'sensitive-upstream-text')
    monkeypatch.setattr(rag_provider.httpx, 'AsyncClient', lambda **kw: original_client(transport=httpx.MockTransport(handler), **kw))
    provider = ModelProvider(Settings(_env_file=None, rag_generation_key='test-only-key'))
    with pytest.raises(AppError) as error:
        asyncio.run(provider.post('generation', '/chat/completions', {}))
    assert len(calls) == 1
    assert error.value.status == 502
    assert 'sensitive' not in str(error.value)


@pytest.mark.parametrize('kind,label', [('generation','回复生成服务'), ('embedding','知识检索服务')])
def test_insufficient_balance_has_actionable_message(monkeypatch, kind, label):
    import httpx
    from app.services import rag_provider
    original_client = httpx.AsyncClient
    async def handler(request):
        return httpx.Response(402, json={'error': {'message': 'Insufficient Balance sensitive-upstream-text'}})
    monkeypatch.setattr(rag_provider.httpx, 'AsyncClient', lambda **kw: original_client(transport=httpx.MockTransport(handler), **kw))
    provider = ModelProvider(Settings(_env_file=None, rag_generation_key='test-only-key',
        rag_embedding_key='test-only-key', rag_embedding_url='https://example.com', rag_embedding_model='test'))
    with pytest.raises(AppError) as error:
        asyncio.run(provider.post(kind, '/test', {}))
    assert error.value.status == 503
    assert error.value.code == 50021
    assert label in error.value.message and '余额或额度不足' in error.value.message
    assert 'sensitive' not in error.value.message
