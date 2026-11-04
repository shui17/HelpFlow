"""SLA 边界、真实 MySQL 并发、事务失败与 Redis 索引丢失补偿。"""
import asyncio
from datetime import timedelta
from types import SimpleNamespace
import os
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select

from app.db.base import utcnow
from app.db.session import create_database
from app.domain.enums import TicketStatus
from app.models import Comment, Notification, SLAEvent, SLARule, Ticket, TicketSLA
from app.services.sla import describe
from app.services.tickets import TicketService
from scripts.scan_sla import Scanner
from app.config import Settings
from app.sla_scheduler import SLAIndex
from tests.test_database import database_url
from tests.test_security import client
from tests.test_ticket_workflow import create, identities


class MemoryIndex:
    """可丢失/断连的调度索引替身；真实 Redis 用例另测协议与服务。"""
    key = "test:sla"

    def __init__(self, offline=False):
        self.members = {}
        self.offline = offline

    def begin_round(self):
        pass

    async def put(self, row):
        if not self.offline:
            self.members[f"{row.ticket_id}:{row.version}"] = row.due_at.timestamp()

    async def remove(self, member):
        if not self.offline:
            self.members.pop(member, None)

    async def command(self, command, key, *args, **kwargs):
        if self.offline:
            return None
        ordered = sorted(self.members, key=lambda k: (self.members[k], k))
        if command == "zrangebyscore":
            found = [k for k in ordered if self.members[k] <= args[1]]
            start = kwargs["start"]
            return found[start:start + kwargs["num"]]
        if command == "zrank":
            return ordered.index(args[0]) if args[0] in ordered else None
        if command == "zscore":
            return self.members.get(args[0])
        raise AssertionError(command)


def run_db(url, action):
    async def run():
        engine, factory = create_database(url)
        try:
            return await action(factory)
        finally:
            await engine.dispose()
    return asyncio.run(run())


def set_due(url, ticket_id, due):
    async def change(factory):
        async with factory() as session, session.begin():
            row = await session.get(TicketSLA, ticket_id)
            row.due_at = due
    run_db(url, change)


def test_describe_boundary_and_termination():
    now = utcnow()
    row = SimpleNamespace(version=1, priority="normal", response_seconds=3600, warning_seconds=900,
        due_at=now, first_response_at=None, terminated_at=None, escalated_at=None)
    assert describe(None) is None
    assert describe(row, now)["state"] == "due_soon"
    assert describe(row, now + timedelta(microseconds=1))["state"] == "overdue"
    row.terminated_at = now
    assert describe(row, now + timedelta(days=1))["state"] == "terminated"
    row.escalated_at = now
    assert describe(row, now)["state"] == "overdue"


def test_redis_failure_is_bounded_and_does_not_log_credentials(caplog):
    async def exercise():
        index = SLAIndex(Settings(_env_file=None, redis_url="redis://127.0.0.1:1/0"))
        async def fail(*args, **kwargs):
            raise ConnectionError("secret-password-must-not-leak")
        index.redis.zadd = fail
        try:
            assert await index.command("zadd", index.key, {"1:1": 0}) is None
        finally:
            await index.close()
    asyncio.run(exercise())
    assert "secret-password-must-not-leak" not in caplog.text
    assert "ConnectionError" in caplog.text


