"""发布单个优先级的新 SLA 版本；既有快照不改变。"""
import argparse
import asyncio

from sqlalchemy import func, select

from app.config import Settings
from app.db.session import create_database
from app.models import SLARule


async def configure(args):
    if args.seconds <= 0 or not 0 <= args.warning_seconds < args.seconds or args.version <= 0:
        raise ValueError("时限必须为正数，提醒窗口需小于时限，版本必须为正数")
    engine, factory = create_database(Settings().database_url.get_secret_value())
    try:
        async with factory() as session, session.begin():
            latest = await session.scalar(select(func.max(SLARule.version)).where(SLARule.priority == args.priority)) or 0
            if args.version <= latest:
                raise ValueError("新版本必须大于该优先级现有最大版本")
            session.add(SLARule(priority=args.priority, version=args.version,
                                response_seconds=args.seconds, warning_seconds=args.warning_seconds))
        print("SLA 规则已发布，仅影响新建工单")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--priority", required=True, choices=["low", "normal", "high", "urgent"])
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument("--warning-seconds", type=int, default=900)
    asyncio.run(configure(parser.parse_args()))
