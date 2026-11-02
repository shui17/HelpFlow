"""在 backend 目录执行 python -m scripts.init_admin，密码通过隐藏输入读取。"""
import argparse
import asyncio
from getpass import getpass

from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db.session import create_database
from app.models import User
from app.repositories.users import UserRepository
from app.schemas import UserRegisterRequest
from app.security import hash_password


async def init_admin(settings: Settings, payload: UserRegisterRequest) -> str:
    engine, factory = create_database(settings.database_url.get_secret_value())
    try:
        async with factory() as session:
            async with session.begin():
                existing = await UserRepository(session).find_by_email(str(payload.email).lower())
                if existing:
                    if existing.role != "admin":
                        raise ValueError("邮箱属于现有非管理员账号，拒绝自动提权")
                    return "管理员已存在，未修改账号"
                session.add(User(username=payload.username, email=str(payload.email).lower(),
                    role="admin", is_active=True, password_hash=await hash_password(payload.password)))
        return "管理员创建成功"
    except IntegrityError:
        raise ValueError("账号已存在，请重新运行检查") from None
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    try:
        payload = UserRegisterRequest(username=args.username, email=args.email,
            password=getpass("管理员密码: "), confirm_password=getpass("确认密码: "))
        print(asyncio.run(init_admin(Settings(), payload)))
    except ValueError:
        # Pydantic 原始异常可能包含密码输入，不直接打印。
        parser.exit(1, "初始化失败：请检查用户名、邮箱、密码规则或既有账号角色。\n")


if __name__ == "__main__":
    main()
