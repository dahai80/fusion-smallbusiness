import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..db.store import Store
from ..models.workspace import Workspace, WorkspaceCreate, WorkspaceUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace", tags=["workspace"])


def get_store() -> Store:
    from ..app import app_state
    return app_state.store


@router.post("", response_model=Workspace)
async def create_workspace(body: WorkspaceCreate):
    store = get_store()
    ws = Workspace(**body.model_dump())
    await store.save_workspace(ws.wsId, ws.model_dump(mode="json"))
    logger.info("workspace created: %s", ws.wsId)
    return ws


@router.get("", response_model=list[Workspace])
async def list_workspaces(offset: int = 0, limit: int = 100, search: str = "", projectId: str = ""):
    store = get_store()
    items = await store.list_workspaces(offset=offset, limit=limit, search=search, project_id=projectId)
    return [Workspace(**d) for d in items]


@router.get("/{wsId}", response_model=Workspace)
async def get_workspace(wsId: str):
    store = get_store()
    data = await store.get_workspace(wsId)
    if not data:
        raise HTTPException(status_code=404, detail="workspace not found")
    return Workspace(**data)


@router.put("/{wsId}", response_model=Workspace)
async def update_workspace(wsId: str, body: WorkspaceUpdate):
    store = get_store()
    data = await store.get_workspace(wsId)
    if not data:
        raise HTTPException(status_code=404, detail="workspace not found")
    ws = Workspace(**data)
    update = body.model_dump(exclude_unset=True)
    for k, v in update.items():
        setattr(ws, k, v)
    from ..models.common import utc_now
    ws.updateTime = utc_now()
    await store.save_workspace(ws.wsId, ws.model_dump(mode="json"))
    logger.info("workspace updated: %s", wsId)
    return ws


@router.post("/{wsId}/duplicate", response_model=Workspace)
async def duplicate_workspace(wsId: str):
    store = get_store()
    data = await store.get_workspace(wsId)
    if not data:
        raise HTTPException(status_code=404, detail="workspace not found")
    src = Workspace(**data)
    new_ws = Workspace(
        title=f"{src.title} (copy)",
        description=src.description,
        variables=src.variables,
        connectorIds=src.connectorIds,
        skillIds=src.skillIds,
    )
    await store.save_workspace(new_ws.wsId, new_ws.model_dump(mode="json"))
    logger.info("workspace duplicated: %s -> %s", wsId, new_ws.wsId)
    return new_ws


@router.post("/{wsId}/export")
async def export_workspace(wsId: str):
    store = get_store()
    data = await store.get_workspace(wsId)
    if not data:
        raise HTTPException(status_code=404, detail="workspace not found")
    connectors = await store.list_connectors(wsId)
    skills = await store.list_skills(wsId)
    workflows = await store.list_workflows(wsId)
    logger.info("workspace exported: %s", wsId)
    return {
        "workspace": data,
        "connectors": connectors,
        "skills": skills,
        "workflows": workflows,
    }


@router.post("/import", response_model=Workspace)
async def import_workspace(body: dict):
    store = get_store()
    ws_data = body.get("workspace", {})
    ws = Workspace(**ws_data)
    await store.save_workspace(ws.wsId, ws.model_dump(mode="json"))
    for c in body.get("connectors", []):
        from ..models.connector import Connector
        conn = Connector(**c)
        conn.workspaceId = ws.wsId
        await store.save_connector(conn.connId, ws.wsId, conn.model_dump(mode="json"))
    for s in body.get("skills", []):
        from ..models.skill import Skill
        sk = Skill(**s)
        sk.workspaceId = ws.wsId
        await store.save_skill(sk.skillId, ws.wsId, sk.model_dump(mode="json"))
    for w in body.get("workflows", []):
        from ..models.workflow import Workflow
        wf = Workflow(**w)
        wf.workspaceId = ws.wsId
        await store.save_workflow(wf.wfId, ws.wsId, wf.model_dump(mode="json"))
    logger.info("workspace imported: %s", ws.wsId)
    return ws


@router.delete("/{wsId}")
async def delete_workspace(wsId: str):
    store = get_store()
    data = await store.get_workspace(wsId)
    if not data:
        raise HTTPException(status_code=404, detail="workspace not found")
    await store.delete_workspace(wsId)
    logger.info("workspace deleted: %s", wsId)
    return {"success": True}
