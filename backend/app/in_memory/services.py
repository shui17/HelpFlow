import logging
from dataclasses import replace
from typing import Literal

from app.domain.enums import TicketPriority, TicketStatus, UserRole
from app.domain.exceptions import (
    InvalidStatusTransitionError,
    InvalidTicketDataError,
    InvalidUserDataError,
    TicketNotEditableError,
    TicketNotFoundError,
    UserNotFoundError,
)
from .models import Comment, Ticket, User
from .storage import MemoryStorage
from app.domain.workflow import ALLOWED_STATUS_TRANSITIONS

logger = logging.getLogger(__name__)


class UserService:
    """处理内存用户的业务规则。"""

    def __init__(self, storage: MemoryStorage) -> None:
        self.storage = storage

    def create_user(
        self,
        username: str,
        email: str,
        role: UserRole = UserRole.USER,
    ) -> User:
        cleaned_username = username.strip()
        normalized_email = email.strip().lower()

        if not cleaned_username:
            raise InvalidUserDataError("用户名不能为空")
        if not normalized_email:
            raise InvalidUserDataError("邮箱不能为空")
        if self.storage.find_user_by_email(normalized_email) is not None:
            raise InvalidUserDataError("邮箱已经存在")

        user = User(
            id=self.storage.next_user_id(),
            username=cleaned_username,
            email=normalized_email,
            role=role,
        )
        self.storage.add_user(user)
        logger.info("user_created user_id=%s role=%s", user.id, user.role)
        return user

    def get_user(self, user_id: int) -> User:
        user = self.storage.get_user(user_id)
        if user is None:
            raise UserNotFoundError(f"用户不存在: {user_id}")
        return user


class TicketService:
    """处理工单创建、查询、回复和状态流转。"""

    def __init__(self, storage: MemoryStorage) -> None:
        self.storage = storage

    def create_ticket(
        self,
        title: str,
        description: str,
        creator_id: int,
        priority: TicketPriority = TicketPriority.NORMAL,
    ) -> Ticket:
        self._get_user(creator_id)
        cleaned_title = title.strip()
        cleaned_description = description.strip()

        if not cleaned_title:
            raise InvalidTicketDataError("工单标题不能为空")
        if not cleaned_description:
            raise InvalidTicketDataError("工单描述不能为空")

        ticket = Ticket(
            id=self.storage.next_ticket_id(),
            title=cleaned_title,
            description=cleaned_description,
            creator_id=creator_id,
            priority=priority,
        )
        self.storage.add_ticket(ticket)
        logger.info(
            "ticket_created ticket_id=%s creator_id=%s priority=%s",
            ticket.id,
            ticket.creator_id,
            ticket.priority,
        )
        return ticket

    def get_ticket(self, ticket_id: int) -> Ticket:
        ticket = self.storage.get_ticket(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(f"工单不存在: {ticket_id}")
        return ticket

    def list_tickets(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        status: TicketStatus | None = None,
        priority: TicketPriority | None = None,
        keyword: str | None = None,
        sort_order: Literal["asc", "desc"] = "desc",
    ) -> tuple[list[Ticket], int]:
        """筛选工单，并返回当前页数据和筛选后的总数。"""

        if page < 1:
            raise InvalidTicketDataError("页码必须大于或等于 1")
        if not 1 <= page_size <= 100:
            raise InvalidTicketDataError("每页数量必须在 1 到 100 之间")
        if sort_order not in ("asc", "desc"):
            raise InvalidTicketDataError("排序方向必须是 asc 或 desc")

        tickets = self.storage.list_tickets()

        if status is not None:
            tickets = [ticket for ticket in tickets if ticket.status is status]
        if priority is not None:
            tickets = [
                ticket for ticket in tickets if ticket.priority is priority
            ]

        cleaned_keyword = keyword.strip().casefold() if keyword else ""
        if cleaned_keyword:
            tickets = [
                ticket
                for ticket in tickets
                if cleaned_keyword in ticket.title.casefold()
                or cleaned_keyword == str(ticket.id)
            ]

        tickets.sort(key=lambda ticket: ticket.id, reverse=sort_order == "desc")
        total = len(tickets)
        start = (page - 1) * page_size
        end = start + page_size
        return tickets[start:end], total

    def update_ticket(
        self,
        ticket_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        priority: TicketPriority | None = None,
    ) -> Ticket:
        """验证全部改动后保存副本，防止失败时留下部分修改。"""

        ticket = self.get_ticket(ticket_id)
        if ticket.status is not TicketStatus.OPEN or ticket.assignee_id is not None:
            raise TicketNotEditableError("只有待处理且未分配的工单可以修改")
        if title is None and description is None and priority is None:
            raise InvalidTicketDataError("至少提供一个需要修改的字段")

        cleaned_title = ticket.title if title is None else title.strip()
        cleaned_description = (
            ticket.description if description is None else description.strip()
        )
        if not 1 <= len(cleaned_title) <= 200:
            raise InvalidTicketDataError("工单标题必须为 1 到 200 个字符")
        if not 1 <= len(cleaned_description) <= 5000:
            raise InvalidTicketDataError("工单描述必须为 1 到 5000 个字符")
        if priority is not None and not isinstance(priority, TicketPriority):
            raise InvalidTicketDataError("工单优先级无效")

        updated_ticket = replace(
            ticket,
            title=cleaned_title,
            description=cleaned_description,
            priority=ticket.priority if priority is None else priority,
        )
        self.storage.update_ticket(updated_ticket)
        logger.info("ticket_updated ticket_id=%s", ticket_id)
        return updated_ticket

    def change_status(
        self,
        ticket_id: int,
        new_status: TicketStatus,
    ) -> Ticket:
        ticket = self.get_ticket(ticket_id)
        allowed_statuses = ALLOWED_STATUS_TRANSITIONS[ticket.status]

        if new_status not in allowed_statuses:
            raise InvalidStatusTransitionError(
                f"不能从 {ticket.status} 变更为 {new_status}"
            )

        old_status = ticket.status
        ticket.status = new_status
        self.storage.update_ticket(ticket)
        logger.info(
            "ticket_status_changed ticket_id=%s old_status=%s new_status=%s",
            ticket.id,
            old_status,
            new_status,
        )
        return ticket

    def add_comment(
        self,
        ticket_id: int,
        author_id: int,
        content: str,
    ) -> Comment:
        ticket = self.get_ticket(ticket_id)
        self._get_user(author_id)
        cleaned_content = content.strip()

        if ticket.status is TicketStatus.CLOSED:
            raise InvalidTicketDataError("已关闭工单不能新增回复")
        if not cleaned_content:
            raise InvalidTicketDataError("回复内容不能为空")

        comment = Comment(
            id=self.storage.next_comment_id(),
            ticket_id=ticket_id,
            author_id=author_id,
            content=cleaned_content,
        )
        self.storage.add_comment(comment)
        logger.info(
            "comment_created comment_id=%s ticket_id=%s author_id=%s",
            comment.id,
            comment.ticket_id,
            comment.author_id,
        )
        return comment

    def list_comments(self, ticket_id: int) -> list[Comment]:
        self.get_ticket(ticket_id)
        return self.storage.list_comments(ticket_id)

    def _get_user(self, user_id: int) -> User:
        user = self.storage.get_user(user_id)
        if user is None:
            raise UserNotFoundError(f"用户不存在: {user_id}")
        return user
