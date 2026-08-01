import logging

from fastapi import APIRouter, HTTPException

from ..db.store import Store
from ..models.common import utc_now
from ..models.workflow import Workflow, WorkflowCreate, WorkflowUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace/{wsId}/workflow", tags=["workflow"])


def get_store() -> Store:
    from ..app import app_state
    return app_state.store


@router.get("", response_model=list[Workflow])
async def list_workflows(wsId: str, offset: int = 0, limit: int = 100):
    store = get_store()
    items = await store.list_workflows(wsId, offset=offset, limit=limit)
    return [Workflow(**d) for d in items]


@router.post("", response_model=Workflow)
async def create_workflow(wsId: str, body: WorkflowCreate):
    store = get_store()
    ws = await store.get_workspace(wsId)
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")
    wf = Workflow(workspaceId=wsId, **body.model_dump())
    await store.save_workflow(wf.wfId, wsId, wf.model_dump(mode="json"))
    ws["workflowIds"] = list(set(ws.get("workflowIds", []) + [wf.wfId]))
    await store.save_workspace(wsId, ws)
    logger.info("workflow created: %s in ws %s", wf.wfId, wsId)
    return wf


@router.get("/{wfId}", response_model=Workflow)
async def get_workflow(wsId: str, wfId: str):
    store = get_store()
    data = await store.get_workflow(wfId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="workflow not found")
    return Workflow(**data)


@router.put("/{wfId}", response_model=Workflow)
async def update_workflow(wsId: str, wfId: str, body: WorkflowUpdate):
    store = get_store()
    data = await store.get_workflow(wfId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="workflow not found")
    wf = Workflow(**data)
    update = body.model_dump(exclude_unset=True)
    for k, v in update.items():
        setattr(wf, k, v)
    wf.updateTime = utc_now()
    await store.save_workflow(wf.wfId, wsId, wf.model_dump(mode="json"))
    logger.info("workflow updated: %s", wfId)
    return wf


@router.delete("/{wfId}")
async def delete_workflow(wsId: str, wfId: str):
    store = get_store()
    data = await store.get_workflow(wfId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="workflow not found")
    await store.delete_workflow(wfId)
    ws = await store.get_workspace(wsId)
    if ws:
        ws["workflowIds"] = [w for w in ws.get("workflowIds", []) if w != wfId]
        await store.save_workspace(wsId, ws)
    logger.info("workflow deleted: %s", wfId)
    return {"success": True}


@router.post("/{wfId}/run")
async def run_workflow(wsId: str, wfId: str, body: dict = None):
    store = get_store()
    data = await store.get_workflow(wfId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="workflow not found")
    from ..engine.runner import WorkflowRunner
    runner = WorkflowRunner(store)
    input_data = (body or {}).get("inputData", {})
    triggered_by = (body or {}).get("triggeredBy", "")
    try:
        run = await runner.start(wsId, wfId, input_data=input_data, triggered_by=triggered_by)
        logger.info("workflow run started: %s for wf %s", run.runId, wfId)
        return run.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{wfId}/schedule")
async def set_schedule(wsId: str, wfId: str, body: dict):
    store = get_store()
    data = await store.get_workflow(wfId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="workflow not found")
    wf = Workflow(**data)
    from ..models.workflow import ScheduleConfig
    from ..models.common import ScheduleType
    sched = ScheduleConfig(
        type=ScheduleType(body.get("type", "cron")),
        cron=body.get("cron"),
        eventTrigger=body.get("eventTrigger"),
    )
    wf.schedule = sched
    wf.updateTime = utc_now()
    await store.save_workflow(wf.wfId, wsId, wf.model_dump(mode="json"))
    logger.info("workflow schedule set: %s type=%s cron=%s", wfId, sched.type, sched.cron)
    return {"success": True, "schedule": sched.model_dump(mode="json")}


@router.delete("/{wfId}/schedule/{scheduleId}")
async def delete_schedule(wsId: str, wfId: str, scheduleId: str):
    store = get_store()
    data = await store.get_workflow(wfId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="workflow not found")
    wf = Workflow(**data)
    from ..models.workflow import ScheduleConfig
    from ..models.common import ScheduleType
    wf.schedule = ScheduleConfig(type=ScheduleType.MANUAL)
    wf.updateTime = utc_now()
    await store.save_workflow(wf.wfId, wsId, wf.model_dump(mode="json"))
    logger.info("workflow schedule deleted: %s", wfId)
    return {"success": True}


@router.post("/import", response_model=Workflow)
async def import_workflow(wsId: str, body: dict):
    store = get_store()
    ws = await store.get_workspace(wsId)
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")
    wf = Workflow(workspaceId=wsId, **body)
    await store.save_workflow(wf.wfId, wsId, wf.model_dump(mode="json"))
    ws["workflowIds"] = list(set(ws.get("workflowIds", []) + [wf.wfId]))
    await store.save_workspace(wsId, ws)
    logger.info("workflow imported: %s into ws %s", wf.wfId, wsId)
    return wf


@router.post("/{wfId}/export")
async def export_workflow(wsId: str, wfId: str):
    store = get_store()
    data = await store.get_workflow(wfId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="workflow not found")
    logger.info("workflow exported: %s", wfId)
    return data
