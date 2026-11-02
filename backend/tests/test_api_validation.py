from tests.async_memory import AsyncMemoryService, transport_user
import logging

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_current_user, get_ticket_service, get_user_service
from app.main import create_app
from app.schemas import TicketRead
from app.domain.exceptions import InvalidTicketDataError
from app.in_memory.services import TicketService, UserService
from app.in_memory.storage import MemoryStorage


@pytest.fixture
def client():
    """每个用例独立创建应用和存储，不污染默认 app 的依赖。"""

    storage = MemoryStorage()
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_current_user] = transport_user
    app.dependency_overrides[get_user_service] = lambda: AsyncMemoryService(UserService(storage))
    app.dependency_overrides[get_ticket_service] = lambda: AsyncMemoryService(TicketService(storage))
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def register(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "学习用户", "email": "learner@example.com", "password": "Testpass123", "confirm_password": "Testpass123"},
    )
    assert response.status_code == 201
    return response.json()["data"]


def create_ticket(client: TestClient, **changes) -> dict:
    payload = {
        "title": "无法登录",
        "description": "输入密码后仍然无法登录",

        "priority": "high",
    }
    payload.update(changes)
    response = client.post("/api/v1/tickets", json=payload)
    assert response.status_code == 201
    return response.json()["data"]


def test_register_normalizes_input_and_rejects_duplicate(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "  Finnian  ", "email": "  Learner@EXAMPLE.COM  ", "password": "Testpass123", "confirm_password": "Testpass123"},
    )
    assert response.status_code == 201
    assert response.json()["data"] == {
        "id": 1,
        "username": "Finnian",
        "email": "learner@example.com",
        "role": "user",
        "is_active": True,
    }
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"username": "另一位用户", "email": "learner@example.com", "password": "Testpass123", "confirm_password": "Testpass123"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == 30002
    assert client.get("/api/v1/users/1").status_code == 200


@pytest.mark.parametrize("fields", [
    {"username": "   "},
    {"email": "not-an-email", "password": "Testpass123", "confirm_password": "Testpass123"},
    {"role": "admin"},
    {"password": "do-not-echo-this-value"},
    {"is_active": False},
])
def test_registration_rejects_invalid_or_internal_fields(client, fields):
    payload = {"username": "用户", "email": "learner@example.com", "password": "Testpass123", "confirm_password": "Testpass123"} | fields
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == 10001
    assert "do-not-echo-this-value" not in response.text
    assert all(set(error) == {"location", "message", "type"}
               for error in response.json()["data"])
    # 校验失败不能写入用户。
    assert client.get("/api/v1/users/1").status_code == 404


@pytest.mark.parametrize("role", ["admin", "agent"])
def test_legacy_user_creation_cannot_bypass_fixed_role(client, role):
    response = client.post(
        "/api/v1/users",
        json={"username": "用户", "email": "learner@example.com", "password": "Testpass123", "confirm_password": "Testpass123", "role": role},
    )
    assert response.status_code == 405


def test_health_and_request_timing(client):
    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/api/v1/health")
    assert response.json() == {
        "code": 0, "message": "success", "data": {"status": "ok"},
    }
    assert float(response.headers["X-Process-Time"]) >= 0
    assert client.get("/").json() == {"message": "欢迎使用 HelpFlow 客服工单系统"}


def test_partial_update_preserves_omitted_fields(client):
    register(client)
    original = create_ticket(client)
    response = client.patch("/api/v1/tickets/1", json={"title": "  修改后的标题  "})
    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated == original | {"title": "修改后的标题"}
    response = client.patch(
        "/api/v1/tickets/1",
        json={"description": "补充新的排查信息", "priority": "urgent"},
    )
    assert response.status_code == 200
    assert response.json()["data"] == updated | {
        "description": "补充新的排查信息", "priority": "urgent",
    }
    assert client.get("/api/v1/tickets/1").json()["data"] == response.json()["data"]


