from typing import Annotated
from fastapi import APIRouter, Depends, Path, Query
from app.dependencies import AdminUser, get_user_service
from app.schemas import ApiResponse, PageData, UserResponse, UserRoleUpdate, UserStatusUpdate
from app.services.users import UserService
from practice.stage1_helpflow.enums import UserRole

router = APIRouter(prefix="/users", tags=["users"])
UserServiceDependency = Annotated[UserService, Depends(get_user_service)]
UserId = Annotated[int, Path(gt=0)]


@router.get("", response_model=ApiResponse[PageData[UserResponse]])
async def list_users(admin: AdminUser, service: UserServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    keyword: Annotated[str | None, Query(max_length=255)] = None,
    role: UserRole | None = None, is_active: bool | None = None):
    users, total = await service.list_users(page=page, page_size=page_size,
        keyword=keyword, role=role.value if role else None, is_active=is_active)
    return ApiResponse(data=PageData(items=[UserResponse.model_validate(u) for u in users],
        page=page, page_size=page_size, total=total))


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(user_id: UserId, admin: AdminUser, service: UserServiceDependency):
    return ApiResponse(data=UserResponse.model_validate(await service.get_user(user_id)))


@router.patch("/{user_id}/role", response_model=ApiResponse[UserResponse])
async def update_role(user_id: UserId, payload: UserRoleUpdate, admin: AdminUser, service: UserServiceDependency):
    user = await service.manage_user(admin, user_id, role=payload.role.value)
    return ApiResponse(data=UserResponse.model_validate(user))


@router.patch("/{user_id}/status", response_model=ApiResponse[UserResponse])
async def update_status(user_id: UserId, payload: UserStatusUpdate, admin: AdminUser, service: UserServiceDependency):
    user = await service.manage_user(admin, user_id, is_active=payload.is_active)
    return ApiResponse(data=UserResponse.model_validate(user))
