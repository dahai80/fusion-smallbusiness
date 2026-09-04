import logging

from ..config import fsb_config
from .http_pool import acquire_client

logger = logging.getLogger(__name__)


async def notify_run_completed(workspace_id: str, agent_id: str, run: dict) -> dict:
    if not agent_id:
        logger.info("chat notify skipped: no agent bound ws=%s", workspace_id)
        return {"status": "skipped", "reason": "no agent bound"}
    url = f"{fsb_config.FUSION_CHAT_URL}/api/v1/chat/notify"
    payload = {
        "workspaceId": workspace_id,
        "agentId": agent_id,
        "event": "run.completed",
        "run": run,
    }
    try:
        async with acquire_client(fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code < 300:
                logger.info("chat notify sent: ws=%s agent=%s run=%s", workspace_id, agent_id, run.get("runId"))
                return {"status": "success", "statusCode": resp.status_code}
            logger.warning("chat notify rejected: ws=%s agent=%s status=%s", workspace_id, agent_id, resp.status_code)
            return {"status": "error", "statusCode": resp.status_code, "message": resp.text}
    except Exception as e:
        logger.warning("chat notify failed (stub fallback): ws=%s agent=%s error=%s", workspace_id, agent_id, e)
        return {"status": "error", "message": str(e)}


async def bind_agent(workspace_id: str, agent_id: str) -> dict:
    url = f"{fsb_config.FUSION_CHAT_URL}/api/v1/chat/agent/bind"
    payload = {"workspaceId": workspace_id, "agentId": agent_id}
    try:
        async with acquire_client(fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code < 300:
                logger.info("chat agent bound: ws=%s agent=%s", workspace_id, agent_id)
                return {"status": "success", "statusCode": resp.status_code}
            logger.warning("chat agent bind rejected: status=%s", resp.status_code)
            return {"status": "error", "statusCode": resp.status_code, "message": resp.text}
    except Exception as e:
        logger.warning("chat agent bind failed (stub fallback): ws=%s error=%s", workspace_id, e)
        return {"status": "error", "message": str(e)}


async def unbind_agent(workspace_id: str, agent_id: str) -> dict:
    url = f"{fsb_config.FUSION_CHAT_URL}/api/v1/chat/agent/unbind"
    payload = {"workspaceId": workspace_id, "agentId": agent_id}
    try:
        async with acquire_client(fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code < 300:
                logger.info("chat agent unbound: ws=%s agent=%s", workspace_id, agent_id)
                return {"status": "success", "statusCode": resp.status_code}
            logger.warning("chat agent unbind rejected: status=%s", resp.status_code)
            return {"status": "error", "statusCode": resp.status_code, "message": resp.text}
    except Exception as e:
        logger.warning("chat agent unbind failed (stub fallback): ws=%s error=%s", workspace_id, e)
        return {"status": "error", "message": str(e)}
