import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_EXEMPT_PATHS = ("/health", "/docs", "/openapi.json", "/redoc")


class _TokenBucket:
    __slots__ = ("capacity", "last", "refill_rate", "tokens")

    def __init__(self, capacity: float, refill_rate: float, now: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last = now

    def allow(self, now: float) -> bool:
        elapsed = now - self.last
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        capacity: float = 60,
        refill_rate: float = 10,
        max_body_bytes: int = 2 * 1024 * 1024,
        store=None,
        distributed: bool = False,
    ):
        super().__init__(app)
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.max_body_bytes = max_body_bytes
        self.store = store
        self.distributed = distributed
        self._buckets: dict[str, _TokenBucket] = {}

    async def _allow(self, key: str) -> bool:
        if self.distributed and self.store is not None:
            try:
                return await self.store.rate_limit_consume(key, int(self.capacity), int(self.refill_rate))
            except Exception as e:
                logger.warning("distributed rate limit failed, falling back local: %s", e)
        now = time.monotonic()
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _TokenBucket(self.capacity, self.refill_rate, now)
            self._buckets[key] = bucket
        return bucket.allow(now)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _EXEMPT_PATHS or path.endswith("/health"):
            return await call_next(request)

        if request.method in ("POST", "PUT", "PATCH"):
            cl = request.headers.get("content-length")
            if cl and cl.isdigit() and int(cl) > self.max_body_bytes:
                logger.warning("request body too large: path=%s size=%s", path, cl)
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"request body exceeds {self.max_body_bytes} bytes"},
                )

        client_id = request.client.host if request.client else "unknown"
        tenant = request.headers.get("X-Tenant-Id", "")
        key = f"{tenant}:{client_id}" if tenant else client_id
        if not await self._allow(key):
            logger.warning("rate limit exceeded: key=%s path=%s", key, path)
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded, retry later"},
                headers={"Retry-After": "1"},
            )
        return await call_next(request)
