"""密码只进行哈希；JWT 固定算法并强制检查必要载荷。"""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.errors import unauthorized

password_hasher = PasswordHash.recommended()
# 未知邮箱也执行一次真实密码校验，避免直接通过返回时间识别账号。
_dummy_hash = password_hasher.hash("unused-dummy-password-4815")


async def hash_password(password: str) -> str:
    return await run_in_threadpool(password_hasher.hash, password)


async def verify_password(password: str, hashed: str | None) -> bool:
    try:
        valid = await run_in_threadpool(password_hasher.verify, password, hashed or _dummy_hash)
        return valid and hashed is not None
    except (UnknownHashError, ValueError):
        await run_in_threadpool(password_hasher.verify, password, _dummy_hash)
        return False


def password_version(hashed: str, settings: Settings) -> str:
    return hmac.new(settings.signing_key().encode(), hashed.encode(), hashlib.sha256).hexdigest()


def create_access_token(user, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": str(user.id), "role": user.role, "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        "pwdv": password_version(user.password_hash, settings),
    }, settings.signing_key(), algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> dict:
    try:
        claims = jwt.decode(token, settings.signing_key(), algorithms=["HS256"],
                            options={"require": ["sub", "role", "iat", "exp", "pwdv"]})
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal():
            raise ValueError
        if not 0 < int(subject) <= 9223372036854775807:
            raise ValueError
        if claims["role"] not in ("user", "agent", "admin") or not isinstance(claims["pwdv"], str):
            raise ValueError
        if len(claims["pwdv"]) != 64 or any(c not in "0123456789abcdef" for c in claims["pwdv"]):
            raise ValueError
        return claims
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise unauthorized() from None
