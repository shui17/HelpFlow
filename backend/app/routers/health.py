from fastapi import APIRouter

from app.schemas import ApiResponse, HealthRead

router = APIRouter(tags=["health"])
legacy_router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[HealthRead])
def health_check() -> ApiResponse[HealthRead]:
    """版本化接口遵循统一响应格式。"""

    return ApiResponse(data=HealthRead())


@legacy_router.get("/health", response_model=HealthRead)
def legacy_health_check() -> HealthRead:
    """保留阶段二的健康检查地址及响应。"""

    return HealthRead()
