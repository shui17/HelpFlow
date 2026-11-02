from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def find_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def list(self, *, page=1, page_size=10, keyword=None, role=None, is_active=None):
        conditions = []
        if keyword and keyword.strip():
            conditions.append(or_(User.username.icontains(keyword.strip(), autoescape=True),
                                  User.email.icontains(keyword.strip(), autoescape=True)))
        if role is not None:
            conditions.append(User.role == role)
        if is_active is not None:
            conditions.append(User.is_active == is_active)
        total = await self.session.scalar(select(func.count()).select_from(User).where(*conditions))
        rows = await self.session.scalars(select(User).where(*conditions).order_by(User.id)
            .offset((page - 1) * page_size).limit(page_size))
        return list(rows), total
