from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models import Activity, Comment, Ticket, User
from app.repositories.tickets import TicketRepository
from app.repositories.users import UserRepository
from app.errors import AppError
from app.domain.enums import TicketPriority, TicketStatus
from app.domain.exceptions import (
    InvalidStatusTransitionError, InvalidTicketDataError, TicketNotEditableError,
    TicketNotFoundError, UserNotFoundError,
)
from app.domain.workflow import ALLOWED_STATUS_TRANSITIONS


class TicketService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tickets = TicketRepository(session)
        self.users = UserRepository(session)

    def _activity(self, ticket, actor, action, **values):
        self.session.add(Activity(ticket_id=ticket.id, operator_id=actor.id,
                                  action=action, **values))

    async def _enabled_agent(self, user_id):
        # 与用户管理共用用户行锁，防止分配与禁用/降级交错。
        user = await self.session.scalar(select(User).where(User.id == user_id)
            .with_for_update().execution_options(populate_existing=True))
        if user is None or user.role != "agent" or not user.is_active:
            raise AppError(409, 40005, "目标账号必须是启用的客服")
        return user

    async def _user(self, user_id):
        if await self.users.get(user_id) is None:
            raise UserNotFoundError(f"用户不存在: {user_id}")

    async def get_ticket(self, ticket_id: int, *, lock: bool = False) -> Ticket:
        ticket = await self.tickets.get(ticket_id, lock=lock)
        if ticket is None:
            raise TicketNotFoundError(f"工单不存在: {ticket_id}")
        return ticket

    def check_view(self, ticket: Ticket, actor):
        allowed = actor.role == "admin" or (actor.role == "user" and ticket.creator_id == actor.id)
        allowed |= actor.role == "agent" and (ticket.assignee_id == actor.id or
            (ticket.status == "open" and ticket.assignee_id is None))
        if not allowed:
            raise AppError(403, 40002, "无权查看或操作该工单")

    def check_owner(self, ticket: Ticket, actor):
        if actor.role != "user" or ticket.creator_id != actor.id:
            raise AppError(403, 40002, "无权查看或操作该工单")

    async def get_visible_ticket(self, ticket_id, actor):
        ticket = await self.get_ticket(ticket_id)
        self.check_view(ticket, actor)
        return ticket

    async def create_ticket(self, title, description, creator_id, priority=TicketPriority.NORMAL, *, actor):
        if actor.role != "user" or creator_id != actor.id:
            raise AppError(403, 40002, "只有普通用户可以创建自己的工单")
        async with self.session.begin():
            await self._user(creator_id)
            if not title.strip() or not description.strip():
                raise InvalidTicketDataError("工单标题和描述不能为空")
            ticket = await self.tickets.add(Ticket(
                ticket_no=uuid4().hex, title=title.strip(), description=description.strip(),
                creator_id=creator_id, priority=priority.value, category="other", status="open",
            ))
            self._activity(ticket, actor, "created", new_status="open")
        return ticket

    async def list_tickets(self, *, actor, page=1, page_size=10, status=None, priority=None,
                           keyword=None, sort_order="desc"):
        if page < 1 or not 1 <= page_size <= 100 or sort_order not in ("asc", "desc"):
            raise InvalidTicketDataError("分页或排序参数无效")
        return await self.tickets.list(page=page, page_size=page_size, status=status,
            priority=priority, keyword=keyword, sort_order=sort_order, actor=actor)

    async def update_ticket(self, ticket_id, *, actor, title=None, description=None, priority=None):
        async with self.session.begin():
            ticket = await self.get_ticket(ticket_id, lock=True)
            self.check_owner(ticket, actor)
            if ticket.status != "open" or ticket.assignee_id is not None:
                raise TicketNotEditableError("只有待处理且未分配的工单可以修改")
            if title is None and description is None and priority is None:
                raise InvalidTicketDataError("至少提供一个需要修改的字段")
            new_title = ticket.title if title is None else title.strip()
            new_description = ticket.description if description is None else description.strip()
            if not 1 <= len(new_title) <= 200 or not 1 <= len(new_description) <= 5000:
                raise InvalidTicketDataError("工单标题或描述长度无效")
            ticket.title, ticket.description = new_title, new_description
            if priority is not None:
                ticket.priority = priority.value
            self._activity(ticket, actor, "updated")
        return ticket

    async def cancel_ticket(self, ticket_id, *, actor):
        async with self.session.begin():
            ticket = await self.get_ticket(ticket_id, lock=True)
            self.check_owner(ticket, actor)
            if ticket.status != "open" or ticket.assignee_id is not None:
                raise AppError(409, 40005, "只有待处理且未分配的工单可以撤销")
            ticket.status, ticket.closed_at = "closed", utcnow()
            self._activity(ticket, actor, "cancelled", old_status="open", new_status="closed")
        return ticket

    async def claim_ticket(self, ticket_id, *, actor):
        if actor.role != "agent":
            raise AppError(403, 40002, "只有客服可以领取工单")
        async with self.session.begin():
            await self._enabled_agent(actor.id)
            if not await self.tickets.claim(ticket_id, actor.id):
                await self.get_ticket(ticket_id)
                raise AppError(409, 40005, "工单已被领取或不再处于待领取状态")
            ticket = await self.get_ticket(ticket_id, lock=True)
            self._activity(ticket, actor, "claimed", new_assignee_id=actor.id)
        return ticket

    async def assign_ticket(self, ticket_id, assignee_id, *, actor):
        if actor.role != "admin":
            raise AppError(403, 40002, "只有管理员可以分配工单")
        async with self.session.begin():
            await self._enabled_agent(assignee_id)
            ticket = await self.get_ticket(ticket_id, lock=True)
            if ticket.status == "closed":
                raise AppError(409, 40005, "已关闭工单不能分配")
            if ticket.assignee_id == assignee_id:
                raise AppError(409, 40005, "该客服已经是工单负责人")
            previous = ticket.assignee_id
            ticket.assignee_id, ticket.assigned_at = assignee_id, utcnow()
            self._activity(ticket, actor, "assigned" if previous is None else "reassigned",
                           old_assignee_id=previous, new_assignee_id=assignee_id)
        return ticket

    async def change_status(self, ticket_id, new_status: TicketStatus, *, actor):
        async with self.session.begin():
            ticket = await self.get_ticket(ticket_id, lock=True)
            if actor.role == "agent" and ticket.assignee_id == actor.id:
                allowed = (ticket.status, new_status.value) in (("open", "in_progress"), ("in_progress", "resolved"))
            elif actor.role == "user" and ticket.creator_id == actor.id:
                allowed = (ticket.status, new_status.value) in (("resolved", "in_progress"), ("resolved", "closed"))
            else:
                raise AppError(403, 40002, "无权查看或操作该工单")
            if not allowed:
                raise AppError(409, 40005, "非法工单状态流转")
            if new_status not in ALLOWED_STATUS_TRANSITIONS[TicketStatus(ticket.status)]:
                raise InvalidStatusTransitionError(f"不能从 {ticket.status} 变更为 {new_status}")
            previous = ticket.status
            ticket.status = new_status.value
            ticket.closed_at = utcnow() if new_status == TicketStatus.CLOSED else None
            action = ("closed" if new_status == TicketStatus.CLOSED else
                      "reopened" if previous == "resolved" else "status_changed")
            self._activity(ticket, actor, action, old_status=previous, new_status=new_status.value)
        return ticket

    async def add_comment(self, ticket_id, author_id, content, *, actor):
        async with self.session.begin():
            ticket = await self.get_ticket(ticket_id, lock=True)
            if author_id != actor.id or not ((actor.role == "user" and ticket.creator_id == actor.id) or
                                            (actor.role == "agent" and ticket.assignee_id == actor.id)):
                raise AppError(403, 40002, "无权查看或操作该工单")
            await self._user(author_id)
            if ticket.status == "closed":
                raise InvalidTicketDataError("已关闭工单不能新增回复")
            if not content.strip():
                raise InvalidTicketDataError("回复内容不能为空")
            comment = await self.tickets.add_comment(Comment(
                ticket_id=ticket_id, author_id=author_id, content=content.strip()
            ))
            ticket.updated_at = utcnow()
        return comment

    async def list_comments(self, ticket_id, *, actor):
        await self.get_visible_ticket(ticket_id, actor)
        return await self.tickets.list_comments(ticket_id)

    async def list_activities(self, ticket_id, *, actor):
        await self.get_visible_ticket(ticket_id, actor)
        return await self.tickets.list_activities(ticket_id)
