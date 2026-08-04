import logging
from typing import Any

import httpx

from ..config import fsb_config

logger = logging.getLogger(__name__)


async def create_external_artifact(
    source_module: str,
    workspace_id: str,
    name: str,
    artifact_type: str,
    content: str,
    workflow_run_id: str | None = None,
    summary: str = "",
    kind: str | None = None,
    project_id: str | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    url = f"{fsb_config.ARTIFACTS_ENGINE_URL}/api/v1/external/create"
    payload = {
        "source_module": source_module,
        "workspace_id": workspace_id,
        "name": name,
        "type": artifact_type,
        "content": content,
        "summary": summary,
        "kind": kind,
        "project_id": project_id,
        "metadata": metadata or {},
    }
    if workflow_run_id:
        payload["workflow_run_id"] = workflow_run_id

    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            logger.info(
                "artifact created: id=%s name=%s source=%s",
                result.get("artifact_id"), name, source_module,
            )
            return result
    except httpx.HTTPError as e:
        logger.error("artifact creation failed: %s error=%s", name, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error("artifact creation unexpected error: %s", e)
        return {"status": "error", "message": str(e)}


async def export_session(session_id: str, output_dir: str) -> dict[str, Any]:
    url = f"{fsb_config.ARTIFACTS_ENGINE_URL}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "artifact.export_session",
        "params": {"session_id": session_id, "output_dir": output_dir},
    }
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT * 3) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if "error" in result:
                logger.error("export session rpc error: session=%s err=%s", session_id, result["error"])
                return {"success": False, "message": result["error"].get("message", "rpc error")}
            data = result.get("result", {})
            logger.info("export session: session=%s count=%d path=%s",
                        session_id, data.get("count", 0), data.get("path", ""))
            return {"success": True, "data": data}
    except httpx.HTTPError as e:
        logger.error("export session failed: session=%s error=%s", session_id, e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("export session unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def move_artifact_to_kb(artifact_id: str, project_id: str) -> dict[str, Any]:
    url = f"{fsb_config.ARTIFACTS_ENGINE_URL}/api/v1/artifacts/{artifact_id}"
    payload = {"action": "move_to_kb", "project_id": project_id}
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            ok = result.get("ok", False)
            logger.info("move artifact to kb: artifact=%s project=%s ok=%s", artifact_id, project_id, ok)
            return {"success": ok, "data": result}
    except httpx.HTTPError as e:
        logger.error("move artifact to kb failed: artifact=%s project=%s error=%s", artifact_id, project_id, e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("move artifact to kb unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def list_artifacts_by_source(source_module: str, workspace_id: str = "") -> dict[str, Any]:
    url = f"{fsb_config.ARTIFACTS_ENGINE_URL}/api/v1/external"
    params: dict[str, str] = {"source_module": source_module}
    if workspace_id:
        params["workspace_id"] = workspace_id
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            result = resp.json()
            artifacts = result.get("artifacts", [])
            logger.info("list artifacts by source: module=%s ws=%s count=%d",
                        source_module, workspace_id, len(artifacts))
            return {"success": True, "data": artifacts}
    except httpx.HTTPError as e:
        logger.error("list artifacts by source failed: module=%s error=%s", source_module, e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("list artifacts by source unexpected error: %s", e)
        return {"success": False, "message": str(e)}
