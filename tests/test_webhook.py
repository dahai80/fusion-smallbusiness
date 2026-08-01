import pytest

from fsb.db.store import Store
from fsb.models.webhook import Webhook


class TestWebhookCRUD:
    @pytest.mark.asyncio
    async def test_save_and_get(self):
        store = Store(db_path=":memory:")
        await store.init()
        wh = Webhook(workspaceId="ws_1", url="https://example.com/hook", events=["run.completed"])
        await store.save_webhook(wh.webhookId, "ws_1", wh.model_dump(mode="json"))
        data = await store.get_webhook(wh.webhookId)
        assert data is not None
        assert data["url"] == "https://example.com/hook"

    @pytest.mark.asyncio
    async def test_list(self):
        store = Store(db_path=":memory:")
        await store.init()
        wh1 = Webhook(workspaceId="ws_1", url="https://a.com/hook")
        wh2 = Webhook(workspaceId="ws_1", url="https://b.com/hook")
        await store.save_webhook(wh1.webhookId, "ws_1", wh1.model_dump(mode="json"))
        await store.save_webhook(wh2.webhookId, "ws_1", wh2.model_dump(mode="json"))
        items = await store.list_webhooks("ws_1")
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_delete(self):
        store = Store(db_path=":memory:")
        await store.init()
        wh = Webhook(workspaceId="ws_1", url="https://example.com/hook")
        await store.save_webhook(wh.webhookId, "ws_1", wh.model_dump(mode="json"))
        await store.delete_webhook(wh.webhookId)
        data = await store.get_webhook(wh.webhookId)
        assert data is None

    @pytest.mark.asyncio
    async def test_find_webhooks_for_event(self):
        store = Store(db_path=":memory:")
        await store.init()
        wh1 = Webhook(workspaceId="ws_1", url="https://a.com/hook", events=["run.completed", "run.failed"])
        wh2 = Webhook(workspaceId="ws_1", url="https://b.com/hook", events=["run.failed"])
        wh3 = Webhook(workspaceId="ws_1", url="https://c.com/hook", events=["run.completed"], enabled=False)
        await store.save_webhook(wh1.webhookId, "ws_1", wh1.model_dump(mode="json"))
        await store.save_webhook(wh2.webhookId, "ws_1", wh2.model_dump(mode="json"))
        await store.save_webhook(wh3.webhookId, "ws_1", wh3.model_dump(mode="json"))
        matches = await store.find_webhooks_for_event("ws_1", "run.completed")
        assert len(matches) == 1
        assert matches[0]["url"] == "https://a.com/hook"
        matches_failed = await store.find_webhooks_for_event("ws_1", "run.failed")
        assert len(matches_failed) == 2
