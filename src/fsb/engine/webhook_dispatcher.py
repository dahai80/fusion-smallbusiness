import hashlib
import hmac
import json
import logging

import httpx

logger = logging.getLogger(__name__)


async def dispatch_webhook(webhook: dict, event: str, payload: dict):
    url = webhook.get("url", "")
    if not url:
        logger.warning("webhook %s has no url, skipping", webhook.get("webhookId"))
        return False

    body = {
        "event": event,
        "webhookId": webhook.get("webhookId"),
        "timestamp": payload.get("endTime", ""),
        "data": payload,
    }

    headers = {"Content-Type": "application/json"}
    secret = webhook.get("secret", "")
    if secret:
        raw = json.dumps(body, default=str, sort_keys=True)
        sig = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
        headers["X-FSB-Signature"] = f"sha256={sig}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=body, headers=headers)
            logger.info(
                "webhook dispatched: %s -> %s status=%d",
                webhook.get("webhookId"), url, resp.status_code,
            )
            return resp.status_code < 300
    except Exception as e:
        logger.error("webhook dispatch failed: %s -> %s error=%s", webhook.get("webhookId"), url, e)
        return False
