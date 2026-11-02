"""仅供早期接口回归测试：把同步练习 Service 适配到异步路由。"""


class AsyncMemoryService:
    def __init__(self, service):
        self.service = service

    def __getattr__(self, name):
        attribute = getattr(self.service, "get_ticket" if name == "get_visible_ticket" else name)
        if not callable(attribute):
            return attribute

        async def invoke(*args, **kwargs):
            kwargs.pop("actor", None)
            kwargs.pop("password", None)
            if name == "get_visible_ticket":
                args = args[:1]
            return attribute(*args, **kwargs)

        return invoke


from fastapi import Request
from types import SimpleNamespace

async def transport_user(request: Request):
    # 早期 HTTP 测试只验证传输层。真实认证与归属测试见 test_stage6_security。
    return SimpleNamespace(id=1, role="admin" if "/users/" in request.url.path else "user")
