"""仅供接口回归测试：把同步内存 Service 适配到异步路由。"""


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
            # 早期内存练习没有分类；分类契约在真实 MySQL 测试中验证。
            kwargs.pop("category", None)
            if name == "list_tickets":
                for field in ("scope", "assignee_id", "unassigned"):
                    kwargs.pop(field, None)
            before_id = kwargs.pop("before_id", None)
            limit = kwargs.pop("limit", 50)
            if name == "get_visible_ticket":
                args = args[:1]
            result = attribute(*args, **kwargs)
            if name == "list_comments":
                result = [row for row in result if before_id is None or row.id < before_id][-limit:]
            return result

        return invoke


from fastapi import Request
from types import SimpleNamespace

async def transport_user(request: Request):
    # 早期 HTTP 测试只验证传输层。真实认证与归属测试见 test_security。
    return SimpleNamespace(id=1, role="admin" if "/users/" in request.url.path else "user")
