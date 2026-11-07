"""阶段十五：真实MySQL事务与SQLite检查点，模型替身只负责工具选择。"""
import asyncio
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.db.base import utcnow
from app.db.session import create_database
from app.models import AgentTask, AgentExecution, Comment, Notification, TicketSLA
from app.errors import AppError
from app.services.agent_tasks import AgentTasks
from app.services.rag_provider import ModelProvider
from app.services.knowledge import publish, deactivate
from tests.test_database import database_url
from tests.test_security import client, db_run, set_fields
from tests.test_ticket_workflow import identities, create


def tool(name, args=None):
    return {'id': uuid4().hex, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args or {}, ensure_ascii=False)}}


def response(*calls):
    return {'choices': [{'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'tool_calls': list(calls)}}]}


@pytest.fixture
def scenario(client, database_url, tmp_path):
    people = identities(client, database_url)
    (_, owner), (_, _), (agent_id, agent), (_, _), (_, _) = people
    path = create(client, owner)
    assert client.post(path+'/claim', headers=agent).status_code == 200
    client.app.state.settings.agent_checkpoint_path = str(tmp_path / 'checkpoints.sqlite')
    return client, path, agent_id, agent, people


def new_task(scenario, mode='internal_summary', **extra):
    client, path, _, agent, _ = scenario
    payload = {'request_id': uuid4().hex, 'mode': mode, 'instruction': '根据事实整理，未知信息明确标记'} | extra
    result = client.post(path+'/agent-tasks', headers=agent, json=payload)
    assert result.status_code == 200, result.text
    return result.json()['data']


def task_path(task):
    return '/api/v1/agent-tasks/'+task['id']


def scripted(monkeypatch, steps):
    calls = []
    async def post(self, kind, path, payload):
        calls.append(payload)
        step = steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step(payload) if callable(step) else step
    monkeypatch.setattr(ModelProvider, 'post', post)
    return calls


def proposal(scenario, monkeypatch, mode='internal_summary'):
    scripted(monkeypatch, [response(tool('get_ticket'), tool('read_records')),
        response(tool('propose_action', {'content': '问题：测试工单；结论：未知；待办：继续核实。'}))])
    task = new_task(scenario, mode)
    result = scenario[0].post(task_path(task)+'/run', headers=scenario[3])
    assert result.status_code == 200, result.text
    value = result.json()['data']
    assert value['status'] == 'waiting_confirmation', value
    return value


def test_internal_proposal_restart_edit_and_duplicate_confirm(scenario, database_url, monkeypatch):
    client, path, _, agent, _ = scenario
    task = proposal(scenario, monkeypatch)
    base = task_path(task)
    assert client.get(path+'/notes', headers=agent).json()['data'] == []
    # 每个run使用新SQLite连接；另建应用实例模拟进程重启后的查询/确认。
    from fastapi.testclient import TestClient
    from app.main import create_app
    with TestClient(create_app(client.app.state.settings)) as restarted:
        assert restarted.get(base, headers=agent).json()['data']['content'] == task['content']
        assert restarted.post(base+'/run', headers=agent).json()['data']['rounds'] == 2
        edited = restarted.patch(base+'/proposal', headers=agent, json={'version': 1, 'content': '核实后保存的内部摘要'}).json()['data']
        assert edited['proposal_version'] == 2 and edited['expires_at'] == task['expires_at']
        assert restarted.post(base+'/confirm', headers=agent, json={'version': 1}).status_code == 409
        assert restarted.post(base+'/confirm', headers=agent, json={'version': 2, 'content': '偷换'}).status_code == 422
        first = restarted.post(base+'/confirm', headers=agent, json={'version': 2}).json()['data']
        again = restarted.post(base+'/confirm', headers=agent, json={'version': 2}).json()['data']
        assert first['result_id'] == again['result_id'] and first['status'] == 'succeeded'
    assert [r['content'] for r in client.get(path+'/notes', headers=agent).json()['data']] == ['核实后保存的内部摘要']
    assert client.get(path+'/comments', headers=scenario[4][0][1]).json()['data'] == []


def test_creation_dedup_and_permission_isolation(scenario, database_url):
    client, path, agent_id, agent, people = scenario
    request_id = uuid4().hex
    task = new_task(scenario, request_id=request_id)
    assert new_task(scenario, request_id=request_id)['id'] == task['id']
    assert client.post(path+'/agent-tasks', headers=agent, json={'request_id': request_id,
        'mode': 'public_reply', 'instruction': '不同内容'}).status_code == 409
    base = task_path(task)
    for _, headers in (people[0], people[1], people[3], people[4]):
        assert client.get(base, headers=headers).status_code == 404
        assert client.get(path+'/agent-tasks', headers=headers).status_code == 403
        assert client.post(base+'/run', headers=headers).status_code == 404
        assert client.post(base+'/confirm', headers=headers, json={'version': 1}).status_code == 404
    assert client.get(base).status_code == 401
    set_fields(database_url, agent_id, is_active=False)
    assert client.get(base, headers=agent).status_code == 403


@pytest.mark.parametrize('mutation', ['comment', 'transfer', 'close', 'expire', 'reject', 'cancel'])
def test_invalidated_confirmation(scenario, database_url, monkeypatch, mutation):
    client, path, _, agent, people = scenario
    task = proposal(scenario, monkeypatch)
    base = task_path(task)
    if mutation == 'comment':
        client.post(path+'/comments', headers=people[0][1], json={'content': '补充信息'})
    elif mutation == 'transfer':
        assert client.post(path+'/transfer', headers=agent, json={'assignee_id': people[3][0], 'reason': '交接'}).status_code == 200
    elif mutation == 'close':
        for status, headers in [('in_progress', agent), ('resolved', agent), ('closed', people[0][1])]:
            assert client.post(path+'/status', headers=headers, json={'status': status}).status_code == 200
    elif mutation == 'expire':
        async def expire(session):
            (await session.get(AgentTask, task['id'])).expires_at = utcnow()-timedelta(seconds=1)
        db_run(database_url, expire)
    else:
        assert client.post(base+'/'+mutation, headers=agent).status_code == 200
    assert client.post(base+'/confirm', headers=agent, json={'version': 1}).status_code == (403 if mutation == 'transfer' else 409)
    if mutation == 'transfer':
        assert client.get(base, headers=agent).status_code == 403
        assert client.get(base, headers=people[3][1]).status_code == 404
    else:
        assert client.get(path+'/notes', headers=agent).json()['data'] == []


@pytest.mark.parametrize('bad', ['unknown', 'extra', 'type', 'repeat', 'no_context', 'no_citation', 'missing_model', 'timeout'])
def test_controlled_model_failures(scenario, monkeypatch, bad):
    steps = {
        'unknown': [response(tool('run_sql', {'sql': 'DELETE FROM users'}))],
        'extra': [response(tool('get_ticket', {'ticket_id': 999}))],
        'type': [response(tool('read_records', {'before_id': '123'}))],
        'repeat': [response(tool('get_ticket')), response(tool('get_ticket'))],
        'no_context': [response(tool('propose_action', {'content': '无依据'}))],
        'no_citation': [response(tool('get_ticket'), tool('read_records')), response(tool('propose_action', {'content': '承诺十分钟退款'}))],
        'missing_model': [AppError(503, 50014, 'AI服务尚未配置')],
        'timeout': [TimeoutError()],
    }[bad]
    scripted(monkeypatch, steps)
    task = new_task(scenario, 'public_reply' if bad == 'no_citation' else 'internal_summary')
    value = scenario[0].post(task_path(task)+'/run', headers=scenario[3]).json()['data']
    assert value['status'] == 'failed' and value['error']
    assert scenario[0].post(task_path(task)+'/confirm', headers=scenario[3], json={'version': 1}).status_code == 409


def test_read_only_and_clarification(scenario, monkeypatch):
    for needs_input in (False, True):
        scripted(monkeypatch, [response(tool('get_ticket')), response(tool('finish', {'message': '请提供订单号，到账时间尚无明确依据。', 'needs_input': needs_input}))])
        task = new_task(scenario)
        value = scenario[0].post(task_path(task)+'/run', headers=scenario[3]).json()['data']
        assert value['status'] == ('needs_input' if needs_input else 'completed')
        assert value['result_id'] is None


def test_plain_text_refusal_gets_bounded_tool_format_repair(scenario, monkeypatch):
    calls = scripted(monkeypatch, [
        {'choices': [{'finish_reason': 'stop', 'message': {'content': '不能提供管理员密码。'}}]},
        response(tool('finish', {'message': '不能提供密码，请描述实际业务问题。', 'needs_input': True}))])
    task = new_task(scenario, 'public_reply')
    result = scenario[0].post(task_path(task)+'/run', headers=scenario[3]).json()['data']
    assert result['status'] == 'needs_input' and result['rounds'] == 2 and result['result_id'] is None
    assert calls[-1]['messages'][-1]['role'] == 'user'


def test_failed_model_resumes_checkpoint_and_lease_fencing(scenario, database_url, monkeypatch):
    client, _, user_id, agent, _ = scenario
    calls = scripted(monkeypatch, [response(tool('get_ticket'), tool('read_records')), AppError(502, 1, '模拟上游中断'),
        response(tool('propose_action', {'content': '从检查点恢复的摘要'}))])
    task = new_task(scenario)
    base = task_path(task)
    assert client.post(base+'/run', headers=agent).json()['data']['status'] == 'failed'
    value = client.post(base+'/run', headers=agent).json()['data']
    assert value['status'] == 'waiting_confirmation' and value['generation'] == 2
    assert calls[-1]['messages'][-1]['role'] == 'tool'
    assert value['tool_calls'] == 3  # 两个读取工具只执行了一次
    another = new_task(scenario)
    async def exercise():
        engine, factory = create_database(database_url)
        tasks = AgentTasks(factory, client.app.state.settings)
        try:
            first, _ = await tasks.start(another['id'], user_id)
            with pytest.raises(AppError) as error:
                await tasks.start(another['id'], user_id)
            assert error.value.status == 409
            async with factory() as session, session.begin():
                (await session.get(AgentTask, another['id'])).lease_until = utcnow()-timedelta(seconds=1)
            second, _ = await tasks.start(another['id'], user_id)
            assert second['generation'] == first['generation']+1
            late = await tasks.finish_run(another['id'], user_id, first['generation'], result={'status': 'completed', 'content': '迟到'})
            assert late['status'] == 'running' and late['content'] == ''
            await tasks.cancel(another['id'], user_id)
            with pytest.raises(AppError):
                await tasks.progress(another['id'], user_id, second['generation'], consume='model')
        finally:
            await engine.dispose()
    asyncio.run(exercise())


def test_concurrent_confirm_and_transaction_rollback(scenario, database_url, monkeypatch):
    client, path, user_id, agent, _ = scenario
    task = proposal(scenario, monkeypatch)
    from app.services.tickets import TicketService
    original = TicketService.add_note_in_transaction
    async def failure(self, *args, **kwargs):
        await original(self, *args, **kwargs)
        raise RuntimeError('injected failure after business flush')
    async def exercise():
        engine, factory = create_database(database_url)
        tasks = AgentTasks(factory, client.app.state.settings)
        try:
            monkeypatch.setattr(TicketService, 'add_note_in_transaction', failure)
            with pytest.raises(RuntimeError):
                await tasks.confirm(task['id'], user_id, 1)
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(Comment).where(Comment.ticket_id == task['ticket_id'])) == 0
                assert await session.scalar(select(func.count()).select_from(AgentExecution).where(AgentExecution.task_id == task['id'])) == 0
            monkeypatch.setattr(TicketService, 'add_note_in_transaction', original)
            values = await asyncio.gather(*[tasks.confirm(task['id'], user_id, 1) for _ in range(3)])
            assert len({v['result_id'] for v in values}) == 1
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(Comment).where(Comment.ticket_id == task['ticket_id'])) == 1
                assert await session.scalar(select(func.count()).select_from(AgentExecution).where(AgentExecution.task_id == task['id'])) == 1
        finally:
            await engine.dispose()
    asyncio.run(exercise())


@pytest.mark.parametrize('invalidate', [False, True])
def test_public_reply_never_reads_internal_and_notifies_once(scenario, database_url, monkeypatch, invalidate):
    client, path, user_id, agent, people = scenario
    assert client.post(path+'/notes', headers=agent, json={'content': 'PRIVATE_INTERNAL_SECRET'}).status_code == 201
    doc_id = 'agent-test-'+uuid4().hex
    class Embedding:
        space = 'agent-test-space'
        async def embed(self, text):
            return [1., 0.]
    async def setup():
        engine, factory = create_database(database_url)
        try:
            async with factory() as session:
                await publish(session, Embedding(), {'id': doc_id, 'version': 1, 'title': '公开登录说明', 'digest': 'a'*64, 'chunks': ['登录请核对注册邮箱。']})
        finally:
            await engine.dispose()
    asyncio.run(setup())
    monkeypatch.setattr(ModelProvider, 'space', property(lambda _: 'agent-test-space'))
    monkeypatch.setattr(ModelProvider, 'embed', Embedding.embed)
    def draft(payload):
        assert 'PRIVATE_INTERNAL_SECRET' not in json.dumps(payload)
        sources = json.loads(payload['messages'][-1]['content'])['sources']
        source = next(s for s in sources if s['document_id'] == doc_id)
        return response(tool('propose_action', {'content': '请核对注册邮箱。', 'citations': [source['chunk_id']]}))
    scripted(monkeypatch, [response(tool('get_ticket'), tool('read_records')), response(tool('search_knowledge', {'query': '登录邮箱'})), draft])
    task = new_task(scenario, 'public_reply')
    base = task_path(task)
    value = client.post(base+'/run', headers=agent).json()['data']
    assert value['status'] == 'waiting_confirmation', value
    async def exercise():
        engine, factory = create_database(database_url)
        tasks = AgentTasks(factory, client.app.state.settings)
        try:
            if invalidate:
                async with factory() as session:
                    await deactivate(session, doc_id)
                with pytest.raises(AppError):
                    await tasks.confirm(task['id'], user_id, 1)
            else:
                # 模拟MySQL提交成功，但提交后的调度/HTTP响应失败。
                from app.services import agent_tasks
                original_after_commit = agent_tasks.after_commit
                async def response_lost(*args, **kwargs):
                    raise RuntimeError('response lost after commit')
                monkeypatch.setattr(agent_tasks, 'after_commit', response_lost)
                with pytest.raises(RuntimeError, match='response lost'):
                    await tasks.confirm(task['id'], user_id, 1)
                monkeypatch.setattr(agent_tasks, 'after_commit', original_after_commit)
                results = await asyncio.gather(tasks.confirm(task['id'], user_id, 1), tasks.confirm(task['id'], user_id, 1))
                assert results[0]['result_id'] == results[1]['result_id']
                async with factory() as session:
                    assert await session.scalar(select(func.count()).select_from(Notification).where(Notification.event_key == f"comment:{results[0]['result_id']}")) == 1
                    assert (await session.get(TicketSLA, task['ticket_id'])).first_response_at is not None
            async with factory() as session:
                await deactivate(session, doc_id)
        finally:
            await engine.dispose()
    asyncio.run(exercise())
    comments = client.get(path+'/comments', headers=people[0][1]).json()['data']
    assert len(comments) == (0 if invalidate else 1)


def test_budget_missing_checkpoint_and_record_pagination(scenario, database_url, monkeypatch):
    client, path, _, agent, _ = scenario
    for i in range(12):
        assert client.post(path+'/notes', headers=agent, json={'content': f'内部记录{i}'}).status_code == 201
    def next_page(payload):
        page = json.loads(payload['messages'][-1]['content'])
        assert len(page['records']) == 10 and page['has_more']
        return response(tool('read_records', {'before_id': page['next_before_id']}))
    def finish(payload):
        page = json.loads(payload['messages'][-1]['content'])
        assert len(page['records']) == 2 and not page['has_more']
        return response(tool('finish', {'message': '已查看12条内部记录'}))
    scripted(monkeypatch, [response(tool('read_records')), next_page, finish])
    task = new_task(scenario)
    assert client.post(task_path(task)+'/run', headers=agent).json()['data']['status'] == 'completed'
    for field, value in [('rounds', 6), ('tool_calls', 8)]:
        task = new_task(scenario)
        async def cap(session):
            setattr(await session.get(AgentTask, task['id']), field, value)
        db_run(database_url, cap)
        scripted(monkeypatch, [response(tool('get_ticket'))])
        assert client.post(task_path(task)+'/run', headers=agent).json()['data']['status'] == 'failed'
    task = new_task(scenario)
    async def lost(session):
        row = await session.get(AgentTask, task['id'])
        row.status, row.generation, row.rounds = 'failed', 1, 1
    db_run(database_url, lost)
    value = client.post(task_path(task)+'/run', headers=agent).json()['data']
    assert value['status'] == 'failed' and '检查点缺失' in value['error']


def test_two_concurrent_tasks_share_user_lease(scenario, database_url):
    client, _, user_id, _, _ = scenario
    first, second = new_task(scenario), new_task(scenario)
    async def exercise():
        engine, factory = create_database(database_url)
        tasks = AgentTasks(factory, client.app.state.settings)
        try:
            results = await asyncio.gather(tasks.start(first['id'], user_id), tasks.start(second['id'], user_id), return_exceptions=True)
            assert sum(isinstance(r, AppError) and r.status == 429 for r in results) == 1
            assert sum(isinstance(r, tuple) and r[1] for r in results) == 1
        finally:
            await engine.dispose()
    asyncio.run(exercise())


def test_checkpoint_loss_blocks_unconfirmed_but_not_committed_retry(scenario, monkeypatch):
    client, path, _, agent, _ = scenario
    first = proposal(scenario, monkeypatch)
    base = task_path(first)
    saved = client.post(base+'/confirm', headers=agent, json={'version': 1}).json()['data']
    Path(client.app.state.settings.agent_checkpoint_path).unlink()
    assert client.post(base+'/confirm', headers=agent, json={'version': 1}).json()['data']['result_id'] == saved['result_id']
    second = proposal(scenario, monkeypatch)
    Path(client.app.state.settings.agent_checkpoint_path).unlink()
    blocked = client.post(task_path(second)+'/confirm', headers=agent, json={'version': 1})
    assert blocked.status_code == 409 and '检查点' in blocked.json()['message']
    assert len(client.get(path+'/notes', headers=agent).json()['data']) == 1


def test_http_confirm_races_checkpoint_acknowledgement(scenario, monkeypatch):
    client, path, _, agent, _ = scenario
    task = proposal(scenario, monkeypatch)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(task_path(task)+'/confirm', headers=agent, json={'version': 1}), range(4)))
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert len({r.json()['data']['result_id'] for r in results}) == 1
    assert len(client.get(path+'/notes', headers=agent).json()['data']) == 1
