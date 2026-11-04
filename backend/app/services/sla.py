"""MySQL 是事实源。所有写操作要求调用者已锁定工单并持有事务。"""
from datetime import timedelta

from sqlalchemy import and_, or_, select

from app.db.base import utcnow
from app.models import SLAEvent, SLARule, TicketSLA, User
from app.services.notifications import enqueue


def describe(row, now=None):
    if row is None:
        return None
    now = now or utcnow()
    if row.escalated_at or (row.first_response_at and row.first_response_at > row.due_at):
        state = "overdue"
    elif row.first_response_at:
        state = "on_time"
    elif row.terminated_at:
        state = "terminated"
    elif now > row.due_at:
        state = "overdue"
    elif now >= row.due_at - timedelta(seconds=row.warning_seconds):
        state = "due_soon"
    else:
        state = "waiting"
    return dict(version=row.version, priority=row.priority, response_seconds=row.response_seconds,
                warning_seconds=row.warning_seconds, due_at=row.due_at,
                first_response_at=row.first_response_at, escalated_at=row.escalated_at, state=state)


def pending():
    return and_(TicketSLA.first_response_at.is_(None), TicketSLA.terminated_at.is_(None),
                TicketSLA.escalated_at.is_(None))


def filter_condition(kind, now=None):
    # TIMESTAMPADD 在数据库中使用每张工单自己的规则快照。
    from sqlalchemy import func, text
    now = now or utcnow()
    if kind == "overdue":
        return or_(TicketSLA.escalated_at.is_not(None), TicketSLA.first_response_at > TicketSLA.due_at,
                   and_(pending(), TicketSLA.due_at < now))
    return and_(pending(), TicketSLA.due_at >= now,
                TicketSLA.due_at <= func.timestampadd(text("SECOND"), TicketSLA.warning_seconds, now))


async def snapshot(session, ticket):
    rule = await session.scalar(select(SLARule).where(SLARule.priority == ticket.priority)
                                .order_by(SLARule.version.desc()).limit(1))
    if rule is None:
        raise RuntimeError("缺少 SLA 规则，请先执行数据库迁移")
    now = utcnow()
    row = TicketSLA(ticket_id=ticket.id, version=rule.version, priority=rule.priority,
                    response_seconds=rule.response_seconds, warning_seconds=rule.warning_seconds,
                    started_at=now, due_at=now + timedelta(seconds=rule.response_seconds))
    ticket.sla_snapshot = row
    session.add(row)
    return row


async def locked_snapshot(session, ticket):
    return await session.scalar(select(TicketSLA).where(TicketSLA.ticket_id == ticket.id)
                                .with_for_update().execution_options(populate_existing=True))


async def record_event(session, ticket, row, kind, now):
    exists = await session.scalar(select(SLAEvent.id).where(SLAEvent.ticket_id == ticket.id,
                                    SLAEvent.version == row.version, SLAEvent.kind == kind).with_for_update())
    if exists:
        return False
    session.add(SLAEvent(ticket_id=ticket.id, version=row.version, kind=kind,
                         occurred_at=now, due_at=row.due_at))
    if kind == "overdue":
        row.escalated_at = now
    recipients = set(await session.scalars(select(User.id).where(User.is_active.is_(True),
        or_(User.role == "admin", and_(User.role == "agent", User.id == ticket.assignee_id)))))
    for recipient in sorted(recipients):
        await enqueue(session, event_key=f"sla:{ticket.id}:{row.version}:{kind}",
                      recipient_id=recipient, ticket_id=ticket.id,
                      message="工单首次响应已超时，请及时处理" if kind == "overdue" else "工单首次响应即将超时，请及时处理")
    await session.flush()
    return True


async def respond(session, ticket, now):
    row = await locked_snapshot(session, ticket)
    if row and row.first_response_at is None and row.terminated_at is None:
        row.first_response_at = now
        if now > row.due_at:
            await record_event(session, ticket, row, "overdue", now)


async def terminate(session, ticket):
    row = await locked_snapshot(session, ticket)
    if row and row.first_response_at is None and row.terminated_at is None:
        row.terminated_at = utcnow()


async def inspect_locked(session, ticket, now):
    row = await locked_snapshot(session, ticket)
    if not row:
        return False, None, 0
    if ticket.status == "closed":
        await terminate(session, ticket)
        return False, row, 0
    if row.first_response_at or row.terminated_at or row.escalated_at:
        return False, row, 0
    kind = ("overdue" if now > row.due_at else
            "due_soon" if now >= row.due_at - timedelta(seconds=row.warning_seconds) else None)
    created = await record_event(session, ticket, row, kind, now) if kind else False
    return kind != "overdue", row, int(created)
