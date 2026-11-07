import asyncio
from uuid import uuid4
import pytest
from sqlalchemy import select, delete
from app.db.session import create_database
from app.models.knowledge import KnowledgeDocument, KnowledgeVersion, KnowledgeChunk
from app.services.knowledge import publish, retrieve, deactivate
from app.services.rag_provider import ModelProvider
from app.config import Settings
from app.errors import AppError
from tests.test_database import database_url
from tests.test_security import client
from tests.test_ticket_workflow import identities, create


class FakeEmbedding:
    space = 'test-space'
    calls = 0
    async def embed(self, text):
        self.calls += 1
        return [1., 0.]


def test_version_lifecycle_and_failure(database_url):
    async def run():
        engine, factory = create_database(database_url)
        doc = {'id':'test-'+uuid4().hex,'version':1,'title':'测试','digest':'a'*64,'chunks':['登录说明']}
        provider = FakeEmbedding()
        try:
            async with factory() as session:
                assert await publish(session, provider, doc) == 'published'
                assert await publish(session, provider, doc) == 'unchanged'
                assert provider.calls == 1
                with pytest.raises(ValueError):
                    await publish(session, provider, doc | {'digest':'b'*64})
                sources = await retrieve(session, provider, '登录', Settings(_env_file=None))
                assert any(s['document_id'] == doc['id'] for s in sources)
                async def fail(text):
                    raise RuntimeError('model unavailable')
                provider.embed = fail
                with pytest.raises(RuntimeError):
                    await publish(session, provider, doc | {'version':2})
                async with session.begin():
                    assert (await session.get(KnowledgeDocument, doc['id'], populate_existing=True)).active_version == 1
                provider = FakeEmbedding()
                async def import_one():
                    async with factory() as separate:
                        return await publish(separate, provider, doc | {'version':2})
                assert sorted(await asyncio.gather(import_one(), import_one())) == ['published','unchanged']
                with pytest.raises(ValueError):
                    await publish(session, provider, doc | {'version':1,'digest':'b'*64})
                await deactivate(session, doc['id'])
                assert not any(s['document_id'] == doc['id'] for s in await retrieve(session, provider, '登录', Settings(_env_file=None)))
        finally:
            async with factory() as session, session.begin():
                for model in (KnowledgeChunk, KnowledgeVersion):
                    await session.execute(delete(model).where(model.document_id == doc['id']))
                await session.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id == doc['id']))
            await engine.dispose()
    asyncio.run(run())


def test_suggestion_authorization_privacy_and_recheck(client, database_url, monkeypatch):
    from app.routers import rag
    (_, owner), (_, outsider), (_, agent), (_, other_agent), (_, admin) = identities(client, database_url)
    path = create(client, owner)
    assert client.post(path+'/claim', headers=agent).status_code == 200
    assert client.post(path+'/notes', headers=agent, json={'content':'PRIVATE_INTERNAL_NOTE'}).status_code == 201
    for headers in (owner, outsider, other_agent, admin):
        assert client.post(path+'/reply-suggestion', headers=headers).status_code == 403
    assert client.post(path+'/reply-suggestion').status_code == 401
    assert client.post(path+'/reply-suggestion', headers=agent).status_code == 503
    monkeypatch.setattr(ModelProvider, 'configured', lambda *args: None)
    async def no_sources(*args):
        assert 'PRIVATE_INTERNAL_NOTE' not in args[2]
        return []
    monkeypatch.setattr(rag, 'retrieve', no_sources)
    response = client.post(path+'/reply-suggestion', headers=agent)
    assert response.status_code == 200, response.text
    assert response.json()['data']['status'] == 'insufficient_evidence'
    assert client.get(path+'/comments', headers=owner).json()['data'] == []
    original = rag.context_snapshot
    calls = 0
    async def changed(*args):
        nonlocal calls
        content, signature = await original(*args)
        calls += 1
        return content, signature + ('changed' if calls == 2 else '')
    monkeypatch.setattr(rag, 'context_snapshot', changed)
    assert client.post(path+'/reply-suggestion', headers=agent).status_code == 409


@pytest.mark.parametrize('mutation', ['none', 'transfer', 'public_reply', 'deactivate'])
def test_generated_result_revalidates_real_database(client, database_url, monkeypatch, mutation):
    from app.models import Ticket, Comment
    (_, owner), (_, _), (agent_id, agent), (next_id, _), (_, _) = identities(client, database_url)
    path = create(client, owner)
    ticket_id = int(path.rsplit('/', 1)[1])
    assert client.post(path+'/claim', headers=agent).status_code == 200
    doc_id = 'test-'+uuid4().hex
    provider = FakeEmbedding()
    async def setup():
        engine, factory = create_database(database_url)
        try:
            async with factory() as session:
                await publish(session, provider, {'id':doc_id,'version':1,'title':'真实数据库来源','digest':'c'*64,'chunks':['登录使用注册邮箱和密码。']})
        finally:
            await engine.dispose()
    asyncio.run(setup())
    monkeypatch.setattr(ModelProvider, 'configured', lambda *args: None)
    monkeypatch.setattr(ModelProvider, 'space', property(lambda self: provider.space))
    async def embed(self, text):
        return [1., 0.]
    monkeypatch.setattr(ModelProvider, 'embed', embed)
    async def post(self, kind, endpoint, payload):
        import json
        sources = json.loads(payload['messages'][1]['content'])['sources']
        if mutation != 'none':
            engine, factory = create_database(database_url)
            try:
                async with factory() as session, session.begin():
                    if mutation == 'transfer':
                        (await session.get(Ticket, ticket_id)).assignee_id = next_id
                    elif mutation == 'public_reply':
                        session.add(Comment(ticket_id=ticket_id, author_id=agent_id, content='新增回复', visibility='public'))
                    else:
                        (await session.get(KnowledgeDocument, doc_id)).active_version = None
            finally:
                await engine.dispose()
        return {'choices':[{'message':{'content':json.dumps({'status':'ok','draft':'请核对邮箱。','citations':[sources[0]['chunk_id']]})}}]}
    monkeypatch.setattr(ModelProvider, 'post', post)
    try:
        response = client.post(path+'/reply-suggestion', headers=agent)
        assert response.status_code == {'none':200,'transfer':403,'public_reply':409,'deactivate':409}[mutation], response.text
        if mutation == 'none':
            assert response.json()['data']['sources'][0]['document_id'] == doc_id
            assert client.get(path+'/comments', headers=owner).json()['data'] == []
    finally:
        async def cleanup():
            engine, factory = create_database(database_url)
            try:
                async with factory() as session, session.begin():
                    await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id))
                    await session.execute(delete(KnowledgeVersion).where(KnowledgeVersion.document_id == doc_id))
                    await session.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
            finally:
                await engine.dispose()
        asyncio.run(cleanup())
