import logging

from fastapi import APIRouter, HTTPException

from ..db.store import Store
from ..models.common import ApprovalAction
from ..models.execution import ApprovalRecord, PendingTask, RunInstance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace/{wsId}", tags=["execution"])


def get_store() -> Store:
    from ..app import app_state
    return app_state.store


@router.get("/task/pending", response_model=list[PendingTask])
async def list_pending_tasks(wsId: str, offset: int = 0, limit: int = 100):
    store = get_store()
    items = await store.list_pending_tasks(wsId, offset=offset, limit=limit)
    return [PendingTask(**d) for d in items]


@router.post("/task/{taskId}/approve")
async def approve_task(wsId: str, taskId: str):
    store = get_store()
    data = await store.get_task(taskId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="task not found")
    task = PendingTask(**data)
    task.status = "approved"
    await store.save_task(taskId, wsId, task.runId, task.model_dump(mode="json"))

    run_data = await store.get_run(task.runId)
    if run_data:
        run = RunInstance(**run_data)
        record = ApprovalRecord(taskId=taskId, action=ApprovalAction.APPROVE)
        run.approvalRecord.append(record)
        await store.save_run(run.runId, wsId, run.workflowId, run.model_dump(mode="json"))

        from ..engine.runner import WorkflowRunner
        runner = WorkflowRunner(store)
        await runner.resume(run.runId, "approved")
        logger.info("task approved: %s run %s", taskId, task.runId)
    return {"success": True, "action": "approved"}


@router.post("/task/{taskId}/deny")
async def deny_task(wsId: str, taskId: str):
    store = get_store()
    data = await store.get_task(taskId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="task not found")
    task = PendingTask(**data)
    task.status = "denied"
    await store.save_task(taskId, wsId, task.runId, task.model_dump(mode="json"))

    run_data = await store.get_run(task.runId)
    if run_data:
        run = RunInstance(**run_data)
        record = ApprovalRecord(taskId=taskId, action=ApprovalAction.DENY)
        run.approvalRecord.append(record)
        await store.save_run(run.runId, wsId, run.workflowId, run.model_dump(mode="json"))

        from ..engine.runner import WorkflowRunner
        runner = WorkflowRunner(store)
        await runner.resume(run.runId, "denied")
        logger.info("task denied: %s run %s", taskId, task.runId)
    return {"success": True, "action": "denied"}


@router.post("/task/{taskId}/edit")
async def edit_task(wsId: str, taskId: str, body: dict):
    store = get_store()
    data = await store.get_task(taskId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="task not found")
    task = PendingTask(**data)
    task.status = "approved"
    edit_content = body.get("editContent", {})
    await store.save_task(taskId, wsId, task.runId, task.model_dump(mode="json"))

    run_data = await store.get_run(task.runId)
    if run_data:
        run = RunInstance(**run_data)
        record = ApprovalRecord(
            taskId=taskId,
            action=ApprovalAction.EDIT,
            editContent=edit_content,
        )
        run.approvalRecord.append(record)
        if edit_content:
            run.contextSandbox.inputData.update(edit_content)
        await store.save_run(run.runId, wsId, run.workflowId, run.model_dump(mode="json"))

        from ..engine.runner import WorkflowRunner
        runner = WorkflowRunner(store)
        await runner.resume(run.runId, "approved")
        logger.info("task edited+approved: %s run %s", taskId, task.runId)
    return {"success": True, "action": "edit"}


@router.get("/execution/history")
async def execution_history(wsId: str, workflowId: str | None = None, offset: int = 0, limit: int = 100):
    store = get_store()
    items = await store.list_runs(wsId, wf_id=workflowId, offset=offset, limit=limit)
    return items





@router.get("/execution/export")
async def export_execution_log(wsId: str):
    store = get_store()
    items = await store.list_runs(wsId)
    logger.info("execution log exported for ws %s, %d records", wsId, len(items))
    return {"workspaceId": wsId, "records": items, "count": len(items)}


@router.get("/execution/{runId}")
async def get_execution(wsId: str, runId: str):
    store = get_store()
    data = await store.get_run(runId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="run not found")
    return data
