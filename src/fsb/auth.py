import logging
import time
from typing import Any

import httpx

from .config import fsb_config

logger = logging.getLogger(__name__)

_JWT_CACHE_TTL = 30
_jwt_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_JWT_CACHE_MAX = 1024


def _cache_get(token: str) -> dict[str, Any] | None:
    entry = _jwt_cache.get(token)
    if not entry:
        return None
    expires_at, claims = entry
    if time.monotonic() > expires_at:
        _jwt_cache.pop(token, None)
        return None
    return claims


def _cache_put(token: str, claims: dict[str, Any]) -> None:
    if len(_jwt_cache) >= _JWT_CACHE_MAX:
        oldest = min(_jwt_cache, key=lambda k: _jwt_cache[k][0])
        _jwt_cache.pop(oldest, None)
    _jwt_cache[token] = (time.monotonic() + _JWT_CACHE_TTL, claims)


def verify_jwt_with_identity(token: str) -> dict[str, Any]:
    cached = _cache_get(token)
    if cached is not None:
        logger.debug("auth: token verified via cache tid=%s", cached.get("tid"))
        return cached
    if not fsb_config.FUSION_IDENTITY_SERVICE_TOKEN:
        logger.warning("auth: FUSION_IDENTITY_SERVICE_TOKEN unset — cannot verify JWT, rejecting")
        raise PermissionError("identity service token not configured")
    url = f"{fsb_config.FUSION_IDENTITY_URL}/api/v1/auth/verify"
    headers = {"X-Service-Token": fsb_config.FUSION_IDENTITY_SERVICE_TOKEN}
    try:
        resp = httpx.post(url, json={"token": token}, headers=headers, timeout=fsb_config.HTTP_TIMEOUT)
    except httpx.HTTPError as exc:
        logger.warning("auth: identity verify call failed: %s", exc)
        raise PermissionError(f"identity unreachable: {exc}") from exc
    if resp.status_code != 200:
        logger.info("auth: identity rejected token (status=%s)", resp.status_code)
        raise PermissionError(f"identity rejected token: {resp.status_code}")
    payload = resp.json()
    if payload.get("revoked"):
        logger.info("auth: token revoked (tid=%s)", payload.get("tid"))
        raise PermissionError("token revoked")
    claims = {
        "tid": payload.get("tid"),
        "role": payload.get("role"),
        "scope": payload.get("scopes") or [],
        "jti": None,
    }
    _cache_put(token, claims)
    logger.info("auth: token verified tid=%s role=%s", claims.get("tid"), claims.get("role"))
    return claims
