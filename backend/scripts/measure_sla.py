"""隔离测试库的 SLA 积压与检测延迟实测，使用明确的合成截止时间。"""
import argparse
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db.base import utcnow
from app.db.session import create_database
from app.models import Activity, Comment, Notification, SLAEvent, Ticket, TicketSLA, User
from app.sla_scheduler import SLAIndex
from scripts.scan_sla import Scanner


async def measure(output):
    url = os.environ.get("HELPFLOW_TEST_DATABASE_URL", "")
    parsed = make_url(url)
    if parsed.drivername != "mysql+asyncmy" or not (parsed.database or "").startswith("helpflow_stage5_test"):
        raise ValueError("只能使用显式 helpflow_stage5_test 前缀的独立测试库")
    engine, factory = create_database(url)
    key = "helpflow:test:sla:measure:" + uuid4().hex
    redis_url = os.environ.get("HELPFLOW_TEST_REDIS_URL")
    index = SLAIndex(Settings(_env_file=None, redis_url=redis_url, sla_redis_key=key))
    ids, user_ids = [], []
    try:
        now = utcnow()
        async with factory() as session, session.begin():
            for role in ("user", "admin"):
                user = User(username="SLA测量", email=f"sla-measure-{uuid4().hex}@example.com",
                    password_hash="!measurement-no-login", role=role, is_active=True)
                session.add(user)
                await session.flush()
                user_ids.append(user.id)
            for number in range(12):
                ticket = Ticket(ticket_no=uuid4().hex, title="SLA测量", description="合成截止时间",
                    creator_id=user_ids[0], category="other", priority="normal", status="open")
                session.add(ticket)
                await session.flush()
                ids.append(ticket.id)
                due = now + timedelta(seconds=-10 if number < 6 else 60)
                session.add(TicketSLA(ticket_id=ticket.id, version=1, priority="normal",
                    response_seconds=28800, warning_seconds=900, started_at=due-timedelta(hours=8), due_at=due))
        # 未向 Redis 写入，重现数据库已提交而索引丢失的状态。
        scanner = Scanner(factory, index, batch_size=3)
        started = perf_counter()
        first = await scanner.run_once()
        elapsed = (perf_counter() - started) * 1000
        second = await scanner.run_once()
        async with factory() as session:
            mysql_version = await session.scalar(select(func.version()))
            rows = list(await session.scalars(select(SLAEvent).where(SLAEvent.ticket_id.in_(ids))))
            escalations = [r for r in rows if r.kind == "overdue"]
            warnings = [r for r in rows if r.kind == "due_soon"]
            notifications = await session.scalar(select(func.count()).select_from(Notification).where(Notification.ticket_id.in_(ids)))
        assert len(escalations) == 6 and len(warnings) == 6 and second["events"] == 0
        report = dict(measured_at=utcnow().isoformat(), sample=12, batch_size=3,
            mode="real_redis" if redis_url else "database_only", mysql=mysql_version,
            scenario="6 overdue by 10 seconds, 6 due in 60 seconds; deliberately synthetic deadlines; Redis initially empty",
            first_round_ms=round(elapsed, 3), first_round=first, repeated_round=second,
            sample_overdue_events=len(escalations), sample_warning_events=len(warnings),
            sample_notifications=notifications,
            overdue_detection_delay_seconds=[round((r.occurred_at-r.due_at).total_seconds(), 6) for r in escalations],
            limitations="Single local scanner, synthetic deadlines, no external network or throughput claim")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
    finally:
        async with factory() as session, session.begin():
            for model in (Notification, SLAEvent, TicketSLA, Comment, Activity):
                await session.execute(delete(model).where(model.ticket_id.in_(ids)))
            await session.execute(delete(Ticket).where(Ticket.id.in_(ids)))
            await session.execute(delete(User).where(User.id.in_(user_ids)))
        await index.command("delete", key)
        await index.close()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2] / ".local/sla-measurement.json")
    asyncio.run(measure(parser.parse_args().output))
