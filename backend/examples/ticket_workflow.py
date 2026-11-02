from app.domain.enums import TicketPriority, TicketStatus, UserRole
from app.domain.exceptions import HelpFlowError
from .logging_config import configure_logging
from app.in_memory.services import TicketService, UserService
from app.in_memory.storage import MemoryStorage


def main() -> None:
    """运行内存工单业务流程示例。"""

    configure_logging()
    storage = MemoryStorage()
    user_service = UserService(storage)
    ticket_service = TicketService(storage)

    try:
        user = user_service.create_user(
            username="Finnian",
            email="finnian@example.com",
        )

        agent = user_service.create_user(
            username="HelpFlow Agent",
            email="agent@example.com",
            role=UserRole.AGENT,
        )

        ticket = ticket_service.create_ticket(
            title="无法登录 HelpFlow",
            description="输入正确密码后仍然提示登录失败。",
            creator_id=user.id,
            priority=TicketPriority.HIGH,
        )
        print(f"创建工单成功: {ticket}")

#       ticket_service.change_status(ticket.id, TicketStatus.RESOLVED)
        ticket_service.change_status(ticket.id, TicketStatus.IN_PROGRESS)
        comment = ticket_service.add_comment(
            ticket_id=ticket.id,
            author_id=agent.id,
            content="您好，我们正在检查登录问题。",
        )
        print(f"新增回复成功: {comment}")

        ticket_service.change_status(ticket.id, TicketStatus.RESOLVED)
        ticket_service.change_status(ticket.id, TicketStatus.CLOSED)
        print(f"最终工单状态: {ticket.status}")

        # 故意制造一次非法流转，验证业务异常是否生效。
        ticket_service.change_status(ticket.id, TicketStatus.IN_PROGRESS)

#        ticket_service.get_ticket(999)
        
    except HelpFlowError as exc:
        print(f"操作失败: {exc}")



if __name__ == "__main__":
    main()