@pytest.mark.parametrize("delta,expected", [(-1, "on_time"), (0, "on_time"), (1, "overdue")])
def test_first_response_microsecond_boundary(client, database_url, monkeypatch, delta, expected):
    (_, owner), (_, _), (_, ah), (_, _), (_, _) = identities(client, database_url)
    path = create(client, owner)
    ticket_id = int(path.rsplit("/", 1)[1])
    due = utcnow() + timedelta(hours=1)
    set_due(database_url, ticket_id, due)
    assert client.post(path + "/claim", headers=ah).status_code == 200
    assert client.post(path + "/notes", headers=ah, json={"content": "内部备注不算响应"}).status_code == 201
    assert client.post(path + "/comments", headers=owner, json={"content": "用户补充不算响应"}).status_code == 201
    assert client.get(path, headers=owner).json()["data"]["sla"]["first_response_at"] is None
    response_time = due + timedelta(microseconds=delta)
    monkeypatch.setattr("app.services.tickets.utcnow", lambda: response_time)
    response = client.post(path + "/comments", headers=ah, json={"content": "第一次公开回复"})
    assert response.status_code == 201, response.text
    first = client.get(path, headers=ah).json()["data"]["sla"]
    assert first["state"] == expected
    assert first["first_response_at"] == response.json()["data"]["created_at"]
    monkeypatch.setattr("app.services.tickets.utcnow", lambda: due + timedelta(hours=2))
    assert client.post(path + "/comments", headers=ah, json={"content": "第二次回复"}).status_code == 201
    assert client.get(path, headers=ah).json()["data"]["sla"] == first
    rows = client.get(path + "/sla-events", headers=owner).json()["data"]
    assert [row["kind"] for row in rows] == (["overdue"] if delta > 0 else [])


def test_snapshots_permissions_close_transfer_and_filters(client, database_url):
    (_, owner), (_, outsider), (_, ah), (b, bh), (_, admin) = identities(client, database_url)
    path = create(client, owner)
    ticket_id = int(path.rsplit("/", 1)[1])
    original = client.get(path, headers=owner).json()["data"]["sla"]
    assert client.patch(path, headers=owner, json={"priority": "urgent"}).status_code == 200
    changed = client.get(path, headers=owner).json()["data"]["sla"]
    assert changed == original and changed["priority"] == "normal"
    assert client.get(path + "/sla-events", headers=outsider).status_code == 403
    assert client.post(path + "/claim", headers=ah).status_code == 200
    assert client.post(path + "/transfer", headers=ah, json={"assignee_id": b, "reason": "继续处理"}).status_code == 200
    assert client.get(path + "/sla-events", headers=ah).status_code == 403
    assert client.get(path, headers=bh).json()["data"]["sla"] == original
    set_due(database_url, ticket_id, utcnow() + timedelta(minutes=5))
    fixed_due = client.get(path, headers=owner).json()["data"]["sla"]["due_at"]
    for h, scope in ((bh, "mine"), (owner, None), (admin, None)):
        result = client.get("/api/v1/tickets", headers=h, params={"sla": "due_soon", **({"scope": scope} if scope else {})}).json()["data"]
        assert ticket_id in [row["id"] for row in result["items"]]
        assert client.get("/api/v1/tickets/summary", headers=h).json()["data"]["counts"]["due_soon"] >= 1
    assert client.get("/api/v1/tickets", headers=outsider, params={"sla": "due_soon"}).json()["data"]["total"] == 0
    assert client.get("/api/v1/tickets", headers=owner, params={"sla": "invalid"}).status_code == 422
    for state in ("in_progress", "resolved"):
        assert client.post(path + "/status", headers=bh, json={"status": state}).status_code == 200
    assert client.post(path + "/status", headers=owner, json={"status": "in_progress"}).status_code == 200
    assert client.get(path, headers=bh).json()["data"]["sla"]["due_at"] == fixed_due
    assert client.post(path + "/status", headers=bh, json={"status": "resolved"}).status_code == 200
    assert client.post(path + "/status", headers=owner, json={"status": "closed"}).status_code == 200
    assert client.get(path, headers=owner).json()["data"]["sla"]["state"] == "terminated"
    cancelled = create(client, owner)
    assert client.post(cancelled + "/cancel", headers=owner).status_code == 200
    assert client.get(cancelled, headers=owner).json()["data"]["sla"]["state"] == "terminated"


