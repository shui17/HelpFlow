"""Agent任务、确认版本与业务写入去重；检查点单独持久化。"""
from datetime import datetime
from sqlalchemy import String, Integer, Text, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UTCMicroDateTime, utcnow


class AgentTask(Base):
    __tablename__ = 'agent_tasks'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    ticket_id: Mapped[int] = mapped_column(ForeignKey('tickets.id'))
    request_id: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(20))
    instruction: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default='pending')
    fingerprint: Mapped[str] = mapped_column(String(64))
    generation: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(UTCMicroDateTime())
    rounds: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    proposal_version: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default='')
    content_hash: Mapped[str] = mapped_column(String(64), default='')
    sources: Mapped[list] = mapped_column(JSON, default=list)
    trace: Mapped[list] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(UTCMicroDateTime())
    result_id: Mapped[int | None] = mapped_column(ForeignKey('ticket_comments.id'))
    error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(UTCMicroDateTime(), default=utcnow)
    __table_args__ = (UniqueConstraint('user_id','request_id',name='uq_agent_user_request'),
                     Index('ix_agent_user_ticket_created','user_id','ticket_id','created_at'))


class AgentExecution(Base):
    __tablename__ = 'agent_executions'
    task_id: Mapped[str] = mapped_column(ForeignKey('agent_tasks.id'), primary_key=True)
    proposal_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    comment_id: Mapped[int] = mapped_column(ForeignKey('ticket_comments.id'))
    created_at: Mapped[datetime] = mapped_column(UTCMicroDateTime(), default=utcnow)
