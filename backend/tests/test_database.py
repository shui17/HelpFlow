"""真实 MySQL 集成测试；只接受显式指定的独立测试库。"""
import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db.session import create_database
from app.main import create_app
from app.models import Comment, Ticket, User
from app.services.users import UserService
from app.domain.exceptions import InvalidUserDataError

ROOT = Path(__file__).resolve().parents[1]
TEST_URL = os.getenv("HELPFLOW_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="需要 HELPFLOW_TEST_DATABASE_URL 独立 MySQL 测试库")


@pytest.fixture(scope="module")
def database_url():
    if not TEST_URL:
        pytest.skip("需要 HELPFLOW_TEST_DATABASE_URL 独立 MySQL 测试库")
    url = make_url(TEST_URL)
    if url.drivername != "mysql+asyncmy" or not (url.database or "").startswith("helpflow_stage5_test"):
        pytest.fail("测试仅允许 mysql+asyncmy 与 helpflow_stage5_test 前缀数据库")
    env = os.environ | {"HELPFLOW_DATABASE_URL": TEST_URL}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True)
    return TEST_URL


def application(url):
    return create_app(Settings(_env_file=None, database_url=url))


def register(client, email=None):
    response = client.post("/api/v1/auth/register", json={
        "username": "数据库用户", "email": email or f"u{uuid4().hex}@example.com",
        "password": "Databasepass123", "confirm_password": "Databasepass123",
    })
    assert response.status_code == 201, response.text
    assert "password_hash" not in response.text
    user = response.json()["data"]
    login = client.post("/api/v1/auth/login", json={"email": user["email"], "password": "Databasepass123"})
    assert login.status_code == 200
    client.headers["Authorization"] = "Bearer " + login.json()["data"]["access_token"]
    return user


def test_persistent_http_flow_and_restart(database_url):
    email = f"u{uuid4().hex}@example.com"
    with TestClient(application(database_url)) as client:
        user = register(client, email)
        duplicate = client.post("/api/v1/auth/register", json={"username": "重复", "email": email, "password": "Databasepass123", "confirm_password": "Databasepass123"})
        assert duplicate.status_code == 409
        created = client.post("/api/v1/tickets", json={
            "title": "持久化 % _ " + uuid4().hex, "description": "数据库测试",
        })
        assert created.status_code == 201, created.text
        ticket = created.json()["data"]
        ticket_id = ticket["id"]
        assert ticket["created_at"].endswith("Z")
        changed = client.patch(f"/api/v1/tickets/{ticket_id}", json={"title": "修改 " + ticket["title"]})
        assert changed.status_code == 200, changed.text
        matches = client.get("/api/v1/tickets", params={"keyword": ticket["title"], "page_size": 1}).json()["data"]
        assert matches["total"] == 1 and matches["items"][0]["id"] == ticket_id
        empty_page = client.get("/api/v1/tickets", params={"keyword": ticket["title"], "page": 999}).json()["data"]
        assert empty_page["items"] == [] and empty_page["total"] == 1
        missing = client.post("/api/v1/tickets", json={"title": "失败", "description": "失败", "creator_id": 9223372036854775807})
        assert missing.status_code == 422
        invalid = client.patch(f"/api/v1/tickets/{ticket_id}/status", json={"status": "closed"})
        assert invalid.status_code == 409
        comment = client.post(f"/api/v1/tickets/{ticket_id}/comments", json={"content": "回复"})
        assert comment.status_code == 201, comment.text
        assert client.patch(f"/api/v1/tickets/{ticket_id}", json={"title": "再次修改"}).status_code == 200
        headers = dict(client.headers)
    with TestClient(application(database_url)) as restarted:
        restarted.headers.update(headers)
        assert restarted.get("/api/v1/auth/me").json()["data"]["email"] == email
        assert restarted.get(f"/api/v1/tickets/{ticket_id}").json()["data"]["status"] == "open"
        assert len(restarted.get(f"/api/v1/tickets/{ticket_id}/comments").json()["data"]) == 1


def test_rollback_after_flush_and_concurrent_sessions(database_url):
    async def exercise():
        engine, factory = create_database(database_url)
        email = f"rollback{uuid4().hex}@example.com"
        try:
            async with factory() as session:
                def fail_commit(sync_session):
                    raise RuntimeError("injected commit failure")
                event.listen(session.sync_session, "before_commit", fail_commit)
                with pytest.raises(RuntimeError, match="injected"):
                    await UserService(session).create_user("回滚用户", email, "Databasepass123")
                assert not session.in_transaction()
            async with factory() as check:
                assert await check.scalar(select(func.count()).select_from(User).where(User.email == email)) == 0

            shared_email = f"race{uuid4().hex}@example.com"
            identities = []
            async def register_racer():
                async with factory() as session:
                    identities.append(session)
                    try:
                        await UserService(session).create_user("并发用户", shared_email, "Databasepass123")
                        return "created"
                    except InvalidUserDataError:
                        assert not session.in_transaction()
                        return "duplicate"
            assert sorted(await asyncio.gather(register_racer(), register_racer())) == ["created", "duplicate"]
            assert identities[0] is not identities[1]
            assert engine.pool.checkedout() == 0
        finally:
            await engine.dispose()
    asyncio.run(exercise())


def test_migration_field_roundtrip_and_metadata(database_url):
    # 迁移回退使用全新的独立库，避免现有内部备注被有损降级为公开回复。
    original_url = make_url(database_url)
    migration_name = 'helpflow_stage5_test_migration_' + uuid4().hex[:12]
    database_url = original_url.set(database=migration_name).render_as_string(hide_password=False)
    async def schema(create):
        engine, _ = create_database(original_url.render_as_string(hide_password=False))
        try:
            async with engine.begin() as connection:
                await connection.execute(text(
                    f"CREATE DATABASE `{migration_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                    if create else f"DROP DATABASE `{migration_name}`"))
        finally:
            await engine.dispose()
    asyncio.run(schema(True))
    env = os.environ | {"HELPFLOW_DATABASE_URL": database_url}
    def migrate(*args):
        subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, check=True)
    async def columns():
        engine, _ = create_database(database_url)
        try:
            async with engine.connect() as connection:
                return await connection.run_sync(lambda conn: {c["name"] for c in inspect(conn).get_columns("tickets")})
        finally:
            await engine.dispose()
    try:
        migrate("upgrade", "head")
        try:
            migrate("downgrade", "001_five_tables")
            assert "updated_at" not in asyncio.run(columns())
        finally:
            migrate("upgrade", "head")
        assert "updated_at" in asyncio.run(columns())
        migrate("check")
    finally:
        asyncio.run(schema(False))