def test_compensation_pagination_and_two_scanners(client, database_url):
    (_, owner), (_, _), (_, ah), (_, _), (_, _) = identities(client, database_url)
    paths = [create(client, owner) for _ in range(5)]
    ids = [int(p.rsplit("/", 1)[1]) for p in paths]
    now = utcnow()
    for ticket_id in ids:
        set_due(database_url, ticket_id, now - timedelta(seconds=10))
    assert client.post(paths[0] + "/claim", headers=ah).status_code == 200

    async def exercise(factory):
        index = MemoryIndex()  # 模拟提交成功、写入 Redis 前停机或 Redis 清空。
        scanners = [Scanner(factory, index, batch_size=2) for _ in range(2)]
        await asyncio.wait_for(asyncio.gather(*(s.run_once(now=now) for s in scanners)), 30)
        await scanners[0].run_once(now=now)
        async with factory() as session:
            events = list(await session.scalars(select(SLAEvent).where(SLAEvent.ticket_id.in_(ids))))
            assert len(events) == 5 and all(e.kind == "overdue" for e in events)
            notices = list(await session.scalars(select(Notification).where(Notification.ticket_id.in_(ids))))
            keys = [(n.event_key, n.recipient_id) for n in notices]
            assert len(keys) == len(set(keys))
            assert all(f"{ticket_id}:1" not in index.members for ticket_id in ids)
    run_db(database_url, exercise)
    assert client.get(paths[0], headers=owner).json()["data"]["sla"]["state"] == "overdue"
    assert client.get("/api/v1/tickets", headers=owner, params={"sla": "overdue"}).json()["data"]["total"] == 5


def test_commit_failure_preserves_pending_and_reply(client, database_url):
    (_, owner), (_, _), (agent, ah), (_, _), (_, _) = identities(client, database_url)
    path = create(client, owner)
    ticket_id = int(path.rsplit("/", 1)[1])
    assert client.post(path + "/claim", headers=ah).status_code == 200
    set_due(database_url, ticket_id, utcnow() - timedelta(seconds=3))

    async def exercise(factory):
        async with factory() as session:
            def fail_commit(sync):
                # enqueue 的嵌套 SAVEPOINT 不代表外层业务提交。
                if not sync.in_nested_transaction():
                    raise RuntimeError("injected commit failure")
            event.listen(session.sync_session, "before_commit", fail_commit)
            with pytest.raises(RuntimeError, match="injected"):
                await TicketService(session).add_comment(ticket_id, agent, "必须一起回滚",
                    actor=SimpleNamespace(id=agent, role="agent"))
        async with factory() as session:
            row = await session.get(TicketSLA, ticket_id)
            assert row.first_response_at is None and row.escalated_at is None
            assert not await session.scalar(select(Comment.id).where(Comment.ticket_id == ticket_id))
            assert not await session.scalar(select(SLAEvent.id).where(SLAEvent.ticket_id == ticket_id))
    run_db(database_url, exercise)


def test_rule_versions_legacy_and_overdue_before_scanning(client, database_url, monkeypatch):
    from scripts.configure_sla import configure
    (_, owner), (_, _), (_, _), (_, _), (_, _) = identities(client, database_url)
    path = create(client, owner)
    ticket_id = int(path.rsplit("/", 1)[1])
    due = utcnow() - timedelta(seconds=1)
    set_due(database_url, ticket_id, due)
    # 超时事实不依赖扫描器先写通知。
    assert client.get(path, headers=owner).json()["data"]["sla"]["state"] == "overdue"
    assert client.get("/api/v1/tickets", headers=owner, params={"sla": "overdue"}).json()["data"]["total"] == 1
    monkeypatch.setenv("HELPFLOW_DATABASE_URL", database_url)
    args = SimpleNamespace(priority="low", version=900013, seconds=1234, warning_seconds=234)
    try:
        asyncio.run(configure(args))
        response = client.post("/api/v1/tickets", headers=owner,
            json={"title": "新版本规则", "description": "仅新工单", "priority": "low"})
        assert response.status_code == 201
        assert response.json()["data"]["sla"]["version"] == args.version
        assert response.json()["data"]["sla"]["response_seconds"] == 1234
        assert client.get(path, headers=owner).json()["data"]["sla"]["version"] == 1
        with pytest.raises(ValueError):
            asyncio.run(configure(args))
    finally:
        async def cleanup(factory):
            async with factory() as session, session.begin():
                await session.execute(delete(SLARule).where(SLARule.priority == "low", SLARule.version == args.version))
                await session.execute(delete(TicketSLA).where(TicketSLA.ticket_id == ticket_id))
        run_db(database_url, cleanup)
    # 既有工单没有快照时可正常读写，不能虚构历史 SLA。
    assert client.get(path, headers=owner).json()["data"]["sla"] is None
    assert client.get(path + "/sla-events", headers=owner).json()["data"] == []


