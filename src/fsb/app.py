import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .auth import verify_jwt_with_identity
from .config import fsb_config
from .db import make_store
from .routes import (
    chat,
    connector,
    execution,
    external,
    integration,
    intent,
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
        self.store = make_store()
        self.scheduler = None


app_state = AppState()


@asynccontextmanager
async def lifespan(application: FastAPI):
    await app_state.store.init()
    logger.info("fsb application started")
    try:
        from .engine.http_pool import init_shared_client

        init_shared_client()
    except Exception as e:
        logger.warning("shared http client init failed: %s", e)

    try:
        from .seed import seed_builtins

        await seed_builtins(app_state.store)
    except Exception as e:
        logger.warning("builtin seeding failed: %s", e)

    try:
        from .engine.scheduler import WorkflowScheduler

        scheduler_enabled = os.environ.get("FSB_SCHEDULER_ENABLED", "true").lower() in ("true", "1", "yes")
        if not scheduler_enabled:
            logger.info("workflow scheduler disabled via FSB_SCHEDULER_ENABLED — leader-only mode")
            app_state.scheduler = None
        else:
            app_state.scheduler = WorkflowScheduler(app_state.store)
            app_state.scheduler.start()
            await app_state.scheduler.ensure_leadership()
            await _register_existing_cron_jobs(app_state.scheduler, app_state.store)
            logger.info("workflow scheduler started")
    except Exception as e:
        logger.error("workflow scheduler start failed: %s — cron schedules may be lost", e)
        app_state.scheduler = None

    try:
        await _reap_stale_runs(app_state.store)
    except Exception as e:
        logger.warning("stale run reaper failed: %s", e)

    try:
        result = await app_state.store.cleanup_old_runs(retention_days=fsb_config.RUN_RETENTION_DAYS)
        logger.info("initial run retention cleanup done: %s", result)
    except Exception as e:
        logger.warning("run retention cleanup failed: %s", e)

    if app_state.scheduler:
        try:
            from apscheduler.triggers.interval import IntervalTrigger

            app_state.scheduler._scheduler.add_job(
                app_state.store.cleanup_old_runs,
                trigger=IntervalTrigger(hours=1),
                id="fsb_retention_cleanup",
                args=[fsb_config.RUN_RETENTION_DAYS],
                replace_existing=True,
            )
            logger.info(
                "run retention cleanup job scheduled (hourly, retention=%d days)", fsb_config.RUN_RETENTION_DAYS
            )
        except Exception as e:
            logger.warning("retention cleanup job scheduling failed: %s", e)

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
    if app_state.scheduler:
        try:
            app_state.scheduler.stop()
        except Exception as e:
            logger.warning("workflow scheduler stop failed: %s", e)
    try:
        from .engine.http_pool import close_shared_client

        await close_shared_client()
    except Exception as e:
        logger.warning("shared http client close failed: %s", e)
    await app_state.store.close()
    logger.info("fsb application stopped")


async def _reap_stale_runs(store):
    from .models.common import RunStatus, utc_now

    try:
        ws_offset = 0
        reaped = 0
        threshold = utc_now()
        while True:
            workspaces = await store.list_workspaces(offset=ws_offset, limit=200)
            if not workspaces:
                break
            for ws_data in workspaces:
                ws_id = ws_data.get("wsId", "")
                wf_offset = 0
                while True:
                    workflows = await store.list_workflows(ws_id, offset=wf_offset, limit=200)
                    if not workflows:
                        break
                    for wf_data in workflows:
                        wf_id = wf_data.get("wfId", "")
                        runs = await store.list_runs(ws_id, wf_id=wf_id, limit=200)
                        for run_data in runs:
                            if run_data.get("status") == RunStatus.RUNNING.value:
                                run_data["status"] = RunStatus.FAILED.value
                                run_data["endTime"] = threshold
                                run_data["error"] = "reaped: stale RUNNING run after restart"
                                await store.save_run(
                                    run_data.get("runId", ""),
                                    ws_id,
                                    wf_id,
                                    run_data,
                                )
                                reaped += 1
                    if len(workflows) < 200:
                        break
                    wf_offset += 200
            if len(workspaces) < 200:
                break
            ws_offset += 200
        if reaped:
            logger.error("reaped %d stale RUNNING runs after restart", reaped)
        else:
            logger.info("stale run reaper: no stale runs found")
    except Exception as e:
        logger.warning("stale run reaper error: %s", e)


async def _register_existing_cron_jobs(scheduler, store):
    from .models.common import ScheduleType

    try:
        ws_offset = 0
        registered = 0
        expected = 0
        while True:
            workspaces = await store.list_workspaces(offset=ws_offset, limit=200)
            if not workspaces:
                break
            for ws_data in workspaces:
                ws_id = ws_data.get("wsId", "")
                wf_offset = 0
                while True:
                    workflows = await store.list_workflows(ws_id, offset=wf_offset, limit=200)
                    if not workflows:
                        break
                    for wf_data in workflows:
                        wf_id = wf_data.get("wfId", "")
                        sched = wf_data.get("schedule", {}) or {}
                        if sched.get("type") == ScheduleType.CRON and sched.get("cron"):
                            expected += 1
                            await scheduler.register(ws_id, wf_id)
                            registered += 1
                    if len(workflows) < 200:
                        break
                    wf_offset += 200
            if len(workspaces) < 200:
                break
            ws_offset += 200
        if registered != expected:
            logger.error(
                "cron rebuild mismatch: registered=%d expected=%d — some schedules may be lost", registered, expected
            )
        else:
            logger.info("registered %d existing cron jobs (paginated, reconciled)", registered)
    except Exception as e:
        logger.error("failed to register existing cron jobs: %s — schedules may be lost after restart", e)


app = FastAPI(
    title="Fusion Small Business",
    version="0.2.0rc1",
    description="Cross-SaaS intelligent business workspace API",
    lifespan=lifespan,
)

API_PREFIX = "/api/v1/fsb"

app.include_router(workspace.router, prefix=API_PREFIX)
app.include_router(connector.router, prefix=API_PREFIX)
app.include_router(connector.meta_router, prefix=API_PREFIX)
app.include_router(skill.router, prefix=API_PREFIX)
app.include_router(workflow.router, prefix=API_PREFIX)
app.include_router(intent.router, prefix=API_PREFIX)
app.include_router(execution.router, prefix=API_PREFIX)
app.include_router(integration.router, prefix=API_PREFIX)
app.include_router(external.router, prefix=API_PREFIX)
app.include_router(variable.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)

_install_auth(app)

from .middleware import RateLimitMiddleware  # noqa: E402

app.add_middleware(
    RateLimitMiddleware,
    capacity=fsb_config.RATE_LIMIT_CAPACITY,
    refill_rate=fsb_config.RATE_LIMIT_REFILL,
    max_body_bytes=fsb_config.MAX_BODY_BYTES,
    store=app_state.store,
    distributed=fsb_config.RATE_LIMIT_DISTRIBUTED,
)
logger.info(
    "rate limit middleware installed: capacity=%s refill=%s max_body=%s",
    fsb_config.RATE_LIMIT_CAPACITY,
    fsb_config.RATE_LIMIT_REFILL,
    fsb_config.MAX_BODY_BYTES,
)


@app.get("/health")
async def health():
    db_ok = False
    try:
        store = app_state.store
        if store:
            db_ok = await store.is_healthy()
    except Exception as e:
        logger.warning("health db check failed: %s", e)
    status = "ok" if db_ok else "degraded"
    return {"status": status, "service": "fusion-smallbusiness", "db": db_ok}


@app.get("/health/ready")
async def health_ready():
    deps = {"db": False, "fusion_mlx": False, "fusion_gateway": False, "fusion_identity": False}
    try:
        store = app_state.store
        if store:
            deps["db"] = await store.is_healthy()
    except Exception as e:
        logger.warning("ready db check failed: %s", e)
    if not fsb_config.STANDALONE_MODE:
        from .engine.http_pool import acquire_client

        async def _probe(url: str) -> bool:
            try:
                async with acquire_client(3.0) as client:
                    resp = await client.get(url, timeout=3.0)
                    return resp.status_code < 500
            except Exception:
                return False

        deps["fusion_mlx"] = await _probe(f"{fsb_config.FUSION_MLX_URL}/health")
        deps["fusion_gateway"] = await _probe(f"{fsb_config.FUSION_GATEWAY_URL}/health")
        deps["fusion_identity"] = await _probe(f"{fsb_config.FUSION_IDENTITY_URL}/health")
    else:
        deps["fusion_mlx"] = True
        deps["fusion_gateway"] = True
        deps["fusion_identity"] = True
    return {"status": "ok", "dependencies": deps}
