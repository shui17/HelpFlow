import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.db.session import create_database
from app.exception_handlers import register_exception_handlers
from app.middleware import register_request_logging
from app.routers import auth, health, tickets, users


def create_app(settings: Settings | None = None) -> FastAPI:
    """集中装配应用，测试可以传入独立配置。"""

    settings = settings if settings is not None else Settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            settings.signing_key()
            yield
        finally:
            await application.state.engine.dispose()

    application = FastAPI(
        title=settings.app_name,
        description="HelpFlow 客服工单、身份认证与权限管理",
        version="0.6.0",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.engine, application.state.session_factory = create_database(
        settings.database_url.get_secret_value()
    )

    register_request_logging(application)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["X-Process-Time"],
    )

    register_exception_handlers(application)
    application.include_router(auth.router, prefix="/api/v1")
    application.include_router(users.router, prefix="/api/v1")
    application.include_router(tickets.router, prefix="/api/v1")
    application.include_router(health.router, prefix="/api/v1")
    application.include_router(health.legacy_router)

    @application.get("/")
    def root() -> dict[str, str]:
        return {"message": "欢迎使用 HelpFlow 客服工单系统"}

    return application


app = create_app()
