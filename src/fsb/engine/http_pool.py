import logging
from contextlib import asynccontextmanager

import httpx

from ..config import fsb_config

logger = logging.getLogger(__name__)

_shared_client: httpx.AsyncClient | None = None


def init_shared_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=fsb_config.HTTP_TIMEOUT,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20, keepalive_expiry=30.0),
        )
        logger.info("shared httpx client initialized (pool: max_conn=50 keepalive=20)")
    return _shared_client


async def close_shared_client() -> None:
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
        logger.info("shared httpx client closed")
    _shared_client = None


@asynccontextmanager
async def acquire_client(timeout: float | None = None):
    if _shared_client is not None and not _shared_client.is_closed:
        yield _shared_client
        return
    async with httpx.AsyncClient(timeout=timeout or fsb_config.HTTP_TIMEOUT) as client:
        yield client
