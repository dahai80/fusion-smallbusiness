import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .auth import verify_jwt_with_identity
from .config import fsb_config
from .db.store import Store
from .routes import (
    connector,
    execution,
    external,
    integration,
    skill,
    variable,
    workflow,
    workspace,
)

logger = logging.getLogger(__name__)


def _install_auth(app: FastAPI) -> None:
    if fsb_config.STANDALONE_MODE:
        logger.info("auth: standalone mode — tenant middleware skipped, workspace routes UNGUARDED")
        return
    try:
        from fusion_core.tenant import install_tenant_middleware
    except ImportError:
        logger.warning("auth: fusion_core.tenant not installed — workspace routes run UNGUARDED")
        return
    install_tenant_middleware(
        app,
        verify_jwt=verify_jwt_with_identity,
        require_jwt=fsb_config.AUTH_REQUIRE_JWT,
    )
    logger.info("auth: tenant middleware installed require_jwt=%s", fsb_config.AUTH_REQUIRE_JWT)


class AppState:
    def __init__(self):
        self.store: Store = Store()


app_state = AppState()


@asynccontextmanager
async def lifespan(application: FastAPI):
    await app_state.store.init()
    logger.info("fsb application started")

    try:
        from .engine.cowork_client import register_module

        result = await register_module(
            module_id="fsb",
            name="Small Business",
            icon="briefcase",
            route_path="/fsb",
        )
        if result.get("status") == "success":
            logger.info("fsb module registered in cowork sidebar")
        else:
            logger.warning("fsb sidebar registration skipped: %s", result.get("message"))
    except Exception as e:
        logger.warning("fsb sidebar registration failed: %s", e)

    yield
    await app_state.store.close()
    logger.info("fsb application stopped")


app = FastAPI(
    title="Fusion Small Business",
    version="0.1.4",
    description="Cross-SaaS intelligent business workspace API",
    lifespan=lifespan,
)

API_PREFIX = "/api/v1/fsb"

app.include_router(workspace.router, prefix=API_PREFIX)
app.include_router(connector.router, prefix=API_PREFIX)
app.include_router(connector.meta_router, prefix=API_PREFIX)
app.include_router(skill.router, prefix=API_PREFIX)
app.include_router(workflow.router, prefix=API_PREFIX)
app.include_router(execution.router, prefix=API_PREFIX)
app.include_router(integration.router, prefix=API_PREFIX)
app.include_router(external.router, prefix=API_PREFIX)
app.include_router(variable.router, prefix=API_PREFIX)

_install_auth(app)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "fusion-smallbusiness"}
