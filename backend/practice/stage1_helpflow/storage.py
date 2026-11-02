from .models import Comment, Ticket, User


class MemoryStorage:
    """使用字典保存阶段一练习数据。"""

    def __init__(self) -> None:
        self._users: dict[int, User] = {}
        self._tickets: dict[int, Ticket] = {}
        self._comments: dict[int, Comment] = {}
        self._next_user_id = 1
        self._next_ticket_id = 1
        self._next_comment_id = 1

    def next_user_id(self) -> int:
        user_id = self._next_user_id
        self._next_user_id += 1
        return user_id

    def next_ticket_id(self) -> int:
        ticket_id = self._next_ticket_id
        self._next_ticket_id += 1
        return ticket_id

    def next_comment_id(self) -> int:
        comment_id = self._next_comment_id
        self._next_comment_id += 1
        return comment_id

    def add_user(self, user: User) -> None:
        self._users[user.id] = user

    def get_user(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    def find_user_by_email(self, email: str) -> User | None:
        return next(
            (user for user in self._users.values() if user.email == email),
            None,
        )

    def add_ticket(self, ticket: Ticket) -> None:
        self._tickets[ticket.id] = ticket

    def get_ticket(self, ticket_id: int) -> Ticket | None:
        return self._tickets.get(ticket_id)

    def list_tickets(self) -> list[Ticket]:
        """返回当前保存的全部工单。"""

        return list(self._tickets.values())

    def update_ticket(self, ticket: Ticket) -> None:
        self._tickets[ticket.id] = ticket

    def add_comment(self, comment: Comment) -> None:
        self._comments[comment.id] = comment

    def list_comments(self, ticket_id: int) -> list[Comment]:
        return [
            comment
            for comment in self._comments.values()
            if comment.ticket_id == ticket_id
        ]
