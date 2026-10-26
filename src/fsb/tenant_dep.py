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


def current_tenant():
    if _current_tenant is None:
        return None
    return _current_tenant()


_ADMIN_ROLES = {"admin", "owner"}


def require_admin() -> None:
    ctx = current_tenant()
    if ctx is None:
        logger.info("require_admin: no tenant context (auth disabled) — skipping")
        return
    role = (ctx.role or "").lower()
    if role not in _ADMIN_ROLES:
        logger.warning("require_admin: forbidden role=%s scopes=%s", ctx.role, ctx.scopes)
        raise HTTPException(status_code=403, detail="admin role required")


def require_tenant_owns(wsId: str) -> None:
    ctx = current_tenant()
    if ctx is None:
        logger.info("require_tenant_owns: no tenant context (auth disabled) for wsId=%s — skipping", wsId)
        return
    if str(ctx.tenant_id) != str(wsId):
        logger.warning(
            "require_tenant_owns: tenant mismatch wsId=%s tenant_id=%s",
            wsId,
            ctx.tenant_id,
        )
        raise HTTPException(status_code=403, detail="resource does not belong to caller tenant")


def require_tenant_present() -> None:
    # Router-level guard: reject when auth is active but no tenant context is
    # attached. Prevents a handler forgetting require_tenant_owns from leaking
    # cross-tenant data — at minimum every external request must carry a tenant.
    # No-op in standalone mode (auth middleware never installed) and when
    # fusion_core.tenant is unavailable.
    from .config import fsb_config

    if fsb_config.STANDALONE_MODE:
        return
    if _current_tenant is None:
        return
    ctx = _current_tenant()
    if ctx is None:
        logger.warning("require_tenant_present: auth active but no tenant context — rejecting")
        raise HTTPException(status_code=401, detail="tenant context required")
