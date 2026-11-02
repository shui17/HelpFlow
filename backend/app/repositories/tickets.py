from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Activity, Comment, Ticket
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

    async def list_activities(self, ticket_id: int) -> list[Activity]:
        rows = await self.session.scalars(select(Activity).where(Activity.ticket_id == ticket_id)
            .order_by(Activity.created_at, Activity.id))
        return list(rows)

    async def add(self, ticket: Ticket) -> Ticket:
        self.session.add(ticket)
        await self.session.flush()
        return ticket

    async def list(self, *, page, page_size, status, priority, keyword, sort_order, actor):
        conditions = []
        if actor.role == "user":
            conditions.append(Ticket.creator_id == actor.id)
        elif actor.role == "agent":
            conditions.append(or_(Ticket.assignee_id == actor.id,
                and_(Ticket.status == "open", Ticket.assignee_id.is_(None))))
        elif actor.role != "admin":
            conditions.append(False)
        if status is not None:
            conditions.append(Ticket.status == status.value)
        if priority is not None:
            conditions.append(Ticket.priority == priority.value)
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

    async def list_comments(self, ticket_id: int) -> list[Comment]:
        rows = await self.session.scalars(
            select(Comment).where(Comment.ticket_id == ticket_id)
            .options(selectinload(Comment.author)).order_by(Comment.created_at, Comment.id)
        )
        return list(rows)

    async def add_comment(self, comment: Comment) -> Comment:
        self.session.add(comment)
        await self.session.flush()
        return comment
