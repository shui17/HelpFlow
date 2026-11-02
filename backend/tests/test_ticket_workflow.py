"""完整请求、MySQL 条件更新竞争与业务/日志原子性。"""
import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import event, func, select

from app.db.session import create_database
from app.errors import AppError
from app.models import Activity, Ticket
from app.services.tickets import TicketService
from app.domain.enums import TicketStatus
from tests.test_database import database_url
from tests.test_security import client, login, register, set_fields


def identities(client, url):
    result = []
    for role in ("user", "user", "agent", "agent", "admin"):
        user, email = register(client)
        if role != "user":
            set_fields(url, user["id"], role=role)
        result.append((user["id"], login(client, email)))
    return result


def create(client, headers):
    response = client.post("/api/v1/tickets", headers=headers,
                           json={"title": "工单完整流程", "description": "验证事务和时间线"})
    assert response.status_code == 201, response.text
    return "/api/v1/tickets/" + str(response.json()["data"]["id"])


def test_complete_workflow_and_timeline(client, database_url):
    (owner, h), (_, other), (agent, ah), (agent2, bh), (admin, adm) = identities(client, database_url)
    path = create(client, h)
    assert client.get(path + "/activities").status_code == 401
    assert client.get(path + "/activities", headers=other).status_code == 403
    assert client.patch(path, headers=h, json={"title": "修订标题"}).status_code == 200
    assert client.post(path + "/claim", headers=h).status_code == 403
    claimed = client.post(path + "/claim", headers=ah)
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["data"]["status"] == "open"
    assert claimed.json()["data"]["assignee_id"] == agent
    assert claimed.json()["data"]["assigned_at"].endswith("Z")
    assert client.post(path + "/claim", headers=bh).status_code == 409
    assert client.patch(path, headers=h, json={"title": "领取后修改"}).status_code == 409
    assert client.post(path + "/cancel", headers=h).status_code == 409
    assert client.post(path + "/assign", headers=ah, json={"assignee_id": agent2}).status_code == 403
    assert client.post(path + "/assign", headers=adm, json={"assignee_id": agent}).status_code == 409
    assigned = client.post(path + "/assign", headers=adm, json={"assignee_id": agent2})
    assert assigned.status_code == 200 and assigned.json()["data"]["status"] == "open"
    assert client.get(path + "/activities", headers=ah).status_code == 403
    assert client.post(path + "/comments", headers=ah, json={"content": "原负责人"}).status_code == 403
    assert client.post(path + "/status", headers=bh, json={"status": "resolved"}).status_code == 409
    assert client.post(path + "/status", headers=adm, json={"status": "in_progress"}).status_code == 403
    for headers, state in ((bh, "in_progress"), (bh, "resolved"), (h, "in_progress"),
                           (bh, "resolved"), (h, "closed")):
        r = client.post(path + "/status", headers=headers, json={"status": state})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["assignee_id"] == agent2
        if state == "in_progress":
            assert client.post(path + "/comments", headers=headers,
                               json={"content": "用户与当前客服均可回复"}).status_code == 201
    assert r.json()["data"]["closed_at"].endswith("Z")
    assert client.post(path + "/comments", headers=h, json={"content": "关闭后回复"}).status_code == 409
    assert client.post(path + "/assign", headers=adm, json={"assignee_id": agent}).status_code == 409
    assert client.patch(path + "/status", headers=h, json={"status": "in_progress"}).status_code == 409
    logs = client.get(path + "/activities", headers=h).json()["data"]
    assert [a["action"] for a in logs] == ["created", "updated", "claimed", "reassigned",
        "status_changed", "status_changed", "reopened", "status_changed", "closed"]
    assert logs[0]["operator_id"] == owner and logs[2]["operator_id"] == agent
    assert logs[3]["operator_id"] == admin
    assert (logs[3]["old_assignee_id"], logs[3]["new_assignee_id"]) == (agent, agent2)
    assert (logs[6]["old_status"], logs[6]["new_status"]) == ("resolved", "in_progress")
    assert [(a["created_at"], a["id"]) for a in logs] == sorted((a["created_at"], a["id"]) for a in logs)
    assert client.get(path + "/activities", headers=adm).json()["data"] == logs


