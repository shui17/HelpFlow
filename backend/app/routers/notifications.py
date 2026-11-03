from fastapi import APIRouter

from app.db.session import SessionDependency
from app.dependencies import CurrentUser
from app.pagination import BeforeId, EntityId, PageSize
from app.schemas import ApiResponse, NotificationResponse
from app.services.notifications import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=ApiResponse[list[NotificationResponse]])
async def list_notifications(session: SessionDependency, user: CurrentUser,
                             before_id: BeforeId = None, limit: PageSize = 20):
    rows = await NotificationService(session).list(user, before_id=before_id, limit=limit)
    return ApiResponse(data=[NotificationResponse.model_validate(row) for row in rows])


@router.get("/unread-count", response_model=ApiResponse[int])
async def unread_count(session: SessionDependency, user: CurrentUser):
    return ApiResponse(data=await NotificationService(session).unread(user))


@router.patch("/{notification_id}/read", response_model=ApiResponse[NotificationResponse])
async def mark_read(notification_id: EntityId, session: SessionDependency, user: CurrentUser):
    row = await NotificationService(session).mark_read(notification_id, user)
    return ApiResponse(data=NotificationResponse.model_validate(row))