@pytest.mark.parametrize("changes", [
    {},
    {"title": None},
    {"description": None},
    {"priority": None},
    {"title": "  "},
    {"description": "\t\n"},
    {"priority": "invalid"},
    {"title": "x" * 201},
    {"description": "x" * 5001},
    {"creator_id": 2},
    {"status": "closed"},
    {"assignee_id": 2},
    {"title": "这部分有效", "description": " "},
])
def test_invalid_update_does_not_modify_ticket(client, changes):
    register(client)
    original = create_ticket(client)
    response = client.patch("/api/v1/tickets/1", json=changes)
    assert response.status_code == 422
    assert response.json()["code"] == 10001
    assert client.get("/api/v1/tickets/1").json()["data"] == original


@pytest.mark.parametrize("states", [
    ["in_progress"],
    ["in_progress", "resolved"],
    ["in_progress", "resolved", "closed"],
])
def test_started_or_closed_ticket_cannot_be_edited(client, states):
    register(client)
    create_ticket(client)
    for state in states:
        assert client.patch(
            "/api/v1/tickets/1/status", json={"status": state},
        ).status_code == 200
    response = client.patch("/api/v1/tickets/1", json={"title": "不允许的修改"})
    assert response.status_code == 409
    assert response.json()["code"] == 40003
    assert client.get("/api/v1/tickets/1").json()["data"]["title"] == "无法登录"


def test_assigned_ticket_cannot_be_edited(client):
    register(client)
    create_ticket(client)
    service = client.app.dependency_overrides[get_ticket_service]()
    service.service.get_ticket(1).assignee_id = 2
    response = client.patch("/api/v1/tickets/1", json={"priority": "urgent"})
    assert response.status_code == 409
    assert response.json()["code"] == 40003
    assert service.service.get_ticket(1).priority.value == "high"


def test_missing_ticket_update_returns_404(client):
    response = client.patch("/api/v1/tickets/999", json={"title": "新标题"})
    assert response.status_code == 404
    assert response.json()["code"] == 40001


def test_service_validates_all_changes_before_saving():
    storage = MemoryStorage()
    UserService(storage).create_user("用户", "learner@example.com")
    service = TicketService(storage)
    original = service.create_ticket("旧标题", "旧描述", 1)
    with pytest.raises(InvalidTicketDataError):
        service.update_ticket(1, title="新的有效标题", description="  ")
    assert storage.get_ticket(1) is original
    assert original.title == "旧标题"
    assert original.description == "旧描述"


def test_search_sort_filter_and_total_before_pagination(client):
    register(client)
    create_ticket(client, title="登录 Login 故障")
    create_ticket(client, title="支付异常")
    create_ticket(client, title="LOGIN 验证失败")
    create_ticket(client, title="login 低优先级", priority="low")
    create_ticket(client, title="login 处理中")
    client.patch("/api/v1/tickets/5/status", json={"status": "in_progress"})
    params = {
        "keyword": "  LoGiN  ", "priority": "high", "status": "open",
        "sort_order": "asc", "page": 2, "page_size": 1,
    }
    data = client.get("/api/v1/tickets", params=params).json()["data"]
    assert data["total"] == 2
    assert [item["id"] for item in data["items"]] == [3]
    params["sort_order"] = "desc"
    assert client.get("/api/v1/tickets", params=params).json()["data"]["items"][0]["id"] == 1
    params["page"] = 3
    data = client.get("/api/v1/tickets", params=params).json()["data"]
    assert data["items"] == []
    assert data["total"] == 2
    by_id = client.get("/api/v1/tickets", params={"keyword": "2"}).json()["data"]
    assert [item["id"] for item in by_id["items"]] == [2]
    blank = client.get("/api/v1/tickets", params={"keyword": "  "}).json()["data"]
    assert blank["total"] == 5
    assert [item["id"] for item in blank["items"]] == [5, 4, 3, 2, 1]
    assert client.get("/api/v1/tickets", params={"keyword": "未匹配"}).json()["data"]["total"] == 0


@pytest.mark.parametrize("params", [
    {"sort_order": "sideways"},
    {"keyword": "x" * 201},
    {"page_size": 101},
])
def test_invalid_list_parameters(client, params):
    response = client.get("/api/v1/tickets", params=params)
    assert response.status_code == 422
    assert response.json()["code"] == 10001