def test_cancel_assignment_validation_and_missing(client, database_url):
    (owner, h), (_, other), (agent, ah), (disabled, bh), (_, adm) = identities(client, database_url)
    path = create(client, h)
    assert client.post(path + "/cancel", headers=other).status_code == 403
    assert client.post(path + "/cancel", headers=ah).status_code == 403
    set_fields(database_url, disabled, is_active=False)
    for target in (owner, disabled, 9223372036854775807):
        assert client.post(path + "/assign", headers=adm, json={"assignee_id": target}).status_code == 409
    for payload in ({"assignee_id": 0}, {"assignee_id": None}, {"assignee_id": agent, "operator_id": owner}):
        assert client.post(path + "/assign", headers=adm, json=payload).status_code == 422
    assigned = client.post(path + "/assign", headers=adm, json={"assignee_id": agent})
    assert assigned.status_code == 200 and assigned.json()["data"]["status"] == "open"
    assert client.get(path + "/activities", headers=h).json()["data"][-1]["action"] == "assigned"
    path = create(client, h)
    cancelled = client.post(path + "/cancel", headers=h)
    assert cancelled.status_code == 200 and cancelled.json()["data"]["status"] == "closed"
    assert cancelled.json()["data"]["closed_at"]
    for suffix, headers in (("cancel", h), ("claim", ah)):
        assert client.post(path + "/" + suffix, headers=headers).status_code == 409
    assert client.patch(path, headers=h, json={"title": "关闭后修改"}).status_code == 409
    logs = client.get(path + "/activities", headers=h).json()["data"]
    assert [a["action"] for a in logs] == ["created", "cancelled"]
    missing = "/api/v1/tickets/9223372036854775807"
    for suffix, headers, payload in (("claim", ah, None), ("cancel", h, None),
                                     ("assign", adm, {"assignee_id": agent})):
        assert client.post(missing + "/" + suffix, headers=headers, json=payload).status_code == 404
    assert client.get(missing + "/activities", headers=h).status_code == 404


def test_concurrent_claim_and_atomic_rollback(client, database_url):
    (owner, h), (_, _), (agent, _), (agent2, _), (admin, _) = identities(client, database_url)
    ticket_id = int(create(client, h).rsplit("/", 1)[1])

    async def exercise():
        engine, factory = create_database(database_url)
        try:
            ready = asyncio.Event()
            async def claim(user_id):
                async with factory() as session:
                    await ready.wait()
                    try:
                        await TicketService(session).claim_ticket(ticket_id,
                            actor=SimpleNamespace(id=user_id, role="agent"))
                        return "success"
                    except AppError as exc:
                        assert exc.status == 409 and not session.in_transaction()
                        return "conflict"
            racers = [asyncio.create_task(claim(user)) for user in (agent, agent2)]
            ready.set()
            assert sorted(await asyncio.wait_for(asyncio.gather(*racers), timeout=15)) == ["conflict", "success"]
            async with factory() as session:
                ticket = await session.get(Ticket, ticket_id)
                winner = ticket.assignee_id
                assert winner in (agent, agent2) and ticket.status == "open"
                logs = list(await session.scalars(select(Activity).where(
                    Activity.ticket_id == ticket_id, Activity.action == "claimed")))
                assert len(logs) == 1 and logs[0].operator_id == winner
            # 日志 INSERT 失败时，负责人修改必须回滚。
            async with factory() as session:
                def fail_log(mapper, connection, target):
                    raise RuntimeError("injected activity failure")
                event.listen(Activity, "before_insert", fail_log)
                try:
                    with pytest.raises(RuntimeError, match="injected activity"):
                        await TicketService(session).assign_ticket(ticket_id,
                            agent2 if winner == agent else agent,
                            actor=SimpleNamespace(id=admin, role="admin"))
                finally:
                    event.remove(Activity, "before_insert", fail_log)
                assert not session.in_transaction()
            async with factory() as session:
                assert (await session.get(Ticket, ticket_id)).assignee_id == winner
                assert await session.scalar(select(func.count()).select_from(Activity).where(
                    Activity.ticket_id == ticket_id)) == 2
            # 提交失败时，状态和日志也一起回滚。
            async with factory() as session:
                def fail_commit(s):
                    raise RuntimeError("injected commit failure")
                event.listen(session.sync_session, "before_commit", fail_commit)
                with pytest.raises(RuntimeError, match="injected commit"):
                    await TicketService(session).change_status(ticket_id,
                        TicketStatus.IN_PROGRESS,
                        actor=SimpleNamespace(id=winner, role="agent"))
                event.remove(session.sync_session, "before_commit", fail_commit)
                assert not session.in_transaction()
            async with factory() as session:
                assert (await session.get(Ticket, ticket_id)).status == "open"
                assert await session.scalar(select(func.count()).select_from(Activity).where(
                    Activity.ticket_id == ticket_id)) == 2
            assert engine.pool.checkedout() == 0
        finally:
            await engine.dispose()
    asyncio.run(exercise())
