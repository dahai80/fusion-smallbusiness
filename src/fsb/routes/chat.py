import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db.store import Store
from ..models.workspace import Workspace
from ..tenant_dep import require_admin, ws_tenant_dep

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workspace/{wsId}",
    tags=["chat"],
    dependencies=[Depends(ws_tenant_dep)],
)


def get_store() -> Store:
    from ..app import app_state

    return app_state.store


class AgentBindRequest(BaseModel):
    agentId: str


class ChatRunRequest(BaseModel):
    query: str
    inputData: dict = {}


@router.post("/agent/bind")
async def bind_agent(wsId: str, body: AgentBindRequest):
    require_admin()
    store = get_store()
    data = await store.get_workspace(wsId)
    if not data:
        raise HTTPException(status_code=404, detail="workspace not found")
    ws = Workspace(**data)
    ws.bindAgentId = body.agentId
    await store.save_workspace(wsId, ws.model_dump(mode="json"))
    from ..engine.chat_client import bind_agent as chat_bind

    upstream = await chat_bind(wsId, body.agentId)
    logger.info("agent bound: ws=%s agent=%s upstream=%s", wsId, body.agentId, upstream.get("status"))
    return {"success": True, "workspaceId": wsId, "bindAgentId": body.agentId, "upstream": upstream}


@router.post("/agent/unbind")
async def unbind_agent(wsId: str):
    require_admin()
    store = get_store()
    data = await store.get_workspace(wsId)
    if not data:
        raise HTTPException(status_code=404, detail="workspace not found")
    ws = Workspace(**data)
    agent_id = ws.bindAgentId or ""
    ws.bindAgentId = None
    await store.save_workspace(wsId, ws.model_dump(mode="json"))
    from ..engine.chat_client import unbind_agent as chat_unbind

    upstream = await chat_unbind(wsId, agent_id) if agent_id else {"status": "skipped"}
    logger.info("agent unbound: ws=%s agent=%s", wsId, agent_id)
    return {"success": True, "workspaceId": wsId, "upstream": upstream}


@router.post("/chat/run")
async def chat_run(wsId: str, body: ChatRunRequest):
    store = get_store()
    from ..engine.router import IntentRouter
    from ..engine.runner import WorkflowRunner

    router_ = IntentRouter(store)
    wf = await router_.match(wsId, body.query)
    if not wf:
        logger.info("chat run no match: ws=%s query=%r", wsId, body.query)
        raise HTTPException(status_code=404, detail=f"no workflow matched query: {body.query}")
    runner = WorkflowRunner(store)
    try:
        run = await runner.start(
            wsId,
            wf.wfId,
            input_data=body.inputData,
            triggered_by=f"chat:{body.query}",
        )
        logger.info("chat run started: ws=%s wf=%s run=%s", wsId, wf.wfId, run.runId)
        return {
            "matched": True,
            "query": body.query,
            "workflow": wf.model_dump(mode="json"),
            "run": run.model_dump(mode="json"),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
