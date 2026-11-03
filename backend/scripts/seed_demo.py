"""在专用 helpflow_demo* 数据库中创建演示账号和工单；不重置既有账号。"""
import argparse
import asyncio
from getpass import getpass
import os
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db.session import create_database
from app.domain.enums import TicketPriority, TicketStatus
from app.models import Ticket, User
from app.schemas import UserRegisterRequest
from app.services.tickets import TicketService
from app.services.users import UserService
from scripts.init_admin import init_admin

ACCOUNTS = (
    ('演示管理员', 'admin@demo.example.com', 'admin'),
    ('演示用户', 'user@demo.example.com', 'user'),
    ('演示客服一', 'agent1@demo.example.com', 'agent'),
    ('演示客服二', 'agent2@demo.example.com', 'agent'),
)


def identity(user):
    return SimpleNamespace(id=user.id, role=user.role)


async def seed(settings, password):
    database = make_url(settings.database_url.get_secret_value()).database or ''
    if not database.startswith('helpflow_demo'):
        raise ValueError('演示初始化仅允许 helpflow_demo 前缀的专用数据库')
    payload = UserRegisterRequest(username=ACCOUNTS[0][0], email=ACCOUNTS[0][1],
        password=password, confirm_password=password)
    await init_admin(settings, payload)
    engine, factory = create_database(settings.database_url.get_secret_value())
    try:
        async with factory() as session:
            admin = await session.scalar(select(User).where(User.email == ACCOUNTS[0][1]))
            admin = identity(admin)
            await session.rollback()
            users = {'admin': admin}
            for name, email, role in ACCOUNTS[1:]:
                user = await session.scalar(select(User).where(User.email == email))
                user = identity(user) if user is not None else None
                await session.rollback()
                if user is None:
                    user = await UserService(session).create_user(name, email, password)
                    if role == 'agent':
                        user = await UserService(session).manage_user(admin, user.id, role=role)
                elif user.role != role:
                    raise ValueError('既有演示账号角色不同，拒绝覆盖，请使用新的演示库')
                users[email.split('@')[0]] = identity(user)
            for title, target in [('演示：账号登录问题', 'open'), ('演示：支付结果未更新', 'in_progress'), ('演示：产品使用咨询', 'resolved')]:
                existing = await session.scalar(select(Ticket).where(Ticket.creator_id == users['user'].id, Ticket.title == title))
                await session.rollback()
                if existing is not None:
                    continue
                service = TicketService(session)
                ticket = await service.create_ticket(title, '这是专用演示工单，可用于本地流程演练。',
                    users['user'].id, TicketPriority.HIGH, actor=users['user'])
                if target != 'open':
                    await service.claim_ticket(ticket.id, actor=users['agent1'])
                    await service.change_status(ticket.id, TicketStatus.IN_PROGRESS, actor=users['agent1'])
                    await service.add_comment(ticket.id, users['agent1'].id, '正在检查问题，请补充发生时间。', actor=users['agent1'])
                if target == 'resolved':
                    await service.change_status(ticket.id, TicketStatus.RESOLVED, actor=users['agent1'])
        return [(email, role) for _, email, role in ACCOUNTS]
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--password-env', help='从指定环境变量读取演示密码；省略时隐藏输入')
    args = parser.parse_args()
    password = os.environ.get(args.password_env, '') if args.password_env else getpass('演示账号共用密码: ')
    try:
        accounts = asyncio.run(seed(Settings(), password))
    except ValueError:
        parser.exit(1, '初始化失败：请检查专用演示库、账号角色及密码规则；不会重置既有账号。\n')
    for email, role in accounts:
        print(f'{role}: {email}')
    print('演示数据准备完成；既有账号密码和工单不会重置。')


if __name__ == '__main__':
    main()
