from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic

from fastapi import Request
from starlette.responses import JSONResponse

from services.gateway.app.middleware.auth import get_actor


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int = 0


class InMemoryRateLimiter:
    def __init__(self, *, limit: int = 240, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._entries: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> RateLimitDecision:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._entries[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - bucket[0])))
                return RateLimitDecision(
                    allowed=False,
                    limit=self.limit,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )
            bucket.append(now)
            remaining = max(self.limit - len(bucket), 0)
            return RateLimitDecision(allowed=True, limit=self.limit, remaining=remaining)


def _client_key(request: Request) -> str:
    actor = get_actor(request)
    client_host = request.client.host if request.client is not None else "local"
    return f"{actor.role}:{actor.user_id}:{client_host}:{request.url.path}"


async def enforce_rate_limit(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        return await call_next(request)

    decision = limiter.check(_client_key(request))
    request.state.rate_limit = decision
    if not decision.allowed:
        return JSONResponse(
            status_code=429,
            content={
                "status": "rate_limited",
                "limit": decision.limit,
                "retry_after_seconds": decision.retry_after_seconds,
            },
            headers={
                "x-ratelimit-limit": str(decision.limit),
                "x-ratelimit-remaining": str(decision.remaining),
                "retry-after": str(decision.retry_after_seconds),
            },
        )

    response = await call_next(request)
    response.headers["x-ratelimit-limit"] = str(decision.limit)
    response.headers["x-ratelimit-remaining"] = str(decision.remaining)
    return response
