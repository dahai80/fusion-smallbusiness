import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db.store import Store
from ..tenant_dep import ws_tenant_dep

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workspace/{wsId}/intent",
    tags=["intent"],
    dependencies=[Depends(ws_tenant_dep)],
)


class IntentRequest(BaseModel):
    query: str


def get_store() -> Store:
    from ..app import app_state

    return app_state.store


@router.post("/match")
async def match_intent(wsId: str, body: IntentRequest):
    store = get_store()
    from ..engine.router import IntentRouter

    router_ = IntentRouter(store)
    wf = await router_.match(wsId, body.query)
    if not wf:
        logger.info("intent no match: ws=%s query=%r", wsId, body.query)
        return {"matched": False, "query": body.query}
    logger.info("intent matched: ws=%s query=%r -> wf=%s", wsId, body.query, wf.wfId)
    return {"matched": True, "query": body.query, "workflow": wf.model_dump(mode="json")}


@router.get("/commands")
async def list_commands(wsId: str):
    store = get_store()
    from ..engine.router import IntentRouter

    router_ = IntentRouter(store)
    commands = await router_.list_slash_commands(wsId)
    return {"commands": commands, "count": len(commands)}


@router.post("/run")
async def run_intent(wsId: str, body: IntentRequest):
    store = get_store()
    from ..engine.router import IntentRouter
    from ..engine.runner import WorkflowRunner

    router_ = IntentRouter(store)
    wf = await router_.match(wsId, body.query)
    if not wf:
        raise HTTPException(status_code=404, detail=f"no workflow matched query: {body.query}")
    runner = WorkflowRunner(store)
    try:
        run = await runner.start(wsId, wf.wfId, triggered_by=f"intent:{body.query}")
        logger.info("intent run started: ws=%s wf=%s run=%s", wsId, wf.wfId, run.runId)
        return {"matched": True, "query": body.query, "run": run.model_dump(mode="json")}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
