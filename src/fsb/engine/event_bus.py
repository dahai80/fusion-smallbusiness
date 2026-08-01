import logging
from typing import Any

from ..db.store import Store
from ..models.common import TriggerType
from ..models.event import EventTrigger

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self, store: Store):
        self.store = store

    async def publish(self, event: EventTrigger) -> list[dict]:
        if not event.workspaceId:
            subs = await self.store.find_matching_subscriptions(event.eventType, event.source)
        else:
            subs = await self.store.find_matching_subscriptions(event.eventType, event.source)
            subs = [s for s in subs if s.get("workspaceId") == event.workspaceId]

        if not event.workspaceId and subs:
            event.workspaceId = subs[0].get("workspaceId", "")

        await self.store.save_event(event.eventId, event.workspaceId, event.model_dump(mode="json"))
        logger.info("event published: %s type=%s source=%s", event.eventId, event.eventType, event.source)

        triggered = []
        for sub in subs:
            wf_id = sub.get("workflowId")
            ws_id = sub.get("workspaceId")
            if not wf_id or not ws_id:
                continue
            try:
                from .runner import WorkflowRunner
                runner = WorkflowRunner(self.store)
                run = await runner.start(
                    ws_id, wf_id,
                    trigger_type=TriggerType.EVENT,
                    triggered_by=f"event:{event.eventId}",
                    input_data=event.payload,
                )
                triggered.append({"subId": sub.get("subId"), "runId": run.runId, "wfId": wf_id})
                logger.info("event triggered workflow: sub=%s wf=%s run=%s", sub.get("subId"), wf_id, run.runId)
            except Exception as e:
                logger.error("event trigger failed: sub=%s wf=%s error=%s", sub.get("subId"), wf_id, e)
                triggered.append({"subId": sub.get("subId"), "wfId": wf_id, "error": str(e)})

        return triggered
