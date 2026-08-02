import logging

from fastapi import APIRouter, HTTPException

from ..db.store import Store
from ..models.common import Variable
from ..models.workspace import Workspace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace/{wsId}", tags=["variable"])


def get_store() -> Store:
    from ..app import app_state
    return app_state.store


@router.get("/variable", response_model=list[Variable])
async def list_variables(wsId: str):
    store = get_store()
    data = await store.get_workspace(wsId)
    if not data:
        raise HTTPException(status_code=404, detail="workspace not found")
    return data.get("variables", [])


@router.put("/variable")
async def update_variables(wsId: str, body: list[dict]):
    store = get_store()
    data = await store.get_workspace(wsId)
    if not data:
        raise HTTPException(status_code=404, detail="workspace not found")
    ws = Workspace(**data)
    var_map = {v.key: v for v in ws.variables}
    for item in body:
        var = Variable(**item)
        var_map[var.key] = var
    ws.variables = list(var_map.values())
    from ..models.common import utc_now
    ws.updateTime = utc_now()
    await store.save_workspace(ws.wsId, ws.model_dump(mode="json"))
    logger.info("variables updated for ws %s: %d vars", wsId, len(ws.variables))
    return ws.variables


@router.get("/template")
async def list_templates(wsId: str):
    store = get_store()
    items = await store.list_templates(wsId)
    return items


@router.post("/template")
async def create_template(wsId: str, body: dict):
    store = get_store()
    ws = await store.get_workspace(wsId)
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")
    from ..models.common import gen_id, utc_now
    tpl_id = gen_id("tpl")
    tpl = {
        "templateId": tpl_id,
        "workspaceId": wsId,
        "name": body.get("name", "unnamed"),
        "category": body.get("category", ""),
        "description": body.get("description", ""),
        "data": body.get("data", {}),
        "graphDefinition": body.get("graphDefinition"),
        "createTime": utc_now().isoformat(),
    }
    await store.save_template(tpl_id, wsId, tpl)
    logger.info("template created: %s in ws %s", tpl_id, wsId)
    return tpl


@router.delete("/template/{templateId}")
async def delete_template(wsId: str, templateId: str):
    store = get_store()
    data = await store.get_template(templateId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="template not found")
    await store.delete_template(templateId)
    logger.info("template deleted: %s from ws %s", templateId, wsId)
    return {"success": True}
