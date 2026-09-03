import logging

from fastapi import HTTPException

try:
    from fusion_core.tenant.context import current as _current_tenant
except ImportError:  # pragma: no cover
    _current_tenant = None

logger = logging.getLogger(__name__)


def require_ws_tenant(wsId: str) -> None:
    if _current_tenant is None:
        logger.warning("tenant_dep: fusion_core.tenant not available — skipping wsId binding")
        return
    ctx = _current_tenant()
    if ctx is None:
        logger.info("tenant_dep: no tenant context (auth disabled) for wsId=%s — skipping", wsId)
        return
    if str(ctx.tenant_id) != str(wsId):
        logger.warning(
            "tenant_dep: tenant mismatch wsId=%s tenant_id=%s",
            wsId,
            ctx.tenant_id,
        )
        raise HTTPException(status_code=403, detail="workspace does not belong to caller tenant")


def ws_tenant_dep(wsId: str) -> None:
    require_ws_tenant(wsId)


def current_tenant_id() -> str | None:
    if _current_tenant is None:
        return None
    ctx = _current_tenant()
    return str(ctx.tenant_id) if ctx else None
