import asyncio

from alembic import context

from app.config import Settings
from app.db.base import Base
from app.db.session import create_database
import app.models  # noqa: F401 -- 注册五表元数据

target_metadata = Base.metadata


def run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online():
    engine, _ = create_database(Settings().database_url.get_secret_value())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(url=Settings().database_url.get_secret_value(),
                      target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_online())