def test_redis_write_failure_keeps_created_ticket(client, database_url, monkeypatch):
    (_, owner), (_, _), (_, _), (_, _), (_, _) = identities(client, database_url)
    async def broken(*args, **kwargs):
        raise ConnectionError("injected offline")
    monkeypatch.setattr("redis.asyncio.Redis.zadd", broken)
    monkeypatch.setenv("HELPFLOW_REDIS_URL", "redis://127.0.0.1:1/0")
    client.app.state.settings.redis_url = Settings(_env_file=None).redis_url
    path = create(client, owner)
    assert client.get(path, headers=owner).json()["data"]["sla"]["state"] == "waiting"


@pytest.mark.skipif(not os.getenv("HELPFLOW_TEST_REDIS_URL"), reason="需要显式 HELPFLOW_TEST_REDIS_URL 验证真实 Redis")
def test_real_redis_index_loss_and_recovery(client, database_url, monkeypatch):
    redis_url = os.environ["HELPFLOW_TEST_REDIS_URL"]
    key = "helpflow:test:sla:" + uuid4().hex
    monkeypatch.setenv("HELPFLOW_REDIS_URL", redis_url)
    monkeypatch.setenv("HELPFLOW_SLA_REDIS_KEY", key)
    client.app.state.settings.redis_url = Settings(_env_file=None).redis_url
    client.app.state.settings.sla_redis_key = key
    (_, owner), (_, _), (_, _), (_, _), (_, _) = identities(client, database_url)
    path = create(client, owner)
    ticket_id = int(path.rsplit("/", 1)[1])
    now = utcnow()

    async def exercise(factory):
        index = SLAIndex(Settings(_env_file=None, redis_url=redis_url, sla_redis_key=key))
        try:
            assert await index.redis.ping()
            assert await index.redis.zscore(key, f"{ticket_id}:1") is not None  # 创建提交后写入。
            await index.redis.delete(key)  # 只删除本测试随机命名的键。
            scanner = Scanner(factory, index, batch_size=2)
            await scanner.run_once(now=now)
            assert await index.redis.zscore(key, f"{ticket_id}:1") is not None
            async with factory() as session, session.begin():
                row = await session.get(TicketSLA, ticket_id)
                row.due_at = now - timedelta(seconds=2)
            async with factory() as session:
                row = await session.get(TicketSLA, ticket_id)
                await index.put(row)
            await scanner.run_once(compensate=False, now=now)
            assert await index.redis.zscore(key, f"{ticket_id}:1") is None
            async with factory() as session:
                assert (await session.get(TicketSLA, ticket_id)).escalated_at is not None
        finally:
            await index.redis.delete(key)
            await index.close()
    run_db(database_url, exercise)


def test_redis_pages_warning_dedupe_and_rebuild(client, database_url):
    (_, owner), (_, _), (_, _), (_, _), (_, _) = identities(client, database_url)
    ids = [int(create(client, owner).rsplit("/", 1)[1]) for _ in range(5)]
    now = utcnow()
    for ticket_id in ids:
        set_due(database_url, ticket_id, now + timedelta(minutes=1))

    async def exercise(factory):
        index = MemoryIndex()
        scanner = Scanner(factory, index, batch_size=2)
        await scanner.run_once(now=now)  # 补偿所有行，并各提醒一次。
        assert all(f"{ticket_id}:1" in index.members for ticket_id in ids)
        await scanner.run_once(compensate=False, now=now)
        index.members.clear()
        await scanner.run_once(now=now)
        assert all(f"{ticket_id}:1" in index.members for ticket_id in ids)
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(SLAEvent).where(SLAEvent.ticket_id.in_(ids))) == 5
        await scanner.run_once(compensate=False, now=now + timedelta(minutes=2))
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(SLAEvent).where(SLAEvent.ticket_id.in_(ids))) == 10
        assert all(f"{ticket_id}:1" not in index.members for ticket_id in ids)
    run_db(database_url, exercise)


