from enum import StrEnum


class UserRole(StrEnum):
    """系统支持的用户角色。"""

    USER = "user"
    AGENT = "agent"
    ADMIN = "admin"


class TicketStatus(StrEnum):
    """工单在处理流程中的状态。"""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    """工单的处理优先级。"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
