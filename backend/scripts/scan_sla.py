"""独立 SLA 扫描进程：uv run python -m scripts.scan_sla [--once|--rebuild]。"""
import argparse
import asyncio
import json
import logging
import time
from datetime import timedelta

from sqlalchemy import func, select

from app.config import Settings
from app.db.base import utcnow
from app.db.session import create_database
from app.models import Ticket, TicketSLA
from app.services.sla import inspect_locked, pending
from app.sla_scheduler import SLAIndex

logger = logging.getLogger(__name__)


class Scanner:
    def __init__(self, factory, index, batch_size=100):
        self.factory, self.index, self.batch_size = factory, index, batch_size

    async def process(self, ticket_id, version, stats, *, now=None):
        """失败不清理 Redis；提交成功后才操作索引，下一轮可重复执行。"""
        try:
            async with self.factory() as session:
                async with session.begin():
                    ticket = await session.scalar(select(Ticket).where(Ticket.id == ticket_id)
                        .with_for_update().execution_options(populate_existing=True))
                    if ticket is None:
                        keep, row, created = False, None, 0
                    else:
                        # SLA 版本不同的旧 Redis 成员只能清理，不能触发新版本业务。
                        current = ticket.sla_snapshot
                        if current is None or current.version != version:
                            keep, row, created = False, None, 0
                        else:
                            checked_at = now or utcnow()
                            keep, row, created = await inspect_locked(session, ticket, checked_at)
                stats["processed"] += 1
                stats["events"] += created
                if created:
                    threshold = row.due_at if row.escalated_at else row.due_at - timedelta(seconds=row.warning_seconds)
                    stats["max_detection_delay_seconds"] = max(stats["max_detection_delay_seconds"],
                                                                (checked_at - threshold).total_seconds())
                    metric = "max_overdue_delay_seconds" if row.escalated_at else "max_warning_delay_seconds"
                    stats[metric] = max(stats.get(metric, 0), (checked_at - threshold).total_seconds())
                if keep:
                    await self.index.put(row)
                else:
                    await self.index.remove(f"{ticket_id}:{version}")
                return keep
        except Exception as exc:
            stats["failed"] += 1
            logger.warning("sla_item_failed ticket_id=%s error=%s", ticket_id, type(exc).__name__)
            return True

    async def compensate(self, stats, *, now=None):
        # 固定高水位 + ID 游标，避免首批已提醒/失败记录和新数据饿死后续记录。
        async with self.factory() as session:
            upper = await session.scalar(select(func.max(TicketSLA.ticket_id))) or 0
        cursor = 0
        while cursor < upper:
            async with self.factory() as session:
                rows = (await session.execute(select(TicketSLA.ticket_id, TicketSLA.version)
                    .where(pending(), TicketSLA.ticket_id > cursor, TicketSLA.ticket_id <= upper)
                    .order_by(TicketSLA.ticket_id).limit(self.batch_size))).all()
            if not rows:
                break
            for ticket_id, version in rows:
                await self.process(ticket_id, version, stats, now=now)
                stats["compensated"] += 1
            cursor = rows[-1].ticket_id

    async def redis_due(self, stats, *, now=None):
        async with self.factory() as session:
            window = await session.scalar(select(func.max(TicketSLA.warning_seconds)).where(pending())) or 0
        horizon = (now or utcnow()).timestamp() + window
        offset = 0
        while True:
            members = await self.index.command("zrangebyscore", self.index.key, "-inf", horizon,
                                                start=offset, num=self.batch_size)
            if not members:
                return
            for member in members:
                try:
                    ticket_id, version = map(int, member.split(":"))
                    if not 0 < ticket_id <= 9_223_372_036_854_775_807 or not 0 < version <= 2_147_483_647:
                        raise ValueError("invalid SLA member")
                except (ValueError, TypeError):
                    await self.index.remove(member)
                    continue
                await self.process(ticket_id, version, stats, now=now)
            # 每页处理后重新计算末尾仍存在成员之前的 rank，避免自身删除引起分页跳过。
            # 并发删除引起的暂时遗漏由下一轮和数据库补偿找回。
            last = members[-1]
            rank = await self.index.command("zrank", self.index.key, last)
            if rank is not None:
                offset = rank + 1
            else:
                retained = 0
                for member in members:
                    if await self.index.command("zscore", self.index.key, member) is not None:
                        retained += 1
                offset += retained

    async def run_once(self, *, compensate=True, now=None):
        self.index.begin_round()
        stats = dict(processed=0, events=0, failed=0, compensated=0, max_detection_delay_seconds=0)
        await self.redis_due(stats, now=now)
        if compensate:
            await self.compensate(stats, now=now)
        async with self.factory() as session:
            current = now or utcnow()
            stats["pending"] = await session.scalar(select(func.count()).select_from(TicketSLA).where(pending()))
            stats["overdue_pending"] = await session.scalar(select(func.count()).select_from(TicketSLA)
                .where(pending(), TicketSLA.due_at < current))
            earliest = await session.scalar(select(func.min(TicketSLA.due_at)).where(pending(), TicketSLA.due_at < current))
            stats["oldest_overdue_at"] = earliest.isoformat() if earliest else None
        return stats


async def main(args):
    settings = Settings()
    engine, factory = create_database(settings.database_url.get_secret_value())
    index = SLAIndex(settings)
    scanner = Scanner(factory, index, settings.sla_batch_size)
    previous = float("-inf")
    try:
        while True:
            start = time.monotonic()
            compensate = args.once or args.rebuild or start - previous >= settings.sla_compensate_seconds
            try:
                stats = await scanner.run_once(compensate=compensate)
                if compensate:
                    previous = start
                print(json.dumps(stats), flush=True)
            except Exception as exc:
                logger.error("sla_scan_failed error=%s", type(exc).__name__)
                if args.once or args.rebuild:
                    raise SystemExit(1) from None
            if args.once or args.rebuild:
                break
            await asyncio.sleep(settings.sla_scan_seconds)
    finally:
        await index.close()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--once", action="store_true")
    modes.add_argument("--rebuild", action="store_true", help="从数据库补齐索引并处理已到期业务；不清空其他 Redis 数据")
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main(parser.parse_args()))
    except KeyboardInterrupt:
        pass
