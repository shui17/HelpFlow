"""绑定工单的只读工具；工具不接受模型指定身份或其他工单。"""
from sqlalchemy import select
from app.models import Comment
from app.services.agent_tasks import scope
from app.services.knowledge import retrieve


class AgentTools:
    def __init__(self, tasks, provider, task, user_id):
        self.tasks, self.provider, self.task, self.user_id = tasks, provider, task, user_id

    async def call(self, name, args):
        async with self.tasks.factory() as session:
            async with session.begin():
                _, ticket = await scope(session, self.user_id, self.task['ticket_id'])
                if name == 'get_ticket':
                    return {key: getattr(ticket, key) for key in
                            ('id', 'title', 'description', 'status', 'priority', 'category', 'assignee_id')}
                if name == 'read_records':
                    query = select(Comment).where(Comment.ticket_id == ticket.id)
                    if self.task['mode'] == 'public_reply':
                        query = query.where(Comment.visibility == 'public')
                    if args.before_id:
                        query = query.where(Comment.id < args.before_id)
                    rows = (await session.scalars(query.order_by(Comment.id.desc()).limit(11))).all()
                    page = rows[:10]
                    return {'records': [{'id': row.id, 'author_id': row.author_id,
                            'visibility': row.visibility, 'content': row.content} for row in reversed(page)],
                            'has_more': len(rows) > 10,
                            'next_before_id': page[-1].id if len(rows) > 10 else None,
                            'coverage': ('仅覆盖本页，尚有更早记录，可用next_before_id继续读取' if len(rows) > 10
                                else '已到最早记录；结合此前读取的页面确定覆盖范围' if args.before_id
                                else '本页已覆盖当前模式允许读取的全部沟通记录；空列表表示暂无此类记录')}
            # 检索会发起网络调用，不能占用上面的业务锁。
            return {'sources': await retrieve(session, self.provider, args.query, self.tasks.settings)}
