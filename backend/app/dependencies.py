import hmac
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.session import SessionDependency
from app.errors import AppError, unauthorized
from app.models import User
from app.repositories.users import UserRepository
from app.security import decode_access_token, password_version
from app.services.tickets import TicketService
from app.services.users import UserService

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request, session: SessionDependency,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise unauthorized()
    settings = request.app.state.settings
    claims = decode_access_token(credentials.credentials, settings)
    # 结束身份查询事务，之后业务 Service 可明确开启自己的写事务。
    async with session.begin():
        user = await UserRepository(session).get(int(claims["sub"]))
        if user is None:
            raise unauthorized()
        if not user.is_active:
            raise AppError(403, 20003, "账号已禁用")
        if not hmac.compare_digest(claims["pwdv"], password_version(user.password_hash, settings)):
            raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str):
    async def check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise AppError(403, 40002, "无权执行该操作")
        return user
    return check


AdminUser = Annotated[User, Depends(require_roles("admin"))]


def get_user_service(session: SessionDependency) -> UserService:
    """供 FastAPI Depends 注入用户服务。"""

    return UserService(session)


def get_ticket_service(session: SessionDependency, request: Request) -> TicketService:
    """供 FastAPI Depends 注入工单服务。"""

    return TicketService(session, request.app.state.settings)
