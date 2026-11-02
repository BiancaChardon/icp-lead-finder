import math
import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    """In-memory sliding-window limiter.

    State is per process: run the backend as a single process (the default)
    or replace this with a shared store before scaling out.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float = 60.0) -> float | None:
        """Record a hit. Returns None if allowed, or seconds until retry if limited."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return max(hits[0] + window_seconds - now, 0.0)
            hits.append(now)
            if len(self._hits) > 10_000:
                self._prune(now, window_seconds)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def _prune(self, now: float, window_seconds: float) -> None:
        stale = [k for k, q in self._hits.items() if not q or q[-1] <= now - window_seconds]
        for key in stale:
            del self._hits[key]


def enforce_rate_limit(request: Request, key: str, limit: int) -> None:
    limiter: RateLimiter = request.app.state.limiter
    retry_after = limiter.hit(key, limit)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait and try again.",
            headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
        )


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
