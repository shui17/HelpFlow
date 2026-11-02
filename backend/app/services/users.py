from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.models import Ticket, User, UserAdminLog
from app.repositories.users import UserRepository
from app.security import hash_password, verify_password
from practice.stage1_helpflow.exceptions import InvalidUserDataError, UserNotFoundError


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)

    async def create_user(self, username: str, email: str, password: str) -> User:
        username, email = username.strip(), email.strip().lower()
        if not username or not email:
            raise InvalidUserDataError("用户名和邮箱不能为空")
        try:
            async with self.session.begin():
                if await self.users.find_by_email(email) is not None:
                    raise InvalidUserDataError("邮箱已经存在")
                user = await self.users.add(User(
                    username=username, email=email, role="user",
                    password_hash=await hash_password(password), is_active=True,
                ))
            return user
        except IntegrityError as exc:
            if exc.orig.args and exc.orig.args[0] == 1062:
                raise InvalidUserDataError("邮箱已经存在") from None
            raise

    async def get_user(self, user_id: int) -> User:
        user = await self.users.get(user_id)
        if user is None:
            raise UserNotFoundError(f"用户不存在: {user_id}")
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.find_by_email(email.strip().lower())
        if not await verify_password(password, user.password_hash if user else None):
            raise AppError(401, 20001, "邮箱或密码错误")
        if not user.is_active:
            raise AppError(403, 20003, "账号已禁用")
        return user

    async def change_password(self, user_id: int, current_password: str, new_password: str):
        async with self.session.begin():
            user = await self.session.scalar(select(User).where(User.id == user_id).with_for_update())
            if user is None:
                raise UserNotFoundError("用户不存在")
            if not await verify_password(current_password, user.password_hash):
                raise AppError(400, 20004, "当前密码错误")
            user.password_hash = await hash_password(new_password)

    async def list_users(self, **filters):
        return await self.users.list(**filters)

    async def manage_user(self, actor: User, user_id: int, *, role=None, is_active=None):
        if actor.role != "admin":
            raise AppError(403, 40002, "无权执行该操作")
        async with self.session.begin():
            user = await self.session.scalar(select(User).where(User.id == user_id).with_for_update())
            if user is None:
                raise UserNotFoundError("用户不存在")
            if role is not None and (user.role == "admin" or role not in ("user", "agent")):
                raise AppError(400, 30005, "不允许的角色修改")
            if user.id == actor.id and is_active is False:
                raise AppError(400, 30003, "不能禁用当前管理员自己")
            if user.role == "agent" and (role == "user" or is_active is False):
                count = await self.session.scalar(select(func.count()).select_from(Ticket).where(
                    Ticket.assignee_id == user_id, Ticket.status != "closed"))
                if count:
                    raise AppError(409, 30004, "客服仍有未关闭负责工单")
            if role is not None and user.role != role:
                self.session.add(UserAdminLog(target_user_id=user_id, operator_id=actor.id,
                    action="role_changed", old_role=user.role, new_role=role))
                user.role = role
            if is_active is not None and user.is_active != is_active:
                self.session.add(UserAdminLog(target_user_id=user_id, operator_id=actor.id,
                    action="account_enabled" if is_active else "account_disabled",
                    old_is_active=user.is_active, new_is_active=is_active))
                user.is_active = is_active
        return user
