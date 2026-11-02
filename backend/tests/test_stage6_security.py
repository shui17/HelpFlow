"""阶段六真实认证回归；数据库用例只在显式隔离测试库上运行。"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.config import Settings
from app.db.session import create_database
from app.errors import AppError
from app.main import create_app
from app.models import Ticket, User, UserAdminLog
from app.schemas import UserRegisterRequest
from app.security import create_access_token, decode_access_token, hash_password, verify_password
from app.services.users import UserService
from scripts.init_admin import init_admin
from tests.test_stage5_database import database_url

PASSWORD = "Stage6pass123 "


def test_password_and_tokens():
    settings = Settings(_env_file=None)
    async def check():
        hashed = await hash_password(PASSWORD)
        assert hashed.startswith("$argon2id$") and PASSWORD not in hashed
        assert await verify_password(PASSWORD, hashed)
        assert not await verify_password(PASSWORD.strip(), hashed)
        assert not await verify_password(PASSWORD, "!stage5-no-login")
        assert not await verify_password(PASSWORD, None)
        return hashed
    hashed = asyncio.run(check())
    token = create_access_token(SimpleNamespace(id=1, role="user", password_hash=hashed), settings)
    assert decode_access_token(token, settings)["sub"] == "1"
    claims = jwt.decode(token, settings.signing_key(), algorithms=["HS256"])
    for changes in ({"exp": datetime.now(timezone.utc) - timedelta(seconds=5)},
                    {"sub": "-1"}, {"sub": "9" * 300}, {"pwdv": None}, {"pwdv": "非ASCII"}):
        with pytest.raises(AppError):
            decode_access_token(jwt.encode(claims | changes, settings.signing_key(), algorithm="HS256"), settings)
    for claim in ("sub", "exp", "iat", "role", "pwdv"):
        with pytest.raises(AppError):
            decode_access_token(jwt.encode({k: v for k, v in claims.items() if k != claim},
                settings.signing_key(), algorithm="HS256"), settings)
    with pytest.raises(AppError):
        decode_access_token(jwt.encode(claims, "wrong-signing-key-with-at-least-32-bytes", algorithm="HS256"), settings)
    with pytest.raises(ValueError):
        Settings(_env_file=None, jwt_secret_key=None).signing_key()
    with pytest.raises(ValueError):
        Settings(_env_file=None, jwt_secret_key="short").signing_key()


@pytest.mark.parametrize("changes", [
    {"password": "short1", "confirm_password": "short1"},
    {"password": "a" * 65, "confirm_password": "a" * 65},
    {"password": "abcdefgh", "confirm_password": "abcdefgh"},
    {"password": "12345678", "confirm_password": "12345678"},
    {"confirm_password": "Otherpass123"}, {"username": "a"},
    {"role": "admin"}, {"is_active": False},
])
def test_registration_validation_does_not_echo_password(changes):
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.post("/api/v1/auth/register", json={"username": "测试用户",
            "email": "test@example.com", "password": PASSWORD, "confirm_password": PASSWORD} | changes)
        assert response.status_code == 422
        assert PASSWORD not in response.text
        assert all("input" not in e for e in response.json()["data"])


@pytest.fixture
def client(database_url):
    # 不覆盖任何认证/Service 依赖，经过完整 MySQL 请求路径。
    with TestClient(create_app(Settings(_env_file=None, database_url=database_url))) as c:
        yield c


def register(client):
    email = f"security{uuid4().hex}@example.com"
    response = client.post("/api/v1/auth/register", json={"username": "安全测试", "email": email,
        "password": PASSWORD, "confirm_password": PASSWORD})
    assert response.status_code == 201, response.text
    assert "password" not in response.text
    return response.json()["data"], email


def login(client, email, password=PASSWORD):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["expires_in"] == 7200 and data["token_type"] == "bearer"
    return {"Authorization": "Bearer " + data["access_token"]}


def db_run(url, operation):
    async def execute():
        engine, factory = create_database(url)
        try:
            async with factory() as session:
                async with session.begin():
                    return await operation(session)
        finally:
            await engine.dispose()
    return asyncio.run(execute())


def set_fields(url, user_id, **fields):
    async def change(session):
        user = await session.get(User, user_id)
        for key, value in fields.items():
            setattr(user, key, value)
    db_run(url, change)


def test_authentication_and_password_revocation(client, database_url, caplog):
    user, email = register(client)
    for header in ({}, {"Authorization": "Bearer forged"}, {"Authorization": "Basic invalid"}):
        r = client.get("/api/v1/auth/me", headers=header)
        assert r.status_code == 401 and r.json()["code"] == 20002
        assert r.headers["www-authenticate"] == "Bearer"
    wrong = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
    unknown = client.post("/api/v1/auth/login", json={"email": "absent@example.com", "password": "wrong"})
    assert wrong.json() == unknown.json() and wrong.status_code == 401
    headers = login(client, email.upper())
    token = headers["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(token, client.app.state.settings.signing_key(), algorithms=["HS256"])
    expired = jwt.encode(claims | {"exp": datetime.now(timezone.utc) - timedelta(seconds=5)},
        client.app.state.settings.signing_key(), algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + expired}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers).json()["data"] == user
    bad = client.patch("/api/v1/auth/password", headers=headers, json={"current_password": "wrong",
        "new_password": "Changedpass123", "confirm_password": "Changedpass123"})
    assert bad.status_code == 400 and bad.json()["code"] == 20004
    assert client.patch("/api/v1/auth/password", headers=headers, json={"current_password": PASSWORD,
        "new_password": "Changedpass123", "confirm_password": "Changedpass123"}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).status_code == 401
    new_headers = login(client, email, "Changedpass123")
    set_fields(database_url, user["id"], is_active=False)
    assert client.get("/api/v1/auth/me", headers=new_headers).json()["code"] == 20003
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "Changedpass123"}).status_code == 403
    assert PASSWORD not in caplog.text and new_headers["Authorization"] not in caplog.text


def test_roles_and_ticket_ownership(client, database_url):
    owner, email = register(client)
    other, other_email = register(client)
    agent, agent_email = register(client)
    admin, admin_email = register(client)
    set_fields(database_url, agent["id"], role="agent")
    set_fields(database_url, admin["id"], role="admin")
    h, other_h, agent_h, admin_h = [login(client, e) for e in (email, other_email, agent_email, admin_email)]
    r = client.post("/api/v1/tickets", headers=h, json={"title": "所有权", "description": "范围测试"})
    assert r.status_code == 201, r.text
    ticket_id = r.json()["data"]["id"]
    path = f"/api/v1/tickets/{ticket_id}"
    assert client.post("/api/v1/tickets", headers=h, json={"title": "伪造", "description": "伪造",
        "creator_id": other["id"]}).status_code == 422
    assert client.post("/api/v1/tickets", headers=agent_h, json={"title": "不允许", "description": "描述"}).status_code == 403
    assert client.get(path, headers=other_h).status_code == 403
    assert client.get(path + "/comments", headers=other_h).status_code == 403
    assert ticket_id not in [t["id"] for t in client.get("/api/v1/tickets", headers=other_h).json()["data"]["items"]]
    assert client.get(path, headers=agent_h).status_code == 200
    assert client.patch(path, headers=agent_h, json={"title": "越权"}).status_code == 403
    assert client.post(path + "/comments", headers=agent_h, json={"content": "未负责"}).status_code == 403
    assert client.post(path + "/comments", headers=admin_h, json={"content": "管理员"}).status_code == 403
    assert client.post(path + "/comments", headers=h, json={"content": "补充"}).json()["data"]["author_id"] == owner["id"]
    assert client.post(path + "/comments", headers=h, json={"content": "伪造", "author_id": other["id"]}).status_code == 422
    assert client.patch(path, headers=h, json={"title": "修改成功"}).status_code == 200
    async def assign_other(session):
        ticket = await session.get(Ticket, ticket_id)
        ticket.assignee_id = other["id"]
    set_fields(database_url, other["id"], role="agent")
    db_run(database_url, assign_other)
    assert client.get(path, headers=agent_h).status_code == 403
    assert client.patch(path + "/status", headers=agent_h, json={"status": "in_progress"}).status_code == 403
    assert ticket_id not in [t["id"] for t in client.get("/api/v1/tickets", headers=agent_h).json()["data"]["items"]]
    async def assign(session):
        ticket = await session.get(Ticket, ticket_id)
        ticket.assignee_id = agent["id"]
    db_run(database_url, assign)
    assert client.patch(path + "/status", headers=admin_h, json={"status": "in_progress"}).status_code == 403
    assert client.patch(path + "/status", headers=h, json={"status": "in_progress"}).status_code == 409
    for state in ("in_progress", "resolved"):
        assert client.patch(path + "/status", headers=agent_h, json={"status": state}).status_code == 200
    assert client.patch(path + "/status", headers=h, json={"status": "closed"}).status_code == 200
    assert client.post(path + "/comments", headers=h, json={"content": "关闭"}).status_code == 409
    assert client.get("/api/v1/users", headers=h).status_code == 403
    assert client.get("/api/v1/users", headers=admin_h).status_code == 200
    assert client.post("/api/v1/users", json={}).status_code == 405


def test_management_rechecks_database_role_and_logs(client, database_url):
    admin, email = register(client)
    target, target_email = register(client)
    old_h = login(client, email)  # Token 内仍是 user。
    set_fields(database_url, admin["id"], role="admin")
    path = f"/api/v1/users/{target['id']}"
    assert client.patch(path + "/role", headers=old_h, json={"role": "agent"}).status_code == 200
    target_h = login(client, target_email)
    async def assign(session):
        session.add(Ticket(ticket_no=uuid4().hex, title="客服保护", description="测试", category="other",
            priority="normal", status="resolved", creator_id=admin["id"], assignee_id=target["id"]))
    db_run(database_url, assign)
    for suffix, data in (("role", {"role": "user"}), ("status", {"is_active": False})):
        r = client.patch(path + "/" + suffix, headers=old_h, json=data)
        assert r.status_code == 409 and r.json()["code"] == 30004
    assert client.patch(f"/api/v1/users/{admin['id']}/status", headers=old_h, json={"is_active": False}).json()["code"] == 30003
    assert client.patch(f"/api/v1/users/{admin['id']}/role", headers=old_h, json={"role": "user"}).json()["code"] == 30005
    async def close(session):
        for ticket in await session.scalars(select(Ticket).where(Ticket.assignee_id == target["id"])):
            ticket.status = "closed"
    db_run(database_url, close)
    assert client.patch(path + "/role", headers=old_h, json={"role": "user"}).status_code == 200
    assert client.patch(path + "/status", headers=old_h, json={"is_active": False}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=target_h).status_code == 403
    async def check_logs(session):
        return list(await session.scalars(select(UserAdminLog).where(UserAdminLog.target_user_id == target["id"]).order_by(UserAdminLog.id)))
    logs = db_run(database_url, check_logs)
    assert [log.action for log in logs] == ["role_changed", "role_changed", "account_disabled"]
    assert all(log.operator_id == admin["id"] for log in logs)
    set_fields(database_url, admin["id"], role="user")
    assert client.get("/api/v1/users", headers=old_h).status_code == 403


def test_init_admin_and_atomic_management(database_url):
    settings = Settings(_env_file=None, database_url=database_url)
    payload = UserRegisterRequest(username="初始管理员", email=f"admin{uuid4().hex}@example.com",
        password=PASSWORD, confirm_password=PASSWORD)
    assert asyncio.run(init_admin(settings, payload)) == "管理员创建成功"
    assert asyncio.run(init_admin(settings, payload)) == "管理员已存在，未修改账号"
    async def rollback_check(session):
        actor = await session.scalar(select(User).where(User.email == str(payload.email)))
        target = await UserService(session).users.add(User(username="回滚", email=f"rollback{uuid4().hex}@example.com",
            role="user", password_hash="!invalid", is_active=True))
        target_id = target.id
        await session.commit()
        def fail_commit(s):
            raise RuntimeError("injected")
        event.listen(session.sync_session, "before_commit", fail_commit)
        with pytest.raises(RuntimeError):
            await UserService(session).manage_user(actor, target_id, role="agent")
        event.remove(session.sync_session, "before_commit", fail_commit)
        assert (await session.get(User, target_id)).role == "user"
        assert await session.scalar(select(func.count()).select_from(UserAdminLog).where(
            UserAdminLog.target_user_id == target_id)) == 0
    # 该用例内部主动 commit，独立运行，不使用 db_run 的外层事务。
    async def exercise():
        engine, factory = create_database(database_url)
        try:
            async with factory() as session:
                await rollback_check(session)
        finally:
            await engine.dispose()
    asyncio.run(exercise())