@pytest.mark.parametrize("changes", [
    {"title": "  "}, {"description": "  "}, {"status": "closed"},
])
def test_create_ticket_validates_before_service(client, changes):
    register(client)
    payload = {"title": "标题", "description": "描述", } | changes
    response = client.post("/api/v1/tickets", json=payload)
    assert response.status_code == 422
    assert client.get("/api/v1/tickets").json()["data"]["total"] == 0


def test_response_schema_does_not_serialize_internal_attributes():
    storage = MemoryStorage()
    UserService(storage).create_user("用户", "learner@example.com")
    ticket = TicketService(storage).create_ticket("标题", "描述", 1)
    ticket.internal_note = "private"
    assert "internal_note" not in TicketRead.model_validate(ticket).model_dump()


def test_http_exceptions_are_unified_and_preserve_headers(client):
    @client.app.get("/test-http-error")
    def raise_http_error():
        raise HTTPException(401, "需要认证", headers={"WWW-Authenticate": "Bearer"})

    missing = client.get("/unknown-url")
    assert missing.status_code == 404
    assert set(missing.json()) == {"code", "message", "data"}
    wrong_method = client.post("/api/v1/health")
    assert wrong_method.status_code == 405
    assert "GET" in wrong_method.headers["allow"]
    unauthorized = client.get("/test-http-error")
    assert unauthorized.status_code == 401
    assert unauthorized.json() == {"code": 10401, "message": "需要认证", "data": None}
    assert unauthorized.headers["www-authenticate"] == "Bearer"


def test_unexpected_error_is_logged_but_response_is_safe(client, caplog):
    @client.app.get("/test-unexpected-error")
    def raise_unexpected_error():
        raise RuntimeError("internal-connection-details")

    with caplog.at_level(logging.INFO):
        response = client.get("/test-unexpected-error")
    assert response.status_code == 500
    assert response.json() == {"code": 90001, "message": "系统暂时不可用", "data": None}
    assert "internal-connection-details" not in response.text
    assert "internal-connection-details" in caplog.text
    assert "status=500" in caplog.text


def test_request_log_excludes_query_body_and_authentication(client, caplog):
    with caplog.at_level(logging.INFO, logger="helpflow.requests"):
        client.get("/api/v1/health?token=query-secret", headers={
            "Authorization": "Bearer header-secret",
        })
        client.post("/api/v1/auth/register", json={
            "username": "日志用户", "email": "body-secret@example.com", "password": "Testpass123", "confirm_password": "Testpass123",
        })
    request_logs = "\n".join(
        record.getMessage() for record in caplog.records if record.name == "helpflow.requests"
    )
    assert "method=GET path=/api/v1/health status=200 duration_ms=" in request_logs
    assert "query-secret" not in request_logs
    assert "header-secret" not in request_logs
    assert "body-secret" not in request_logs


def test_settings_env_file_environment_priority_and_cors(tmp_path, monkeypatch):
    monkeypatch.delenv("HELPFLOW_CORS_ORIGINS", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        'HELPFLOW_APP_NAME=FromFile\n'
        'HELPFLOW_CORS_ORIGINS=["http://localhost:4173"]\n', encoding="utf-8",
    )
    monkeypatch.setenv("HELPFLOW_APP_NAME", "FromEnvironment")
    settings = Settings(_env_file=env_file)
    app = create_app(settings)
    assert app.title == "FromEnvironment"
    with TestClient(app) as client:
        allowed = client.options("/api/v1/tickets", headers={
            "Origin": "http://localhost:4173", "Access-Control-Request-Method": "PATCH",
        })
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:4173"
        denied = client.options("/api/v1/tickets", headers={
            "Origin": "http://untrusted.example", "Access-Control-Request-Method": "PATCH",
        })
        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers


def test_openapi_declares_new_models_and_routes(client):
    schema = client.get("/openapi.json").json()
    assert {"TicketCreate", "TicketUpdate", "TicketRead"} <= schema["components"]["schemas"].keys()
    assert "patch" in schema["paths"]["/api/v1/tickets/{ticket_id}"]
    assert "post" in schema["paths"]["/api/v1/auth/register"]
