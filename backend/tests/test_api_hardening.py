from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_current_user, get_user_service
from app.main import create_app
from app.rate_limit import AuthRateLimiter


@pytest.mark.parametrize("path,params", [
    ("/api/v1/tickets", {"page": 10**30}),
    ("/api/v1/users", {"page": 10**30}),
    ("/api/v1/tickets/1/comments", {"limit": 101}),
    ("/api/v1/tickets/1/activities", {"before_id": 2**63}),
    ("/api/v1/tickets", {"assignee_id": 2**63}),
])
def test_boundaries_rejected_before_database(path, params):
    app = create_app(Settings(_env_file=None))
    async def admin():
        return SimpleNamespace(id=1, role="admin")
    app.dependency_overrides[get_current_user] = admin
    with TestClient(app) as client:
        response = client.get(path, params=params)
        assert response.status_code == 422
        assert response.json()["code"] == 10001


def test_limiter_expires_and_keeps_live_keys_under_capacity_pressure():
    now = [0.0]
    limiter = AuthRateLimiter(clock=lambda: now[0], max_keys=2)
    limiter.check([("account", 2), ("ip", 4)], 60)
    limiter.check([("account", 2), ("ip", 4)], 60)
    with pytest.raises(HTTPException) as failure:
        limiter.check([("account", 2), ("other-ip", 4)], 60)
    assert failure.value.status_code == 429
    assert failure.value.headers["Retry-After"] == "60"
    with pytest.raises(HTTPException):
        limiter.check([("new-account", 2)], 60)
    now[0] = 60
    limiter.check([("new-account", 2)], 60)
    assert len(limiter.buckets) == 1


def test_login_and_registration_limits_prevent_service_work():
    settings = Settings(_env_file=None, auth_login_account_limit=2, auth_register_ip_limit=2)
    app = create_app(settings)
    class Service:
        attempts = 0
        async def authenticate(self, *args):
            self.attempts += 1
            raise HTTPException(401, "bad credentials")
        async def create_user(self, **kwargs):
            self.attempts += 1
            raise HTTPException(409, "already exists")
    service = Service()
    app.dependency_overrides[get_user_service] = lambda: service
    with TestClient(app) as client:
        for email in ["Case@example.com", "case@example.com"]:
            assert client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"}).status_code == 401
        blocked = client.post("/api/v1/auth/login", json={"email": "CASE@example.com", "password": "wrong"},
                              headers={"X-Forwarded-For": "1.2.3.4"})
        assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
        payload = {"username": "user", "email": "user@example.com", "password": "Password123", "confirm_password": "Password123"}
        assert client.post("/api/v1/auth/register", json=payload).status_code == 409
        assert client.post("/api/v1/auth/register", json=payload).status_code == 409
        assert client.post("/api/v1/auth/register", json=payload, headers={"X-Forwarded-For": "5.6.7.8"}).status_code == 429
        assert service.attempts == 4
