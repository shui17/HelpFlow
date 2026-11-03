"""单进程滑动窗口限流；多实例部署需在可信网关配置共享限流。"""
from collections import OrderedDict, deque
import hashlib
import math
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request


class AuthRateLimiter:
    def __init__(self, *, clock=monotonic, max_keys=10_000):
        self.clock = clock
        self.max_keys = max_keys
        self.buckets = OrderedDict()
        self.lock = Lock()

    def check(self, rules, window):
        now = self.clock()
        with self.lock:
            # 按最后一次接受请求的时间淘汰过期条目；不淘汰活跃条目以绕过限制。
            while self.buckets and next(iter(self.buckets.values()))[-1] <= now - window:
                self.buckets.popitem(last=False)
            for key, limit in rules:
                hits = self.buckets.get(key, ())
                while hits and hits[0] <= now - window:
                    hits.popleft()
                if len(hits) >= limit:
                    self.reject(max(1, math.ceil(hits[0] + window - now)))
            missing = sum(key not in self.buckets for key, _ in rules)
            if len(self.buckets) + missing > self.max_keys:
                self.reject(window)
            for key, _ in rules:
                self.buckets.setdefault(key, deque()).append(now)
                self.buckets.move_to_end(key)

    @staticmethod
    def reject(retry_after):
        raise HTTPException(429, "请求过于频繁，请稍后重试", headers={"Retry-After": str(retry_after)})


def check_auth_rate(request: Request, operation: str, email: str):
    settings = request.app.state.settings
    if not settings.auth_rate_limit_enabled:
        return
    # 不信任任意 X-Forwarded-For；反向代理部署应明确配置 Uvicorn 的可信代理。
    host = request.client.host if request.client else "unknown"
    account = hashlib.sha256(email.strip().lower().encode()).hexdigest()
    if operation == "login":
        rules = [(f"login:ip:{host}", settings.auth_login_ip_limit),
                 (f"login:account:{account}", settings.auth_login_account_limit)]
    else:
        rules = [(f"register:ip:{host}", settings.auth_register_ip_limit)]
    request.app.state.auth_rate_limiter.check(rules, settings.auth_rate_window_seconds)
