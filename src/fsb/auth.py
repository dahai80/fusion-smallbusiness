import logging
from typing import Any

import httpx

from .config import fsb_config

logger = logging.getLogger(__name__)


def verify_jwt_with_identity(token: str) -> dict[str, Any]:
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
    logger.info("auth: token verified tid=%s role=%s", payload.get("tid"), payload.get("role"))
    return {
        "tid": payload.get("tid"),
        "role": payload.get("role"),
        "scope": payload.get("scopes") or [],
        "jti": None,
    }
