import logging
from typing import Any, Optional

import httpx

from ..config import fsb_config

logger = logging.getLogger(__name__)


async def list_connectors() -> dict[str, Any]:
    url = f"{fsb_config.FUSION_GATEWAY_URL}/gateway/v1/connector/list"
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error("gateway list connectors failed: %s", e)
        return {"success": False, "code": -1, "message": str(e)}
    except Exception as e:
        logger.error("gateway list connectors unexpected error: %s", e)
        return {"success": False, "code": -1, "message": str(e)}


async def execute_action(
    connector_key: str,
    action_key: str,
    params: dict = None,
    connection_id: str = "",
) -> dict[str, Any]:
    url = f"{fsb_config.FUSION_GATEWAY_URL}/gateway/v1/connector/{connector_key}/action/{action_key}"
    payload: dict[str, Any] = {"params": params or {}}
    headers: dict[str, str] = {}
    if connection_id:
        headers["X-Fusion-Connection-Id"] = connection_id
        payload["connectionId"] = connection_id

    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            result = resp.json()
            if result.get("success"):
                logger.info("gateway action ok: %s/%s", connector_key, action_key)
            else:
                logger.warning("gateway action failed: %s/%s code=%s msg=%s",
                               connector_key, action_key, result.get("code"), result.get("message"))
            return result
    except httpx.HTTPError as e:
        logger.error("gateway action failed: %s/%s error=%s", connector_key, action_key, e)
        return {"success": False, "code": -1, "message": str(e)}
    except Exception as e:
        logger.error("gateway action unexpected error: %s/%s %s", connector_key, action_key, e)
        return {"success": False, "code": -1, "message": str(e)}


async def test_action(
    connector_key: str,
    action_key: str,
    params: dict = None,
) -> dict[str, Any]:
    url = f"{fsb_config.FUSION_GATEWAY_URL}/gateway/v1/connector/test"
    payload = {
        "connectorKey": connector_key,
        "actionKey": action_key,
        "params": params or {},
        "testMode": True,
    }
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error("gateway test action failed: %s/%s error=%s", connector_key, action_key, e)
        return {"success": False, "code": -1, "message": str(e)}
    except Exception as e:
        logger.error("gateway test action unexpected error: %s/%s %s", connector_key, action_key, e)
        return {"success": False, "code": -1, "message": str(e)}


async def list_connections() -> dict[str, Any]:
    url = f"{fsb_config.FUSION_GATEWAY_URL}/gateway/v1/connection"
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error("gateway list connections failed: %s", e)
        return {"success": False, "code": -1, "message": str(e)}
    except Exception as e:
        logger.error("gateway list connections unexpected error: %s", e)
        return {"success": False, "code": -1, "message": str(e)}


async def create_connection(
    connection_id: str,
    connector_key: str,
    auth_type: str = "oauth2",
    status: str = "active",
    expires_at: Optional[str] = None,
) -> dict[str, Any]:
    url = f"{fsb_config.FUSION_GATEWAY_URL}/gateway/v1/connection"
    payload: dict[str, Any] = {
        "id": connection_id,
        "connectorKey": connector_key,
        "authType": auth_type,
        "status": status,
    }
    if expires_at:
        payload["expiresAt"] = expires_at

    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            logger.info("gateway connection created: id=%s connector=%s", connection_id, connector_key)
            return result
    except httpx.HTTPError as e:
        logger.error("gateway create connection failed: id=%s error=%s", connection_id, e)
        return {"success": False, "code": -1, "message": str(e)}
    except Exception as e:
        logger.error("gateway create connection unexpected error: %s", e)
        return {"success": False, "code": -1, "message": str(e)}


async def get_connection(connection_id: str) -> dict[str, Any]:
    url = f"{fsb_config.FUSION_GATEWAY_URL}/gateway/v1/connection/{connection_id}"
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error("gateway get connection failed: id=%s error=%s", connection_id, e)
        return {"success": False, "code": -1, "message": str(e)}
    except Exception as e:
        logger.error("gateway get connection unexpected error: %s", e)
        return {"success": False, "code": -1, "message": str(e)}


async def delete_connection(connection_id: str) -> dict[str, Any]:
    url = f"{fsb_config.FUSION_GATEWAY_URL}/gateway/v1/connection/{connection_id}"
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.delete(url)
            if resp.status_code == 204:
                logger.info("gateway connection deleted: id=%s", connection_id)
                return {"success": True}
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        logger.error("gateway delete connection failed: id=%s error=%s", connection_id, e)
        return {"success": False, "code": -1, "message": str(e)}
    except Exception as e:
        logger.error("gateway delete connection unexpected error: %s", e)
        return {"success": False, "code": -1, "message": str(e)}


async def refresh_connection(connection_id: str) -> dict[str, Any]:
    url = f"{fsb_config.FUSION_GATEWAY_URL}/gateway/v1/connection/{connection_id}/refresh"
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.post(url)
            resp.raise_for_status()
            result = resp.json()
            logger.info("gateway connection refreshed: id=%s", connection_id)
            return result
    except httpx.HTTPError as e:
        logger.error("gateway refresh connection failed: id=%s error=%s", connection_id, e)
        return {"success": False, "code": -1, "message": str(e)}
    except Exception as e:
        logger.error("gateway refresh connection unexpected error: %s", e)
        return {"success": False, "code": -1, "message": str(e)}


async def initiate_oauth2(
    connector_key: str,
    redirect_uri: str,
    state: str = "",
    scope: str = "",
) -> dict[str, Any]:
    url = f"{fsb_config.FUSION_GATEWAY_URL}/gateway/v1/oauth2/authorize"
    params: dict[str, str] = {
        "connectorKey": connector_key,
        "redirectUri": redirect_uri,
    }
    if state:
        params["state"] = state
    if scope:
        params["scope"] = scope
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            result = resp.json()
            logger.info("oauth2 authorize initiated: connector=%s", connector_key)
            return result
    except httpx.HTTPError as e:
        logger.error("oauth2 authorize failed: connector=%s error=%s", connector_key, e)
        return {"success": False, "code": -1, "message": str(e)}
    except Exception as e:
        logger.error("oauth2 authorize unexpected error: connector=%s %s", connector_key, e)
        return {"success": False, "code": -1, "message": str(e)}


async def handle_oauth2_callback(
    code: str,
    state: str = "",
) -> dict[str, Any]:
    url = f"{fsb_config.FUSION_GATEWAY_URL}/gateway/v1/oauth2/callback"
    params: dict[str, str] = {"code": code}
    if state:
        params["state"] = state
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            result = resp.json()
            logger.info("oauth2 callback handled: state=%s", state)
            return result
    except httpx.HTTPError as e:
        logger.error("oauth2 callback failed: code=%s error=%s", code[:8], e)
        return {"success": False, "code": -1, "message": str(e)}
    except Exception as e:
        logger.error("oauth2 callback unexpected error: %s", e)
        return {"success": False, "code": -1, "message": str(e)}
