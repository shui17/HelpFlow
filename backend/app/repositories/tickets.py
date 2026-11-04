from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Activity, Comment, Ticket, TicketSLA, User
from app.services.sla import filter_condition
from app.db.base import utcnow


class TicketRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, ticket_id: int, *, lock: bool = False) -> Ticket | None:
        query = select(Ticket).where(Ticket.id == ticket_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.session.scalar(query)

    async def claim(self, ticket_id: int, agent_id: int) -> bool:
        result = await self.session.execute(update(Ticket).where(
            Ticket.id == ticket_id, Ticket.status == "open", Ticket.assignee_id.is_(None),
        ).values(assignee_id=agent_id, assigned_at=utcnow(), updated_at=utcnow())
          .execution_options(synchronize_session=False))
        return result.rowcount == 1

    async def list_activities(self, ticket_id: int, *, before_id=None, limit=50) -> list[Activity]:
        query = select(Activity).where(Activity.ticket_id == ticket_id)
        if before_id is not None:
            query = query.where(Activity.id < before_id)
        rows = await self.session.scalars(query.order_by(Activity.id.desc()).limit(limit))
        return list(reversed(list(rows)))

    async def add(self, ticket: Ticket) -> Ticket:
        self.session.add(ticket)
        await self.session.flush()
        return ticket

    @staticmethod
    def visible_conditions(actor):
        conditions = []
        if actor.role == "user":
            conditions.append(Ticket.creator_id == actor.id)
        elif actor.role == "agent":
            conditions.append(or_(Ticket.assignee_id == actor.id,
                and_(Ticket.status == "open", Ticket.assignee_id.is_(None))))
        elif actor.role != "admin":
            conditions.append(False)
        return conditions

    async def list(self, *, page, page_size, status, priority, keyword, sort_order, actor,
                   category=None, scope=None, assignee_id=None, unassigned=False, sla_filter=None):
        conditions = self.visible_conditions(actor)
        if sla_filter:
            conditions.append(Ticket.id.in_(select(TicketSLA.ticket_id).where(filter_condition(sla_filter))))
        if scope == "mine":
            conditions.append(Ticket.assignee_id == actor.id)
        if scope == "unassigned":
            conditions.extend([Ticket.status == "open", Ticket.assignee_id.is_(None)])
        if unassigned:
            conditions.append(Ticket.assignee_id.is_(None))
        if assignee_id is not None:
            conditions.append(Ticket.assignee_id == assignee_id)
        if status is not None:
            conditions.append(Ticket.status == status.value)
        if priority is not None:
            conditions.append(Ticket.priority == priority.value)
        if category is not None:
            conditions.append(Ticket.category == category.value)
        cleaned = keyword.strip() if keyword else ""
        if cleaned:
            title_match = Ticket.title.icontains(cleaned, autoescape=True)
            valid_id = cleaned.isascii() and cleaned.isdecimal() and len(cleaned) <= 19
            number = int(cleaned) if valid_id else 0
            if 0 < number <= 9223372036854775807 and str(number) == cleaned:
                conditions.append(or_(title_match, Ticket.id == number))
            else:
                conditions.append(title_match)
        total = await self.session.scalar(select(func.count()).select_from(Ticket).where(*conditions))
        order = Ticket.id.asc() if sort_order == "asc" else Ticket.id.desc()
        rows = await self.session.scalars(
            select(Ticket).where(*conditions).order_by(order)
            .offset((page - 1) * page_size).limit(page_size)
        )
        return list(rows), total

    async def list_comments(self, ticket_id: int, *, before_id=None, limit=50, visibility="public") -> list[Comment]:
        query = select(Comment).where(Comment.ticket_id == ticket_id, Comment.visibility == visibility)
        if before_id is not None:
            query = query.where(Comment.id < before_id)
        rows = await self.session.scalars(query.options(selectinload(Comment.author))
            .order_by(Comment.id.desc()).limit(limit))
        return list(reversed(list(rows)))

    async def summary(self, actor):
        # 同一请求会话中的一致性读取；只向客户端返回聚合值和五条最近工单。
        conditions = self.visible_conditions(actor)
        owned = conditions + ([Ticket.assignee_id == actor.id] if actor.role == "agent" else [])
        grouped = await self.session.execute(select(Ticket.status, func.count())
            .where(*owned).group_by(Ticket.status))
        counts = dict(grouped.all())
        now = utcnow()
        for kind in ("due_soon", "overdue"):
            counts[kind] = await self.session.scalar(select(func.count()).select_from(Ticket)
                .where(*owned, Ticket.id.in_(select(TicketSLA.ticket_id).where(filter_condition(kind, now)))))
        counts["unassigned"] = await self.session.scalar(select(func.count()).select_from(Ticket)
            .where(*conditions, Ticket.status == "open", Ticket.assignee_id.is_(None)))
        if actor.role == "admin":
            users = await self.session.execute(select(User.role, func.count())
                .where(User.is_active.is_(True)).group_by(User.role))
            active = dict(users.all())
            counts.update(users=active.get("user", 0), agents=active.get("agent", 0))
        recent = await self.session.scalars(select(Ticket).where(*owned).order_by(Ticket.id.desc()).limit(5))
        return {"counts": counts, "recent": list(recent)}

    async def add_comment(self, comment: Comment) -> Comment:
        self.session.add(comment)
        await self.session.flush()
        return comment