def test_offline_fallback_and_notification_rollback(client, database_url, monkeypatch):
    (_, owner), (_, _), (agent, ah), (_, _), (_, _) = identities(client, database_url)
    path = create(client, owner)
    ticket_id = int(path.rsplit("/", 1)[1])
    assert client.post(path + "/claim", headers=ah).status_code == 200
    set_due(database_url, ticket_id, utcnow() - timedelta(seconds=2))
    original = __import__('app.services.sla', fromlist=['enqueue']).enqueue
    async def failing(session, **kwargs):
        if kwargs["ticket_id"] == ticket_id:
            raise RuntimeError("injected notification failure")
        return await original(session, **kwargs)
    monkeypatch.setattr("app.services.sla.enqueue", failing)

    async def exercise(factory):
        scanner = Scanner(factory, MemoryIndex(offline=True), batch_size=2)
        stats = await scanner.run_once()
        assert stats["failed"] >= 1
        async with factory() as session:
            row = await session.get(TicketSLA, ticket_id)
            assert row.escalated_at is None
            assert not await session.scalar(select(SLAEvent.id).where(SLAEvent.ticket_id == ticket_id))
        async with factory() as session:
            with pytest.raises(RuntimeError, match="injected"):
                await TicketService(session).add_comment(ticket_id, agent, "应当回滚", actor=SimpleNamespace(id=agent, role="agent"))
        async with factory() as session:
            assert (await session.get(TicketSLA, ticket_id)).first_response_at is None
            assert not await session.scalar(select(Comment.id).where(Comment.ticket_id == ticket_id))
        monkeypatch.setattr("app.services.sla.enqueue", original)
        await scanner.run_once()
        async with factory() as session:
            assert (await session.get(TicketSLA, ticket_id)).escalated_at is not None
    run_db(database_url, exercise)


@pytest.mark.parametrize("competitor", ["reply", "close"])
def test_scanner_competes_with_reply_or_close(client, database_url, competitor):
    (user, owner), (_, _), (agent, ah), (_, _), (_, _) = identities(client, database_url)
    path = create(client, owner)
    ticket_id = int(path.rsplit("/", 1)[1])
    assert client.post(path + "/claim", headers=ah).status_code == 200
    if competitor == "close":
        for state in ("in_progress", "resolved"):
            assert client.post(path + "/status", headers=ah, json={"status": state}).status_code == 200
    set_due(database_url, ticket_id, utcnow() - timedelta(seconds=5))

    async def exercise(factory):
        scanner = Scanner(factory, MemoryIndex())
        async def action():
            async with factory() as session:
                service = TicketService(session)
                if competitor == "reply":
                    await service.add_comment(ticket_id, agent, "并发首次回复", actor=SimpleNamespace(id=agent, role="agent"))
                else:
                    await service.change_status(ticket_id, TicketStatus.CLOSED, actor=SimpleNamespace(id=user, role="user"))
        stats = dict(processed=0, events=0, failed=0, max_detection_delay_seconds=0)
        await asyncio.wait_for(asyncio.gather(scanner.process(ticket_id, 1, stats), action()), 15)
        assert stats["failed"] == 0
        async with factory() as session:
            row = await session.get(TicketSLA, ticket_id)
            count = await session.scalar(select(func.count()).select_from(SLAEvent).where(SLAEvent.ticket_id == ticket_id))
            assert count == (1 if row.escalated_at else 0)
            if competitor == "reply":
                assert row.first_response_at and count == 1
            else:
                assert row.terminated_at
    run_db(database_url, exercise)
