"""业务、通知与 SLA 映射；SLA 摘要按批预加载，其余关系禁止隐式 IO。"""

from datetime import datetime
from app.models.knowledge import KnowledgeDocument, KnowledgeVersion, KnowledgeChunk

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, UTCMicroDateTime, utcnow

TABLE_OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}


class CreatedMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, server_default=text("CURRENT_TIMESTAMP"))


class UpdatedMixin:
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))


class User(CreatedMixin, UpdatedMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    created_tickets: Mapped[list["Ticket"]] = relationship(back_populates="creator", foreign_keys="Ticket.creator_id", lazy="raise")
    assigned_tickets: Mapped[list["Ticket"]] = relationship(back_populates="assignee", foreign_keys="Ticket.assignee_id", lazy="raise")
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("role IN ('user', 'agent', 'admin')", name="ck_users_role"),
        CheckConstraint("is_active IN (0, 1)", name="ck_users_active"),
        Index("ix_users_role", "role"), Index("ix_users_active", "is_active"), TABLE_OPTIONS,
    )


class Ticket(CreatedMixin, UpdatedMixin, Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_no: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(20), default="normal", server_default="normal")
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    creator: Mapped[User] = relationship(back_populates="created_tickets", foreign_keys=[creator_id], lazy="raise")
    assignee: Mapped[User | None] = relationship(back_populates="assigned_tickets", foreign_keys=[assignee_id], lazy="raise")
    comments: Mapped[list["Comment"]] = relationship(back_populates="ticket", lazy="raise")
    activities: Mapped[list["Activity"]] = relationship(back_populates="ticket", lazy="raise")
    sla_snapshot: Mapped["TicketSLA | None"] = relationship(lazy="selectin", uselist=False)

    @property
    def sla(self):
        from app.services.sla import describe
        return describe(self.sla_snapshot)

    __table_args__ = (
        UniqueConstraint("ticket_no", name="uq_tickets_no"),
        CheckConstraint("category IN ('account', 'product', 'payment', 'technical', 'other')", name="ck_tickets_category"),
        CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_tickets_priority"),
        CheckConstraint("status IN ('open', 'in_progress', 'resolved', 'closed')", name="ck_tickets_status"),
        Index("ix_tickets_creator_created", "creator_id", "created_at", "id"),
        Index("ix_tickets_assignee_status_created", "assignee_id", "status", "created_at", "id"),
        Index("ix_tickets_status", "status"), Index("ix_tickets_priority", "priority"),
        Index("ix_tickets_category", "category"), Index("ix_tickets_created", "created_at"), TABLE_OPTIONS,
    )


class Comment(CreatedMixin, Base):
    __tablename__ = "ticket_comments"
    created_at: Mapped[datetime] = mapped_column(UTCMicroDateTime(), default=utcnow,
                                                server_default=text("CURRENT_TIMESTAMP(6)"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(20), default="public", server_default="public")
    ticket: Mapped[Ticket] = relationship(back_populates="comments", lazy="raise")
    author: Mapped[User] = relationship(lazy="raise")
    __table_args__ = (
        CheckConstraint("visibility IN ('public', 'internal')", name="ck_comments_visibility"),
        Index("ix_comments_visibility_id", "ticket_id", "visibility", "id"),
        CheckConstraint("CHAR_LENGTH(TRIM(content)) BETWEEN 1 AND 2000", name="ck_comments_content"),
        Index("ix_comments_ticket_created", "ticket_id", "created_at", "id"),
        Index("ix_comments_author", "author_id"), TABLE_OPTIONS,
    )


class Activity(CreatedMixin, Base):
    __tablename__ = "ticket_activity_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    action: Mapped[str] = mapped_column(String(30))
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    old_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str | None] = mapped_column(String(20))
    old_assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    new_assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    description: Mapped[str | None] = mapped_column(String(500))
    ticket: Mapped[Ticket] = relationship(back_populates="activities", lazy="raise")
    operator: Mapped[User] = relationship(foreign_keys=[operator_id], lazy="raise")
    old_assignee: Mapped[User | None] = relationship(foreign_keys=[old_assignee_id], lazy="raise")
    new_assignee: Mapped[User | None] = relationship(foreign_keys=[new_assignee_id], lazy="raise")
    __table_args__ = (
        CheckConstraint("action IN ('created', 'updated', 'cancelled', 'claimed', 'assigned', 'reassigned', 'transferred', 'status_changed', 'reopened', 'closed')", name="ck_activity_action"),
        CheckConstraint("old_status IN ('open', 'in_progress', 'resolved', 'closed')", name="ck_activity_old_status"),
        CheckConstraint("new_status IN ('open', 'in_progress', 'resolved', 'closed')", name="ck_activity_new_status"),
        Index("ix_activity_ticket_created", "ticket_id", "created_at", "id"),
        Index("ix_activity_operator", "operator_id"), Index("ix_activity_old_assignee", "old_assignee_id"),
        Index("ix_activity_new_assignee", "new_assignee_id"), Index("ix_activity_action", "action"), TABLE_OPTIONS,
    )


