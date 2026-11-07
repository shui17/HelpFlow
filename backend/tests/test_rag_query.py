from app.services.knowledge import retrieval_text


def test_duplicate_title_description_matches_question_evaluation():
    assert retrieval_text({'title':'  无法登录  ', 'description':'无法登录', 'comments':[]}) == '无法登录'


def test_query_contains_public_text_not_serialized_ids():
    context = {'title':'登录失败', 'description':'账号禁用',
               'comments':[{'id':987654321,'content':'账号禁用'}, {'id':987654322,'content':'今天开始出现'}]}
    assert retrieval_text(context) == '登录失败\n账号禁用\n今天开始出现'


def test_query_budget_keeps_latest_reply_with_long_description():
    query = retrieval_text({'title':'故障', 'description':'旧描述'*2000,
                            'comments':[{'content':'旧补充'*1000}, {'content':'最新问题'}]})
    assert len(query) <= 2000
    assert '最新问题' in query


def test_empty_context():
    assert retrieval_text({'title':' ', 'description':'', 'comments':[]}) == ''


def test_threshold_preserves_boundary_and_reports_false_positive():
    from scripts.evaluate_rag import evaluate_case
    sources = [{'document_id':'login-failed','version':1,'chunk_id':'a','score':0.55}]
    assert evaluate_case({'expected':'login-failed'}, sources, 0.55, 4)['retrieval_pass']
    assert not evaluate_case({'expected':None}, sources, 0.55, 4)['retrieval_pass']
    assert evaluate_case({'expected':None}, sources, 0.56, 4)['retrieval_pass']


def test_evaluation_keeps_errors_separate_and_uses_shared_query(tmp_path, monkeypatch):
    import asyncio
    import json
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    import pytest
    from scripts import evaluate_rag
    from app.config import Settings
    from app.errors import AppError
    cases, output = tmp_path/'cases.json', tmp_path/'report.json'
    cases.write_text(json.dumps([{'question':'失败请求','expected':None}, {'question':'无答案','expected':None}]), encoding='utf-8')
    queries = []
    @asynccontextmanager
    async def factory():
        yield object()
    async def dispose():
        pass
    async def retrieve(session, provider, text, settings):
        queries.append(text)
        if len(queries) == 1:
            raise AppError(502, 50015, '服务不可用')
        return []
    monkeypatch.setattr(evaluate_rag, 'Settings', lambda: Settings(_env_file=None))
    monkeypatch.setattr(evaluate_rag, 'create_database', lambda url: (SimpleNamespace(dispose=dispose), factory))
    monkeypatch.setattr(evaluate_rag, 'retrieve', retrieve)
    with pytest.raises(SystemExit) as error:
        asyncio.run(evaluate_rag.main(SimpleNamespace(threshold=0.55, cases=[str(cases)], output=str(output))))
    assert error.value.code == 1
    report = json.loads(output.read_text(encoding='utf-8'))
    assert report['summary']['passed'] == 1
    assert report['summary']['errors'] == 1
    assert report['results'][0]['retrieval_pass'] is None
    assert queries == ['失败请求', '无答案']
