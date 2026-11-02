from tests.async_memory import AsyncMemoryService, transport_user
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_ticket_service, get_user_service
from app.main import app
from practice.stage1_helpflow.services import TicketService, UserService
from practice.stage1_helpflow.storage import MemoryStorage


def create_test_client() -> TestClient:
    """每次测试都使用全新的内存存储，避免测试之间互相影响。"""

    storage = MemoryStorage()
    app.dependency_overrides[get_current_user] = transport_user
    app.dependency_overrides[get_user_service] = lambda: AsyncMemoryService(UserService(storage))
    app.dependency_overrides[get_ticket_service] = lambda: AsyncMemoryService(TicketService(storage))
    return TestClient(app)


def test_complete_http_flow() -> None:
    client = create_test_client()

    user_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "Finnian",
            "email": "finnian@example.com", "password": "Testpass123", "confirm_password": "Testpass123",
        },
    )
    assert user_response.status_code == 201
    assert user_response.json()["data"]["id"] == 1

    get_user_response = client.get("/api/v1/users/1")
    assert get_user_response.status_code == 200
    assert get_user_response.json()["data"]["email"] == "finnian@example.com"

    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "title": "无法登录",
            "description": "输入正确密码后仍然无法登录",

            "priority": "high",
        },
    )
    assert ticket_response.status_code == 201
    assert ticket_response.json()["data"]["status"] == "open"

    get_ticket_response = client.get("/api/v1/tickets/1")
    assert get_ticket_response.status_code == 200
    assert get_ticket_response.json()["data"]["priority"] == "high"

    status_response = client.patch(
        "/api/v1/tickets/1/status",
        json={"status": "in_progress"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["data"]["status"] == "in_progress"

    comment_response = client.post(
        "/api/v1/tickets/1/comments",
        json={"content": "补充：浏览器显示 401。"},
    )
    assert comment_response.status_code == 201

    comments_response = client.get("/api/v1/tickets/1/comments")
    assert comments_response.status_code == 200
    assert len(comments_response.json()["data"]) == 1

    app.dependency_overrides.clear()


def test_http_error_statuses() -> None:
    client = create_test_client()

    missing_response = client.get("/api/v1/tickets/999")
    assert missing_response.status_code == 404
    assert missing_response.json()["code"] == 40001

    invalid_response = client.post(
        "/api/v1/auth/register",
        json={"username": "", "email": "bad", "password": "Testpass123", "confirm_password": "Testpass123"},
    )
    assert invalid_response.status_code == 422
    assert invalid_response.json()["code"] == 10001

    client.post(
        "/api/v1/auth/register",
        json={"username": "AA", "email": "same@example.com", "password": "Testpass123", "confirm_password": "Testpass123"},
    )
    duplicate_response = client.post(
        "/api/v1/auth/register",
        json={"username": "BB", "email": "same@example.com", "password": "Testpass123", "confirm_password": "Testpass123"},
    )
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["code"] == 30002

    client.post(
        "/api/v1/tickets",
        json={
            "title": "状态码练习",
            "description": "验证工单状态冲突",

        },
    )
    invalid_transition_response = client.patch(
        "/api/v1/tickets/1/status",
        json={"status": "resolved"},
    )
    assert invalid_transition_response.status_code == 409
    assert invalid_transition_response.json()["code"] == 40005

    for ticket_status in ("in_progress", "resolved", "closed"):
        response = client.patch(
            "/api/v1/tickets/1/status",
            json={"status": ticket_status},
        )
        assert response.status_code == 200

    closed_comment_response = client.post(
        "/api/v1/tickets/1/comments",
        json={"content": "关闭后不能回复"},
    )
    assert closed_comment_response.status_code == 409
    assert closed_comment_response.json()["code"] == 40006

    app.dependency_overrides.clear()


def test_ticket_list_filter_and_pagination() -> None:
    client = create_test_client()
    client.post(
        "/api/v1/auth/register",
        json={"username": "列表用户", "email": "list@example.com", "password": "Testpass123", "confirm_password": "Testpass123"},
    )

    priorities = ("low", "high", "normal", "high", "urgent")
    for index, priority in enumerate(priorities, start=1):
        response = client.post(
            "/api/v1/tickets",
            json={
                "title": f"工单 {index}",
                "description": f"第 {index} 张分页测试工单",

                "priority": priority,
            },
        )
        assert response.status_code == 201

    for ticket_id in (2, 4):
        response = client.patch(
            f"/api/v1/tickets/{ticket_id}/status",
            json={"status": "in_progress"},
        )
        assert response.status_code == 200

    first_page = client.get("/api/v1/tickets?page=1&page_size=2")
    assert first_page.status_code == 200
    assert first_page.json()["data"]["total"] == 5
    assert [item["id"] for item in first_page.json()["data"]["items"]] == [
        5,
        4,
    ]

    third_page = client.get("/api/v1/tickets?page=3&page_size=2")
    assert third_page.status_code == 200
    assert [item["id"] for item in third_page.json()["data"]["items"]] == [1]

    empty_page = client.get("/api/v1/tickets?page=4&page_size=2")
    assert empty_page.status_code == 200
    assert empty_page.json()["data"]["items"] == []
    assert empty_page.json()["data"]["total"] == 5

    filtered = client.get(
        "/api/v1/tickets?status=in_progress&priority=high"
    )
    assert filtered.status_code == 200
    assert filtered.json()["data"]["total"] == 2
    assert [item["id"] for item in filtered.json()["data"]["items"]] == [
        4,
        2,
    ]

    invalid_page = client.get("/api/v1/tickets?page=0")
    assert invalid_page.status_code == 422
    assert invalid_page.json()["code"] == 10001

    invalid_status = client.get("/api/v1/tickets?status=unknown")
    assert invalid_status.status_code == 422
    assert invalid_status.json()["code"] == 10001

    app.dependency_overrides.clear()


def test_cors_preflight() -> None:
    client = create_test_client()

    response = client.options(
        "/api/v1/tickets",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )

    app.dependency_overrides.clear()
