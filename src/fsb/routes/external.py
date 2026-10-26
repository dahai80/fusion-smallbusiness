import logging

from fastapi import APIRouter, Depends, HTTPException

from ..db.store import Store
from ..models.event import EventSubscription, EventTrigger
from ..models.webhook import Webhook
from ..tenant_dep import require_admin, require_tenant_owns, require_tenant_present

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/external", tags=["external"], dependencies=[Depends(require_tenant_present)])


def get_store() -> Store:
    from ..app import app_state

    return app_state.store


def _encrypt_webhook_secret(secret: str) -> str:
    from ..config import fsb_config
    from ..engine.secret_crypto import encrypt_secret

    return encrypt_secret(secret, fsb_config.SECRET_KEY)


def _decrypt_webhook_secret(stored: str) -> str:
    from ..config import fsb_config
    from ..engine.secret_crypto import decrypt_secret

    return decrypt_secret(stored, fsb_config.SECRET_KEY)


def _redact_webhook(data: dict) -> dict:
    out = {**data}
    if out.get("secret"):
        out["secret"] = "***"
    return out


@router.post("/workflow/{wfId}/trigger")
async def external_trigger(wfId: str, body: dict | None = None):
    store = get_store()
    data = await store.get_workflow(wfId)
    if not data:
        raise HTTPException(status_code=404, detail="workflow not found")
    ws_id = data["workspaceId"]
    require_tenant_owns(ws_id)
    from ..engine.runner import WorkflowRunner

    runner = WorkflowRunner(store)
    input_data = (body or {}).get("inputData", {})
    run = await runner.start(ws_id, wfId, input_data=input_data, triggered_by="external_api")
    logger.info("external trigger: wf %s run %s", wfId, run.runId)
    return run.model_dump(mode="json")


@router.get("/workflow/{wfId}/status")
async def external_status(wfId: str):
    store = get_store()
    data = await store.get_workflow(wfId)
    if not data:
        raise HTTPException(status_code=404, detail="workflow not found")
    ws_id = data["workspaceId"]
    require_tenant_owns(ws_id)
    runs = await store.list_runs(ws_id, wf_id=wfId)
    latest = runs[-1] if runs else None
    return {
        "wfId": wfId,
        "latestRun": latest,
    }


@router.post("/event")
async def post_event(body: dict):
    store = get_store()
    event = EventTrigger(
        eventType=body.get("eventType", ""),
        source=body.get("source", ""),
        payload=body.get("payload", {}),
        workspaceId=body.get("workspaceId", ""),
    )
    if not event.eventType:
        raise HTTPException(status_code=400, detail="eventType is required")
    if not event.workspaceId:
        raise HTTPException(status_code=400, detail="workspaceId is required (cross-tenant broadcast disabled)")
    require_tenant_owns(event.workspaceId)
    from ..engine.event_bus import EventBus

    bus = EventBus(store)
    triggered = await bus.publish(event)
    logger.info("event received: %s triggered %d workflows", event.eventId, len(triggered))
    return {"eventId": event.eventId, "triggered": triggered}


@router.post("/event/subscription")
async def create_subscription(body: dict):
    store = get_store()
    sub = EventSubscription(
        workspaceId=body.get("workspaceId", ""),
        workflowId=body.get("workflowId", ""),
        eventType=body.get("eventType", ""),
        source=body.get("source"),
        enabled=body.get("enabled", True),
    )
    if not sub.workspaceId or not sub.workflowId or not sub.eventType:
        raise HTTPException(status_code=400, detail="workspaceId, workflowId, eventType are required")
    require_tenant_owns(sub.workspaceId)
    require_admin()
    await store.save_subscription(sub.subId, sub.workspaceId, sub.model_dump(mode="json"))
    logger.info("subscription created: %s eventType=%s wf=%s", sub.subId, sub.eventType, sub.workflowId)
    return sub.model_dump(mode="json")


@router.get("/event/subscription")
async def list_subscriptions(wsId: str, offset: int = 0, limit: int = 100):
    store = get_store()
    require_tenant_owns(wsId)
    items = await store.list_subscriptions(wsId, offset=offset, limit=limit)
    return items


@router.delete("/event/subscription/{subId}")
async def delete_subscription(subId: str):
    store = get_store()
    data = await store.get_subscription(subId)
    if not data:
        raise HTTPException(status_code=404, detail="subscription not found")
    require_tenant_owns(data.get("workspaceId", ""))
    require_admin()
    await store.delete_subscription(subId)
    logger.info("subscription deleted: %s", subId)
    return {"success": True}


@router.post("/webhook/register")
async def register_webhook(body: dict):
    store = get_store()
    wh = Webhook(
        workspaceId=body.get("workspaceId", ""),
        url=body.get("url", ""),
        events=body.get("events", ["run.completed"]),
        secret=body.get("secret", ""),
        enabled=body.get("enabled", True),
    )
    if not wh.workspaceId or not wh.url:
        raise HTTPException(status_code=400, detail="workspaceId and url are required")
    from ..engine.url_guard import validate_outbound_url

    ok, reason = validate_outbound_url(wh.url)
    if not ok:
        raise HTTPException(status_code=400, detail=f"webhook url not allowed: {reason}")
    require_tenant_owns(wh.workspaceId)
    require_admin()
    persist = wh.model_dump(mode="json")
    persist["secret"] = _encrypt_webhook_secret(persist.get("secret", ""))
    await store.save_webhook(wh.webhookId, wh.workspaceId, persist)
    logger.info("webhook registered: %s url=%s", wh.webhookId, wh.url)
    return _redact_webhook(wh.model_dump(mode="json"))


@router.get("/webhook")
async def list_webhooks(wsId: str, offset: int = 0, limit: int = 100):
    store = get_store()
    require_tenant_owns(wsId)
    items = await store.list_webhooks(wsId, offset=offset, limit=limit)
    return [_redact_webhook(d) for d in items]


@router.delete("/webhook/{webhookId}")
async def delete_webhook(webhookId: str):
    store = get_store()
    data = await store.get_webhook(webhookId)
    if not data:
        raise HTTPException(status_code=404, detail="webhook not found")
    require_tenant_owns(data.get("workspaceId", ""))
    require_admin()
    await store.delete_webhook(webhookId)
    logger.info("webhook deleted: %s", webhookId)
    return {"success": True}
