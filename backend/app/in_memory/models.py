from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.enums import TicketPriority, TicketStatus, UserRole


@dataclass
class User:
    """HelpFlow 用户"""

    id: int
    username: str
    email: str
    role: UserRole = UserRole.USER
    is_active: bool = True


@dataclass
class Ticket:
    """HelpFlow 工单"""

    id: int
    title: str
    description: str
    creator_id: int
    priority: TicketPriority = TicketPriority.NORMAL
    status: TicketStatus = TicketStatus.OPEN
    assignee_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Comment:
    """工单中的一条文字回复"""

    id: int
    ticket_id: int
    author_id: int
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
