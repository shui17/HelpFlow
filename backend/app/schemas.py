from datetime import datetime
from typing import Generic, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.domain.enums import (
    TicketPriority,
    TicketStatus,
    UserRole,
)

DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    """HelpFlow 的统一 JSON 响应外壳。"""

    code: int = 0
    message: str = "success"
    data: DataT


class PageData(BaseModel, Generic[DataT]):
    """列表接口使用的统一分页结构。"""

    items: list[DataT]
    page: int
    page_size: int
    total: int


class RequestModel(BaseModel):
    """输入模型拒绝未知字段，并在长度校验前清理首尾空白。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UserRegisterRequest(RequestModel):
    """公开注册仅创建普通用户，密码保留原始空白。"""

    username: str = Field(min_length=2, max_length=30)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=64)
    confirm_password: str = Field(min_length=8, max_length=64)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    @field_validator("username", "email", mode="before")
    @classmethod
    def strip_identity(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def password_strength(cls, value):
        if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
            raise ValueError("密码至少包含一个字母和一个数字")
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> Self:
        if self.password != self.confirm_password:
            raise ValueError("两次密码不一致")
        return self


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=64)

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value):
        return value.strip() if isinstance(value, str) else value


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=8, max_length=64)
    confirm_password: str = Field(min_length=8, max_length=64)

    @model_validator(mode="after")
    def validate_password(self) -> Self:
        UserRegisterRequest.password_strength(self.new_password)
        if self.new_password != self.confirm_password:
            raise ValueError("两次密码不一致")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserRoleUpdate(RequestModel):
    role: Literal[UserRole.USER, UserRole.AGENT]


class UserStatusUpdate(RequestModel):
    is_active: bool = Field(strict=True)


class UserResponse(BaseModel):
    """可以安全返回给客户端的用户字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: UserRole
    is_active: bool


class TicketCreate(RequestModel):
    """创建工单时由客户端发送的 JSON。"""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    priority: TicketPriority = TicketPriority.NORMAL


class TicketUpdate(RequestModel):
    """省略字段表示保持原值；显式 null 和空修改均不合法。"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    priority: TicketPriority | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要修改的字段")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("修改字段不能为 null,请省略无需修改的字段")
        return self


class TicketStatusUpdateRequest(RequestModel):
    """局部更新工单状态时发送的 JSON。"""

    status: TicketStatus


class TicketAssignRequest(RequestModel):
    assignee_id: int = Field(gt=0)


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    action: Literal["created", "updated", "cancelled", "claimed", "assigned", "reassigned",
                    "status_changed", "reopened", "closed"]
    operator_id: int
    old_status: TicketStatus | None
    new_status: TicketStatus | None
    old_assignee_id: int | None
    new_assignee_id: int | None
    description: str | None
    created_at: datetime


class TicketRead(BaseModel):
    """工单的 HTTP 响应字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    creator_id: int
    priority: TicketPriority
    status: TicketStatus
    assignee_id: int | None
    created_at: datetime
    updated_at: datetime | None = None
    assigned_at: datetime | None = None
    closed_at: datetime | None = None


# 保留接口模型的兼容别名，两个名称指向同一个模型。
TicketCreateRequest = TicketCreate
TicketResponse = TicketRead


class HealthRead(BaseModel):
    status: Literal["ok"] = "ok"


class CommentCreateRequest(RequestModel):
    """新增工单回复时发送的 JSON。"""

    content: str = Field(min_length=1, max_length=2000)


class CommentResponse(BaseModel):
    """工单回复的 HTTP 响应字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    author_id: int
    content: str
    created_at: datetime
