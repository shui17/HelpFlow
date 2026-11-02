from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def create_database(url: str):
    engine = create_async_engine(url, pool_pre_ping=True, hide_parameters=True)

    @event.listens_for(engine.sync_engine, "connect")
    def set_utc(connection, record):
        cursor = connection.cursor()
        cursor.execute("SET time_zone = '+00:00'")
        cursor.close()

    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        try:
            yield session
        finally:
            if session.in_transaction():
                await session.rollback()


SessionDependency = Annotated[AsyncSession, Depends(get_session)]