class UserAdminLog(CreatedMixin, Base):
    __tablename__ = "user_admin_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(30))
    old_role: Mapped[str | None] = mapped_column(String(20))
    new_role: Mapped[str | None] = mapped_column(String(20))
    old_is_active: Mapped[bool | None] = mapped_column(Boolean)
    new_is_active: Mapped[bool | None] = mapped_column(Boolean)
    target: Mapped[User] = relationship(foreign_keys=[target_user_id], lazy="raise")
    operator: Mapped[User] = relationship(foreign_keys=[operator_id], lazy="raise")
    __table_args__ = (
        CheckConstraint("action IN ('role_changed', 'account_enabled', 'account_disabled')", name="ck_admin_action"),
        CheckConstraint("old_role IN ('user', 'agent', 'admin')", name="ck_admin_old_role"),
        CheckConstraint("new_role IN ('user', 'agent', 'admin')", name="ck_admin_new_role"),
        CheckConstraint("old_is_active IN (0, 1)", name="ck_admin_old_active"),
        CheckConstraint("new_is_active IN (0, 1)", name="ck_admin_new_active"),
        Index("ix_admin_target_created", "target_user_id", "created_at", "id"),
        Index("ix_admin_operator", "operator_id"), Index("ix_admin_action", "action"), TABLE_OPTIONS,
    )


class Notification(CreatedMixin, Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    event_key: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(String(200))
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    __table_args__ = (
        UniqueConstraint("event_key", "recipient_id", name="uq_notifications_event_recipient"),
        Index("ix_notifications_recipient_id", "recipient_id", "id"),
        Index("ix_notifications_recipient_read", "recipient_id", "read_at", "id"),
        Index("ix_notifications_ticket", "ticket_id"), TABLE_OPTIONS,
    )


class SLARule(Base):
    __tablename__ = "sla_rules"
    priority: Mapped[str] = mapped_column(String(20), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    response_seconds: Mapped[int] = mapped_column(Integer)
    warning_seconds: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        CheckConstraint("response_seconds > 0 AND warning_seconds >= 0 AND warning_seconds < response_seconds", name="ck_sla_rule_duration"),
        CheckConstraint("version > 0", name="ck_sla_rule_version"),
        CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_sla_rule_priority"), TABLE_OPTIONS,
    )


class TicketSLA(Base):
    __tablename__ = "ticket_sla"
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    priority: Mapped[str] = mapped_column(String(20))
    response_seconds: Mapped[int] = mapped_column(Integer)
    warning_seconds: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(UTCMicroDateTime())
    due_at: Mapped[datetime] = mapped_column(UTCMicroDateTime())
    first_response_at: Mapped[datetime | None] = mapped_column(UTCMicroDateTime())
    terminated_at: Mapped[datetime | None] = mapped_column(UTCMicroDateTime())
    escalated_at: Mapped[datetime | None] = mapped_column(UTCMicroDateTime())
    __table_args__ = (
        Index("ix_sla_pending_due", "first_response_at", "terminated_at", "escalated_at", "due_at", "ticket_id"), TABLE_OPTIONS,
    )


class SLAEvent(Base):
    __tablename__ = "sla_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    occurred_at: Mapped[datetime] = mapped_column(UTCMicroDateTime())
    due_at: Mapped[datetime] = mapped_column(UTCMicroDateTime())
    __table_args__ = (
        UniqueConstraint("ticket_id", "version", "kind", name="uq_sla_event"),
        CheckConstraint("kind IN ('due_soon', 'overdue')", name="ck_sla_event_kind"), TABLE_OPTIONS,
    )
