from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.dependencies import CurrentUser, get_user_service
from app.schemas import ApiResponse, UserRegisterRequest, UserResponse, LoginRequest, PasswordChangeRequest, TokenResponse
from app.security import create_access_token
from app.rate_limit import check_auth_rate
from app.services.users import UserService

router = APIRouter(prefix="/auth", tags=["auth"])
UserServiceDependency = Annotated[UserService, Depends(get_user_service)]


@router.post(
    "/register",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    payload: UserRegisterRequest,
    service: UserServiceDependency,
    request: Request,
) -> ApiResponse[UserResponse]:
    """注册固定为普通用户，密码经 Argon2 哈希保存。"""

    check_auth_rate(request, "register", str(payload.email))
    user = await service.create_user(username=payload.username, email=str(payload.email), password=payload.password)
    return ApiResponse(data=UserResponse.model_validate(user))


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(payload: LoginRequest, service: UserServiceDependency, request: Request):
    check_auth_rate(request, "login", str(payload.email))
    user = await service.authenticate(str(payload.email), payload.password)
    settings = request.app.state.settings
    return ApiResponse(data=TokenResponse(access_token=create_access_token(user, settings),
        expires_in=settings.jwt_access_token_expire_minutes * 60))


@router.get("/me", response_model=ApiResponse[UserResponse])
async def me(user: CurrentUser):
    return ApiResponse(data=UserResponse.model_validate(user))


@router.patch("/password", response_model=ApiResponse[None])
async def change_password(payload: PasswordChangeRequest, user: CurrentUser, service: UserServiceDependency):
    await service.change_password(user.id, payload.current_password, payload.new_password)
    return ApiResponse(message="密码修改成功，请重新登录", data=None)
