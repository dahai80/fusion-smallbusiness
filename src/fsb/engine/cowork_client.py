import logging
from typing import Any

import httpx

from ..config import fsb_config

logger = logging.getLogger(__name__)

_RPC_ID_COUNTER = 0


def _next_rpc_id() -> int:
    global _RPC_ID_COUNTER
    _RPC_ID_COUNTER += 1
    return _RPC_ID_COUNTER


async def _rpc_call(method: str, params: dict) -> dict[str, Any]:
    url = f"{fsb_config.FUSION_COWORK_URL}/rpc"
    payload = {
        "jsonrpc": "2.0",
        "id": _next_rpc_id(),
        "method": method,
        "params": params,
    }
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if "error" in result:
                logger.error("cowork rpc error: method=%s error=%s", method, result["error"])
                return {"status": "error", "message": str(result["error"])}
            return {"status": "success", "data": result.get("result", {})}
    except httpx.HTTPError as e:
        logger.error("cowork rpc call failed: method=%s error=%s", method, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error("cowork rpc unexpected error: method=%s %s", method, e)
        return {"status": "error", "message": str(e)}


async def register_module(
    module_id: str,
    name: str,
    icon: str = "",
    route_path: str = "",
    enabled: bool = True,
    metadata: dict = None,
) -> dict[str, Any]:
    result = await _rpc_call("desk.module.register", {
        "module_id": module_id,
        "name": name,
        "icon": icon,
        "route_path": route_path,
        "enabled": enabled,
        "metadata": metadata or {},
    })
    if result.get("status") == "success":
        logger.info("cowork module registered: id=%s name=%s", module_id, name)
    return result


async def push_notification(
    space_id: str,
    user_id: str,
    notification_type: str,
    title: str,
    content: str = "",
    metadata: dict = None,
) -> dict[str, Any]:
    result = await _rpc_call("desk.notification.push", {
        "space_id": space_id,
        "user_id": user_id,
        "notification_type": notification_type,
        "title": title,
        "content": content,
        "metadata": metadata or {},
    })
    if result.get("status") == "success":
        logger.info("cowork notification pushed: space=%s user=%s type=%s", space_id, user_id, notification_type)
    return result


async def sync_knowledge(
    space_id: str,
    files: list[dict],
) -> dict[str, Any]:
    result = await _rpc_call("desk.project.syncKnowledge", {
        "spaceId": space_id,
        "files": files,
    })
    if result.get("status") == "success":
        logger.info("cowork knowledge synced: space=%s files=%d", space_id, len(files))
    return result


async def import_snapshot(
    space_id: str,
    snapshot: dict,
) -> dict[str, Any]:
    result = await _rpc_call("desk.project.importSnapshot", {
        "spaceId": space_id,
        "snapshot": snapshot,
    })
    if result.get("status") == "success":
        logger.info("cowork snapshot imported: space=%s title=%s", space_id, snapshot.get("title", ""))
    return result


async def export_to_project(
    space_id: str,
    items: dict,
    target_project_id: str,
) -> dict[str, Any]:
    result = await _rpc_call("desk.project.exportToProject", {
        "spaceId": space_id,
        "items": items,
        "targetProjectId": target_project_id,
    })
    if result.get("status") == "success":
        logger.info("cowork exported to project: space=%s project=%s", space_id, target_project_id)
    return result
