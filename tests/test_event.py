import pytest

from fsb.db.store import Store
from fsb.engine.event_bus import EventBus
from fsb.models.event import EventSubscription, EventTrigger


class TestEventBus:
    @pytest.mark.asyncio
    async def test_publish_no_subscriptions(self):
        store = Store(db_path=":memory:")
        await store.init()
        bus = EventBus(store)
        event = EventTrigger(eventType="invoice.created", source="quickbooks", payload={"invoiceId": "inv_123"})
        triggered = await bus.publish(event)
        assert len(triggered) == 0
        saved = await store.get_event(event.eventId)
        assert saved is not None
        assert saved["eventType"] == "invoice.created"

    @pytest.mark.asyncio
    async def test_publish_with_matching_subscription(self):
        store = Store(db_path=":memory:")
        await store.init()
        sub = EventSubscription(
            workspaceId="ws_test",
            workflowId="wf_test",
            eventType="invoice.created",
            enabled=True,
        )
        await store.save_subscription(sub.subId, "ws_test", sub.model_dump(mode="json"))
        bus = EventBus(store)
        event = EventTrigger(
            eventType="invoice.created",
            source="quickbooks",
            payload={"invoiceId": "inv_123"},
            workspaceId="ws_test",
        )
        triggered = await bus.publish(event)
        assert len(triggered) == 1
        assert triggered[0]["wfId"] == "wf_test"

    @pytest.mark.asyncio
    async def test_publish_no_match_event_type(self):
        store = Store(db_path=":memory:")
        await store.init()
        sub = EventSubscription(
            workspaceId="ws_test",
            workflowId="wf_test",
            eventType="invoice.created",
            enabled=True,
        )
        await store.save_subscription(sub.subId, "ws_test", sub.model_dump(mode="json"))
        bus = EventBus(store)
        event = EventTrigger(
            eventType="invoice.paid",
            source="quickbooks",
            payload={},
            workspaceId="ws_test",
        )
        triggered = await bus.publish(event)
        assert len(triggered) == 0

    @pytest.mark.asyncio
    async def test_subscription_source_filter(self):
        store = Store(db_path=":memory:")
        await store.init()
        sub = EventSubscription(
            workspaceId="ws_test",
            workflowId="wf_test",
            eventType="invoice.created",
            source="quickbooks",
            enabled=True,
        )
        await store.save_subscription(sub.subId, "ws_test", sub.model_dump(mode="json"))
        bus = EventBus(store)
        event = EventTrigger(
            eventType="invoice.created",
            source="xero",
            payload={},
            workspaceId="ws_test",
        )
        triggered = await bus.publish(event)
        assert len(triggered) == 0

    @pytest.mark.asyncio
    async def test_subscription_source_wildcard(self):
        store = Store(db_path=":memory:")
        await store.init()
        sub = EventSubscription(
            workspaceId="ws_test",
            workflowId="wf_test",
            eventType="invoice.created",
            source=None,
            enabled=True,
        )
        await store.save_subscription(sub.subId, "ws_test", sub.model_dump(mode="json"))
        bus = EventBus(store)
        event = EventTrigger(
            eventType="invoice.created",
            source="xero",
            payload={},
            workspaceId="ws_test",
        )
        triggered = await bus.publish(event)
        assert len(triggered) == 1

    @pytest.mark.asyncio
    async def test_find_matching_subscriptions(self):
        store = Store(db_path=":memory:")
        await store.init()
        sub1 = EventSubscription(workspaceId="ws_1", workflowId="wf_1", eventType="lead.new", enabled=True)
        sub2 = EventSubscription(workspaceId="ws_2", workflowId="wf_2", eventType="lead.new", enabled=True)
        sub3 = EventSubscription(workspaceId="ws_1", workflowId="wf_3", eventType="invoice.paid", enabled=True)
        await store.save_subscription(sub1.subId, "ws_1", sub1.model_dump(mode="json"))
        await store.save_subscription(sub2.subId, "ws_2", sub2.model_dump(mode="json"))
        await store.save_subscription(sub3.subId, "ws_1", sub3.model_dump(mode="json"))
        matches = await store.find_matching_subscriptions("lead.new")
        assert len(matches) == 2

    @pytest.mark.asyncio
    async def test_subscription_crud(self):
        store = Store(db_path=":memory:")
        await store.init()
        sub = EventSubscription(
            workspaceId="ws_test",
            workflowId="wf_test",
            eventType="order.placed",
            enabled=True,
        )
        await store.save_subscription(sub.subId, "ws_test", sub.model_dump(mode="json"))
        data = await store.get_subscription(sub.subId)
        assert data is not None
        assert data["eventType"] == "order.placed"
        items = await store.list_subscriptions("ws_test")
        assert len(items) == 1
        await store.delete_subscription(sub.subId)
        data = await store.get_subscription(sub.subId)
        assert data is None
