"""仅为专用测试库准备浏览器测试账号，不读取业务库配置。"""
import asyncio
import os
from sqlalchemy.engine import make_url
from app.config import Settings
from app.db.session import create_database
from app.repositories.users import UserRepository
from app.schemas import UserRegisterRequest
from app.services.users import UserService
from scripts.init_admin import init_admin

async def seed():
    url = os.environ["HELPFLOW_TEST_DATABASE_URL"]
    if not (make_url(url).database or "").startswith("helpflow_stage5_test"):
        raise ValueError("Browser seed requires a dedicated test database")
    settings = Settings(_env_file=None, database_url=url)
    password = os.environ.get("E2E_PASSWORD", "BrowserTest123")
    await init_admin(settings, UserRegisterRequest(username="浏览器管理员", email="browser-admin@example.com",
        password=password, confirm_password=password))
    engine, factory = create_database(url)
    try:
        async with factory() as session:
            admin = await UserRepository(session).find_by_email("browser-admin@example.com")
            await session.commit()
            agent = await UserRepository(session).find_by_email("browser-agent@example.com")
            await session.commit()
            if agent is None:
                agent = await UserService(session).create_user("浏览器客服", "browser-agent@example.com", password)
                await UserService(session).manage_user(admin, agent.id, role="agent")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed())
