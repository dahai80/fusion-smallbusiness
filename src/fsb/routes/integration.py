import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import fsb_config
from ..db.store import Store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace/{wsId}", tags=["integration"])


def get_store() -> Store:
    from ..app import app_state
    return app_state.store


class CreateArtifactRequest(BaseModel):
    name: str
    type: str = "text"
    content: str = ""
    projectId: Optional[str] = None
    runId: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SendToCanvasRequest(BaseModel):
    sessionId: Optional[str] = None
    outputDir: Optional[str] = None


class SyncToProjectRequest(BaseModel):
    projectId: str
    artifactIds: Optional[list[str]] = None


@router.post("/workflow/{wfId}/send-to-canvas")
async def send_to_canvas(wsId: str, wfId: str, body: SendToCanvasRequest = None):
    store = get_store()
    data = await store.get_workflow(wfId)
    if not data or data.get("workspaceId") != wsId:
        raise HTTPException(status_code=404, detail="workflow not found")

    session_id = body.sessionId if body and body.sessionId else wfId
    output_dir = body.outputDir if body and body.outputDir else f"exports/{session_id}"

    if fsb_config.STANDALONE_MODE:
        logger.info("send-to-canvas (standalone): wf=%s session=%s", wfId, session_id)
        return {
            "success": True,
            "sessionId": session_id,
            "exportedCount": 0,
            "exportPath": "",
            "standalone": True,
        }

    from ..engine.artifact_client import export_session
    result = await export_session(session_id=session_id, output_dir=output_dir)
    if not result.get("success"):
        logger.warning("send-to-canvas export failed: wf=%s session=%s err=%s",
                       wfId, session_id, result.get("message"))
        return {"success": False, "message": f"export failed: {result.get('message', 'unknown')}"}

    logger.info("send-to-canvas: wf=%s session=%s count=%d path=%s",
                wfId, session_id, result["data"].get("count", 0), result["data"].get("path", ""))
    return {
        "success": True,
        "sessionId": session_id,
        "exportedCount": result["data"].get("count", 0),
        "exportPath": result["data"].get("path", ""),
    }


@router.post("/sync-to-project")
async def sync_to_project(wsId: str, body: SyncToProjectRequest):
    store = get_store()
    ws = await store.get_workspace(wsId)
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")

    if fsb_config.STANDALONE_MODE:
        logger.info("sync-to-project (standalone): ws=%s project=%s", wsId, body.projectId)
        return {
            "success": True,
            "synced": 0,
            "failed": 0,
            "projectId": body.projectId,
            "standalone": True,
        }

    from ..engine.artifact_client import list_artifacts_by_source, move_artifact_to_kb

    artifact_ids = body.artifactIds
    if not artifact_ids:
        list_result = await list_artifacts_by_source(source_module="fsb", workspace_id=wsId)
        if not list_result.get("success"):
            raise HTTPException(status_code=502, detail=list_result.get("message", "failed to list artifacts"))
        artifact_ids = [a["id"] for a in list_result["data"] if "id" in a]

    if not artifact_ids:
        logger.info("sync-to-project: ws=%s no artifacts to sync", wsId)
        return {"success": True, "synced": 0, "projectId": body.projectId}

    synced = 0
    failed = 0
    for aid in artifact_ids:
        result = await move_artifact_to_kb(artifact_id=aid, project_id=body.projectId)
        if result.get("success"):
            synced += 1
        else:
            failed += 1
            logger.warning("sync-to-project: artifact=%s move failed: %s", aid, result.get("message"))

    logger.info("sync-to-project: ws=%s project=%s synced=%d failed=%d",
                wsId, body.projectId, synced, failed)
    return {
        "success": True,
        "synced": synced,
        "failed": failed,
        "projectId": body.projectId,
    }


@router.post("/create-artifact")
async def create_artifact(wsId: str, body: CreateArtifactRequest):
    store = get_store()
    ws = await store.get_workspace(wsId)
    if not ws:
        raise HTTPException(status_code=404, detail="workspace not found")

    if fsb_config.STANDALONE_MODE:
        logger.info("create-artifact (standalone): ws=%s name=%s", wsId, body.name)
        return {
            "success": True,
            "artifact": {
                "artifact_id": f"fsb_stub_{body.name}",
                "name": body.name,
                "type": body.type,
            },
            "standalone": True,
        }

    from ..engine.artifact_client import create_external_artifact
    result = await create_external_artifact(
        source_module="fsb",
        workspace_id=wsId,
        name=body.name,
        artifact_type=body.type,
        content=body.content,
        workflow_run_id=body.runId,
        project_id=body.projectId,
        metadata=body.metadata,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("message", "artifact creation failed"))
    return {"success": True, "artifact": result}
