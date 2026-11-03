from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.base import utcnow
from app.errors import AppError
from app.models import Notification


async def enqueue(session, *, event_key, recipient_id, ticket_id, message):
    """调用者持有业务事务；唯一约束同时保护重复与并发事件。"""
    try:
        async with session.begin_nested():
            session.add(Notification(event_key=event_key, recipient_id=recipient_id,
                                     ticket_id=ticket_id, message=message))
            await session.flush()
    except IntegrityError as exc:
        if not exc.orig.args or exc.orig.args[0] != 1062:
            raise


class NotificationService:
    def __init__(self, session):
        self.session = session

    async def list(self, actor, *, before_id=None, limit=20):
        query = select(Notification).where(Notification.recipient_id == actor.id)
        if before_id is not None:
            query = query.where(Notification.id < before_id)
        return list(await self.session.scalars(query.order_by(Notification.id.desc()).limit(limit)))

    async def unread(self, actor):
        return await self.session.scalar(select(func.count()).select_from(Notification).where(
            Notification.recipient_id == actor.id, Notification.read_at.is_(None)))

    async def mark_read(self, notification_id, actor):
        async with self.session.begin():
            row = await self.session.scalar(select(Notification).where(
                Notification.id == notification_id, Notification.recipient_id == actor.id).with_for_update())
            if row is None:
                raise AppError(404, 40004, "通知不存在")
            if row.read_at is None:
                # MySQL DATETIME 当前精度为秒；首次响应与后续读取保持一致。
                row.read_at = utcnow().replace(microsecond=0)
        return row
