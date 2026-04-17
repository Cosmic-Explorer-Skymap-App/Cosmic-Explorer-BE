import datetime
import os
import threading
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """Simple in-memory limiter: suitable for a single-process deployment."""

    def __init__(self) -> None:
        self._store: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._store[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


rate_limiter = InMemoryRateLimiter()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def user_agent(request: Request) -> str:
    return (request.headers.get("user-agent", "") or "")[:500]


def require_rate_limit(request: Request, *, scope: str, limit: int, window_seconds: int) -> None:
    ip = client_ip(request)
    key = f"{scope}:{ip}"
    if not rate_limiter.hit(key, limit=limit, window_seconds=window_seconds):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, please try again later.",
        )


def security_headers() -> dict[str, str]:
    csp = os.getenv(
        "SECURITY_CSP",
        "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self';",
    )
    hsts_max_age = os.getenv("HSTS_MAX_AGE", "31536000")
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
        "Content-Security-Policy": csp,
        "Strict-Transport-Security": f"max-age={hsts_max_age}; includeSubDomains; preload",
    }


def now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)
