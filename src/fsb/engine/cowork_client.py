import json
import logging
from typing import Any, Optional

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
