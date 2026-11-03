import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

logger = logging.getLogger("helpflow.requests")


def register_request_logging(app: FastAPI) -> None:
    """记录请求概要，不记录请求体、查询串或认证信息。"""

    @app.middleware("http")
    async def log_request(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request.state.request_id = uuid4().hex
        started_at = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request.state.request_id
            response.headers["X-Process-Time"] = f"{perf_counter() - started_at:.6f}"
            return response
        finally:
            logger.info(
                "method=%s path=%s status=%s duration_ms=%.3f request_id=%s",
                request.method,
                request.url.path,
                status_code,
                (perf_counter() - started_at) * 1000,
                request.state.request_id,
            )
