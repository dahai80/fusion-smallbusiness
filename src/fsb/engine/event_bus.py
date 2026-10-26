import logging

from ..config import fsb_config
from ..db.store import Store
from ..models.common import TriggerType
from ..models.event import EventTrigger

logger = logging.getLogger(__name__)

_EVENT_DEPTH_LIMIT = 5
_event_depth: dict[str, int] = {}
_recent_event_ids: dict[str, float] = {}
_DEDUP_TTL = 60.0


class EventBus:
    def __init__(self, store: Store):
        self.store = store

    async def _is_duplicate(self, event: EventTrigger) -> bool:
        if fsb_config.DB_BACKEND == "postgres" or fsb_config.RATE_LIMIT_DISTRIBUTED:
            try:
                ttl = max(60, fsb_config.EVENT_DEDUP_TTL)
                return await self.store.event_seen(event.eventId, event.workspaceId or "_global", ttl)
            except Exception as e:
                logger.warning("distributed dedup failed, falling back to in-memory: %s", e)
        import time

        now = time.monotonic()
        stale = [k for k, ts in _recent_event_ids.items() if now - ts > _DEDUP_TTL]
        for k in stale:
            _recent_event_ids.pop(k, None)
        if event.eventId in _recent_event_ids:
            return True
        _recent_event_ids[event.eventId] = now
        return False

    async def publish(self, event: EventTrigger) -> list[dict]:
        if await self._is_duplicate(event):
            logger.warning("event deduplicated (already processed): %s", event.eventId)
            return []

        await self.store.save_event(event.eventId, event.workspaceId, event.model_dump(mode="json"))
        logger.info(
            "event published: %s type=%s source=%s ws=%s",
            event.eventId,
            event.eventType,
            event.source,
            event.workspaceId,
        )

        if not event.workspaceId:
            logger.warning("event %s has no workspaceId — cross-tenant broadcast disabled, no triggers", event.eventId)
            return []

        depth = _event_depth.get(event.eventType, 0)
        if depth >= _EVENT_DEPTH_LIMIT:
            logger.error("event %s exceeds depth limit %d — dropping to break loop", event.eventType, depth)
            return []

        subs = await self.store.find_matching_subscriptions(event.eventType, event.source, ws_id=event.workspaceId)
        subs = [s for s in subs if s.get("workspaceId") == event.workspaceId]

        _event_depth[event.eventType] = depth + 1
        triggered = []
        try:
            for sub in subs:
                wf_id = sub.get("workflowId")
                ws_id = sub.get("workspaceId")
                if not wf_id or not ws_id:
                    continue
                try:
                    from .runner import WorkflowRunner

                    runner = WorkflowRunner(self.store)
                    run = await runner.start(
                        ws_id,
                        wf_id,
                        trigger_type=TriggerType.EVENT,
                        triggered_by=f"event:{event.eventId}",
                        input_data=event.payload,
                    )
                    triggered.append({"subId": sub.get("subId"), "runId": run.runId, "wfId": wf_id})
                    logger.info("event triggered workflow: sub=%s wf=%s run=%s", sub.get("subId"), wf_id, run.runId)
                except Exception as e:
                    logger.error("event trigger failed: sub=%s wf=%s error=%s", sub.get("subId"), wf_id, e)
                    triggered.append({"subId": sub.get("subId"), "wfId": wf_id, "error": str(e)})
        finally:
            _event_depth[event.eventType] = depth
        return triggered
