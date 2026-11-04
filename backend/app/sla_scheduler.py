"""可丢弃的 Redis 待办索引；不把 Redis 成功与否当成业务提交结果。"""
import asyncio
import logging

from redis.asyncio import Redis
from redis.backoff import NoBackoff
from redis.asyncio.retry import Retry

from app.config import Settings

logger = logging.getLogger(__name__)


class SLAIndex:
    def __init__(self, settings):
        self.key = settings.sla_redis_key
        self.failed = False
        self.redis = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True,
            socket_timeout=0.5, socket_connect_timeout=0.5, retry=Retry(NoBackoff(), 0)) if settings.redis_url else None

    async def command(self, name, *args, **kwargs):
        if self.redis is None or self.failed:
            return None
        try:
            async with asyncio.timeout(1):
                return await getattr(self.redis, name)(*args, **kwargs)
        except Exception as exc:
            self.failed = True
            # Redis 的异常正文可能包含连接凭据，仅记录异常类型。
            logger.warning("sla_redis_unavailable operation=%s error=%s", name, type(exc).__name__)
            return None

    def begin_round(self):
        # 一轮连接失败后直接补偿，下一轮再探测，避免每条待办等待连接超时。
        self.failed = False

    async def put(self, row):
        return await self.command("zadd", self.key, {f"{row.ticket_id}:{row.version}": row.due_at.timestamp()})

    async def remove(self, member):
        return await self.command("zrem", self.key, member)

    async def close(self):
        if self.redis:
            try:
                await self.redis.aclose()
            except Exception as exc:
                logger.warning("sla_redis_close_failed error=%s", type(exc).__name__)


async def after_commit(ticket_id, version, due_at=None, *, settings=None):
    index = None
    try:
        settings = settings if settings is not None else Settings()
        if not settings.redis_url:
            return
        index = SLAIndex(settings)
        member = f"{ticket_id}:{version}"
        if due_at is None:
            await index.remove(member)
        else:
            await index.command("zadd", index.key, {member: due_at.timestamp()})
    except Exception as exc:
        logger.warning("sla_index_after_commit_failed error=%s", type(exc).__name__)
    finally:
        if index:
            await index.close()
