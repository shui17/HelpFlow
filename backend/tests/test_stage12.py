"""阶段12真实 MySQL：隐私、转交竞争、通知幂等与故障回滚。"""
import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import event, func, select

from app.db.session import create_database
from app.domain.enums import TicketStatus
from app.errors import AppError
from app.models import Activity, Comment, Notification, Ticket
from app.services.notifications import enqueue
from app.services.tickets import TicketService
from tests.test_database import database_url
from tests.test_security import client
from tests.test_ticket_workflow import identities, create


def test_collaboration_privacy_and_notifications(client, database_url):
    (_, owner), (_, outsider), (a, ah), (b, bh), (_, admin) = identities(client, database_url)
    path = create(client, owner)
    assert client.get('/api/v1/tickets/agents', headers=owner).status_code == 403
    options = client.get('/api/v1/tickets/agents', headers=ah).json()['data']
    assert all(set(row) == {'id', 'username'} for row in options)
    assert client.post(path + '/claim', headers=ah).status_code == 200
    note = client.post(path + '/notes', headers=ah, json={'content': '仅内部：敏感排查信息'})
    assert note.status_code == 201
    for h in (owner, outsider, bh):
        assert client.get(path + '/notes', headers=h).status_code == 403
        assert client.post(path + '/notes', headers=h, json={'content': '越权'}).status_code == 403
    assert client.get(path + '/comments', headers=owner).json()['data'] == []
    assert client.get(path + '/comments', headers=owner, params={'before_id': note.json()['data']['id'] + 1}).json()['data'] == []
    assert client.get('/api/v1/notifications', headers=owner).json()['data'] == []
    assert client.post(path + '/transfer', headers=ah, json={'assignee_id': a, 'reason': '自己'}).status_code == 400
    assert client.post(path + '/transfer', headers=ah, json={'assignee_id': b, 'reason': '   '}).status_code == 422
    transferred = client.post(path + '/transfer', headers=ah, json={'assignee_id': b, 'reason': '内部转交原因'})
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()['data']['assignee_id'] == b
    assert client.post(path + '/transfer', headers=ah, json={'assignee_id': b, 'reason': '重复'}).status_code == 409
    assert client.get(path + '/notes', headers=ah).status_code == 403
    assert client.get(path + '/notes', headers=bh).json()['data'][0]['content'] == '仅内部：敏感排查信息'
    assert client.get(path + '/notes', headers=admin).status_code == 200
    assert client.post(path + '/comments', headers=ah, json={'content': '旧负责人'}).status_code == 403
    assert '内部转交原因' not in client.get(path + '/activities', headers=owner).text
    assert '内部转交原因' in client.get(path + '/activities', headers=admin).text
    notice = client.get('/api/v1/notifications', headers=bh).json()['data'][0]
    assert notice['ticket_id'] == int(path.rsplit('/', 1)[1])
    assert client.patch(f"/api/v1/notifications/{notice['id']}/read", headers=owner).status_code == 404
    first = client.patch(f"/api/v1/notifications/{notice['id']}/read", headers=bh).json()['data']
    assert first['read_at']
    assert client.patch(f"/api/v1/notifications/{notice['id']}/read", headers=bh).json()['data']['read_at'] == first['read_at']
    assert client.get('/api/v1/notifications/unread-count', headers=bh).json()['data'] == 0
    assert client.post(path + '/comments', headers=owner, json={'content': '补充问题'}).status_code == 201
    assert client.get('/api/v1/notifications/unread-count', headers=bh).json()['data'] == 1
    assert client.post(path + '/comments', headers=bh, json={'content': '公开回复'}).status_code == 201
    assert client.get('/api/v1/notifications/unread-count', headers=owner).json()['data'] == 1
    for h, state in ((bh, 'in_progress'), (bh, 'resolved'), (owner, 'closed')):
        assert client.post(path + '/status', headers=h, json={'status': state}).status_code == 200
    assert client.post(path + '/transfer', headers=bh, json={'assignee_id': a, 'reason': '关闭后'}).status_code == 409
    assert client.post(path + '/notes', headers=admin, json={'content': '关闭后'}).status_code == 409
    assert client.get(path + '/notes', headers=bh).status_code == 200


