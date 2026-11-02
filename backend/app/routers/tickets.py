from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies import CurrentUser, get_ticket_service
from app.schemas import (
    ApiResponse,
    ActivityResponse,
    CommentCreateRequest,
    CommentResponse,
    PageData,
    TicketCreate,
    TicketAssignRequest,
    TicketRead,
    TicketStatusUpdateRequest,
    TicketUpdate,
)
from app.domain.enums import TicketPriority, TicketStatus
from app.services.tickets import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])

TicketServiceDependency = Annotated[TicketService, Depends(get_ticket_service)]
TicketId = Annotated[int, Path(gt=0)]


@router.post(
    "",
    response_model=ApiResponse[TicketRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    payload: TicketCreate,
    service: TicketServiceDependency,
    user: CurrentUser,
) -> ApiResponse[TicketRead]:
    """从 JSON 请求体创建工单。"""

    ticket = await service.create_ticket(
        title=payload.title,
        description=payload.description,
        creator_id=user.id,
        actor=user,
        priority=payload.priority,
    )
    return ApiResponse(data=TicketRead.model_validate(ticket))


@router.get(
    "",
    response_model=ApiResponse[PageData[TicketRead]],
)
async def list_tickets(
    service: TicketServiceDependency,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    ticket_status: Annotated[
        TicketStatus | None,
        Query(alias="status"),
    ] = None,
    priority: Annotated[TicketPriority | None, Query()] = None,
    keyword: Annotated[str | None, Query(max_length=200)] = None,
    sort_order: Annotated[Literal["asc", "desc"], Query()] = "desc",
) -> ApiResponse[PageData[TicketRead]]:
    """通过查询参数筛选并分页查询工单集合。"""

    tickets, total = await service.list_tickets(
        actor=user,
        page=page,
        page_size=page_size,
        status=ticket_status,
        priority=priority,
        keyword=keyword,
        sort_order=sort_order,
    )
    return ApiResponse(
        data=PageData(
            items=[TicketRead.model_validate(ticket) for ticket in tickets],
            page=page,
            page_size=page_size,
            total=total,
        )
    )


@router.get(
    "/{ticket_id}",
    response_model=ApiResponse[TicketRead],
)
async def get_ticket(
    ticket_id: TicketId,
    service: TicketServiceDependency,
    user: CurrentUser,
) -> ApiResponse[TicketRead]:
    """通过 URL 路径参数查询工单。"""

    ticket = await service.get_visible_ticket(ticket_id, user)
    return ApiResponse(data=TicketRead.model_validate(ticket))


@router.patch("/{ticket_id}", response_model=ApiResponse[TicketRead])
async def update_ticket(
    ticket_id: TicketId,
    payload: TicketUpdate,
    service: TicketServiceDependency,
    user: CurrentUser,
) -> ApiResponse[TicketRead]:
    """只传递客户端实际提交的字段，不覆盖被省略的值。"""

    ticket = await service.update_ticket(
        ticket_id, actor=user, **payload.model_dump(exclude_unset=True),
    )
    return ApiResponse(data=TicketRead.model_validate(ticket))


@router.patch(
    "/{ticket_id}/status",
    response_model=ApiResponse[TicketRead],
)
@router.post("/{ticket_id}/status", response_model=ApiResponse[TicketRead])
async def update_ticket_status(
    ticket_id: TicketId,
    payload: TicketStatusUpdateRequest,
    service: TicketServiceDependency,
    user: CurrentUser,
) -> ApiResponse[TicketRead]:
    """局部修改工单状态。"""

    ticket = await service.change_status(ticket_id, payload.status, actor=user)
    return ApiResponse(data=TicketRead.model_validate(ticket))


@router.post("/{ticket_id}/cancel", response_model=ApiResponse[TicketRead])
async def cancel_ticket(ticket_id: TicketId, service: TicketServiceDependency,
                        user: CurrentUser) -> ApiResponse[TicketRead]:
    ticket = await service.cancel_ticket(ticket_id, actor=user)
    return ApiResponse(data=TicketRead.model_validate(ticket))


@router.post("/{ticket_id}/claim", response_model=ApiResponse[TicketRead])
async def claim_ticket(ticket_id: TicketId, service: TicketServiceDependency,
                       user: CurrentUser) -> ApiResponse[TicketRead]:
    ticket = await service.claim_ticket(ticket_id, actor=user)
    return ApiResponse(data=TicketRead.model_validate(ticket))


@router.post("/{ticket_id}/assign", response_model=ApiResponse[TicketRead])
async def assign_ticket(ticket_id: TicketId, payload: TicketAssignRequest,
                        service: TicketServiceDependency, user: CurrentUser) -> ApiResponse[TicketRead]:
    ticket = await service.assign_ticket(ticket_id, payload.assignee_id, actor=user)
    return ApiResponse(data=TicketRead.model_validate(ticket))


@router.get("/{ticket_id}/activities", response_model=ApiResponse[list[ActivityResponse]])
async def list_activities(ticket_id: TicketId, service: TicketServiceDependency,
                          user: CurrentUser) -> ApiResponse[list[ActivityResponse]]:
    activities = await service.list_activities(ticket_id, actor=user)
    return ApiResponse(data=[ActivityResponse.model_validate(row) for row in activities])


@router.post(
    "/{ticket_id}/comments",
    response_model=ApiResponse[CommentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    ticket_id: TicketId,
    payload: CommentCreateRequest,
    service: TicketServiceDependency,
    user: CurrentUser,
) -> ApiResponse[CommentResponse]:
    """给未关闭的工单新增回复。"""

    comment = await service.add_comment(
        ticket_id=ticket_id,
        author_id=user.id,
        actor=user,
        content=payload.content,
    )
    return ApiResponse(data=CommentResponse.model_validate(comment))


@router.get(
    "/{ticket_id}/comments",
    response_model=ApiResponse[list[CommentResponse]],
)
async def list_comments(
    ticket_id: TicketId,
    service: TicketServiceDependency,
    user: CurrentUser,
) -> ApiResponse[list[CommentResponse]]:
    """查询工单的全部回复。"""

    comments = await service.list_comments(ticket_id, actor=user)
    return ApiResponse(
        data=[CommentResponse.model_validate(comment) for comment in comments]
    )
