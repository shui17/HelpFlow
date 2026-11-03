import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.errors import AppError

from app.domain.exceptions import (
    InvalidStatusTransitionError,
    InvalidTicketDataError,
    InvalidUserDataError,
    TicketNotEditableError,
    TicketNotFoundError,
    UserNotFoundError,
)

logger = logging.getLogger(__name__)


def error_response(
    *,
    http_status: int,
    code: int,
    message: str,
    data: object | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """生成统一结构的 HTTP 错误响应。"""

    return JSONResponse(
        status_code=http_status,
        content=jsonable_encoder({"code": code, "message": message, "data": data}),
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """统一处理业务、请求校验、HTTP 及未预期异常。"""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(http_status=exc.status, code=exc.code, message=exc.message,
                              headers={"WWW-Authenticate": "Bearer"} if exc.status == 401 else None)

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        # 不记录原始 SQL、参数或驱动异常，避免连接信息及用户数据进入日志。
        original = getattr(exc, "orig", None)
        args = getattr(original, "args", ())
        db_code = args[0] if args and isinstance(args[0], int) else None
        logger.error("database_error type=%s db_code=%s request_id=%s", type(exc).__name__,
                     db_code, getattr(request.state, "request_id", "unknown"))
        return error_response(http_status=500, code=90001, message="系统暂时不可用")

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        return error_response(
            http_status=exc.status_code,
            code=10000 + exc.status_code,
            message=exc.detail if isinstance(exc.detail, str) else "HTTP 请求失败",
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.error("unexpected_error", exc_info=(type(exc), exc, exc.__traceback__))
        return error_response(
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=90001,
            message="系统暂时不可用",
        )

    @app.exception_handler(TicketNotEditableError)
    async def handle_ticket_not_editable(
        request: Request,
        exc: TicketNotEditableError,
    ) -> JSONResponse:
        return error_response(
            http_status=status.HTTP_409_CONFLICT,
            code=40003,
            message=str(exc),
        )

    @app.exception_handler(UserNotFoundError)
    async def handle_user_not_found(
        request: Request,
        exc: UserNotFoundError,
    ) -> JSONResponse:
        return error_response(
            http_status=status.HTTP_404_NOT_FOUND,
            code=30001,
            message=str(exc),
        )

    @app.exception_handler(TicketNotFoundError)
    async def handle_ticket_not_found(
        request: Request,
        exc: TicketNotFoundError,
    ) -> JSONResponse:
        return error_response(
            http_status=status.HTTP_404_NOT_FOUND,
            code=40001,
            message=str(exc),
        )

    @app.exception_handler(InvalidUserDataError)
    async def handle_invalid_user_data(
        request: Request,
        exc: InvalidUserDataError,
    ) -> JSONResponse:
        is_duplicate_email = "邮箱已经存在" in str(exc)
        return error_response(
            http_status=(
                status.HTTP_409_CONFLICT
                if is_duplicate_email
                else status.HTTP_400_BAD_REQUEST
            ),
            code=30002 if is_duplicate_email else 10002,
            message=str(exc),
        )

    @app.exception_handler(InvalidStatusTransitionError)
    async def handle_invalid_status_transition(
        request: Request,
        exc: InvalidStatusTransitionError,
    ) -> JSONResponse:
        return error_response(
            http_status=status.HTTP_409_CONFLICT,
            code=40005,
            message=str(exc),
        )

    @app.exception_handler(InvalidTicketDataError)
    async def handle_invalid_ticket_data(
        request: Request,
        exc: InvalidTicketDataError,
    ) -> JSONResponse:
        is_closed_ticket = "已关闭工单" in str(exc)
        return error_response(
            http_status=(
                status.HTTP_409_CONFLICT
                if is_closed_ticket
                else status.HTTP_400_BAD_REQUEST
            ),
            code=40006 if is_closed_ticket else 10003,
            message=str(exc),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        safe_errors = [
            {
                "location": list(error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return error_response(
            http_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=10001,
            message="请求参数校验失败",
            data=safe_errors,
        )