@pytest.mark.parametrize('competition', ['transfer', 'assign', 'close'])
def test_transfer_races(client, database_url, competition):
    (owner, oh), (_, _), (a, ah), (b, _), (admin, _) = identities(client, database_url)
    path = create(client, oh)
    ticket_id = int(path.rsplit('/', 1)[1])
    assert client.post(path + '/claim', headers=ah).status_code == 200
    if competition == 'close':
        for state in ('in_progress', 'resolved'):
            assert client.post(path + '/status', headers=ah, json={'status': state}).status_code == 200

    async def exercise():
        engine, factory = create_database(database_url)
        ready = asyncio.Event()
        async def run(kind):
            async with factory() as session:
                await ready.wait()
                service = TicketService(session)
                try:
                    if kind == 'transfer':
                        await service.transfer_ticket(ticket_id, b, '并发转交', actor=SimpleNamespace(id=a, role='agent'))
                    elif kind == 'assign':
                        await service.assign_ticket(ticket_id, b, actor=SimpleNamespace(id=admin, role='admin'))
                    else:
                        await service.change_status(ticket_id, TicketStatus.CLOSED, actor=SimpleNamespace(id=owner, role='user'))
                    return 'success'
                except AppError as exc:
                    assert exc.status == 409
                    return 'conflict'
        try:
            jobs = [asyncio.create_task(run(kind)) for kind in ('transfer', competition)]
            ready.set()
            results = await asyncio.wait_for(asyncio.gather(*jobs), 15)
            if competition != 'close':
                assert sorted(results) == ['conflict', 'success']
            async with factory() as session:
                ticket = await session.get(Ticket, ticket_id)
                logs = list(await session.scalars(select(Activity).where(Activity.ticket_id == ticket_id).order_by(Activity.id)))
                changes = [row for row in logs if row.new_assignee_id is not None]
                assert ticket.assignee_id == changes[-1].new_assignee_id
                assert ticket.status == ('closed' if competition == 'close' else 'open')
                assert await session.scalar(select(func.count()).select_from(Notification).where(
                    Notification.ticket_id == ticket_id)) == len(changes) - 1
        finally:
            await engine.dispose()
    asyncio.run(exercise())


@pytest.mark.parametrize('failure', ['notification', 'activity', 'comment'])
def test_notification_atomicity_and_duplicate_events(client, database_url, failure):
    (_, oh), (_, _), (a, ah), (b, _), (_, _) = identities(client, database_url)
    ticket_id = int(create(client, oh).rsplit('/', 1)[1])
    assert client.post(f'/api/v1/tickets/{ticket_id}/claim', headers=ah).status_code == 200
    async def exercise():
        engine, factory = create_database(database_url)
        model = {'notification': Notification, 'activity': Activity, 'comment': Notification}[failure]
        def fail(*args):
            raise RuntimeError('injected stage12 failure')
        try:
            async with factory() as session:
                event.listen(model, 'before_insert', fail)
                try:
                    with pytest.raises(RuntimeError, match='injected stage12'):
                        if failure == 'comment':
                            await TicketService(session).add_comment(ticket_id, a, '回滚回复', actor=SimpleNamespace(id=a, role='agent'))
                        else:
                            await TicketService(session).transfer_ticket(ticket_id, b, '回滚转交', actor=SimpleNamespace(id=a, role='agent'))
                finally:
                    event.remove(model, 'before_insert', fail)
                assert not session.in_transaction()
            async with factory() as session:
                assert (await session.get(Ticket, ticket_id)).assignee_id == a
                assert await session.scalar(select(func.count()).select_from(Activity).where(Activity.ticket_id == ticket_id)) == 2
                assert await session.scalar(select(func.count()).select_from(Comment).where(Comment.ticket_id == ticket_id)) == 0
                assert await session.scalar(select(func.count()).select_from(Notification).where(Notification.ticket_id == ticket_id)) == 0
            async def deliver():
                async with factory() as session, session.begin():
                    await enqueue(session, event_key=f'test:{ticket_id}', recipient_id=b,
                                  ticket_id=ticket_id, message='重复事件')
            await asyncio.wait_for(asyncio.gather(deliver(), deliver()), 15)
            await deliver()
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(Notification).where(Notification.ticket_id == ticket_id)) == 1
        finally:
            await engine.dispose()
    asyncio.run(exercise())
