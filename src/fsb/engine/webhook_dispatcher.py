import hashlib
import hmac
import json
import logging

from .http_pool import acquire_client
from .url_guard import resolve_pinned_url

logger = logging.getLogger(__name__)


async def dispatch_webhook(webhook: dict, event: str, payload: dict):
    url = webhook.get("url", "")
    if not url:
        logger.warning("webhook %s has no url, skipping", webhook.get("webhookId"))
        return False

    pinned_url, original_host = resolve_pinned_url(url)
    if not pinned_url:
        logger.warning(
            "webhook %s url rejected by url_guard (ssrf/private/loopback): %s",
            webhook.get("webhookId"),
            url,
        )
        return False

    body = {
        "event": event,
        "webhookId": webhook.get("webhookId"),
        "timestamp": payload.get("endTime", ""),
        "data": payload,
    }

    headers = {"Content-Type": "application/json"}
    if original_host:
        headers["Host"] = original_host
    from ..config import fsb_config
    from .secret_crypto import decrypt_secret

    secret = decrypt_secret(webhook.get("secret", ""), fsb_config.SECRET_KEY)
    if secret:
        raw = json.dumps(body, default=str, sort_keys=True)
        sig = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
        headers["X-FSB-Signature"] = f"sha256={sig}"

    try:
        async with acquire_client(10.0) as client:
            resp = await client.post(pinned_url, json=body, headers=headers, timeout=10.0)
            logger.info(
                "webhook dispatched: %s -> %s status=%d",
                webhook.get("webhookId"),
                url,
                resp.status_code,
            )
            return resp.status_code < 300
    except Exception as e:
        logger.error("webhook dispatch failed: %s -> %s error=%s", webhook.get("webhookId"), url, e)
        return False
