from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """DATETIME 存储 UTC，读取恢复时区。"""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("数据库时间必须显式指定时区")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    pass


class UTCMicroDateTime(UTCDateTime):
    """SLA 边界比较保留微秒；不改变历史业务时间列的精度。"""
    cache_ok = True

    def load_dialect_impl(self, dialect):
        from sqlalchemy.dialects.mysql import DATETIME
        return dialect.type_descriptor(DATETIME(fsp=6) if dialect.name == "mysql" else DateTime())


def utcnow() -> datetime:
    return datetime.now(UTC)
