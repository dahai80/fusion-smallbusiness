import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fsb.app import lifespan, AppState
from fsb.engine.event_bus import EventBus
from fsb.models.event import EventTrigger


def test_app_state_has_store():
    state = AppState()
    assert state.store is not None


@pytest.mark.asyncio
async def test_lifespan_register_success():
    mock_app = MagicMock()
    with patch("fsb.app.app_state") as mock_state, \
         patch("fsb.engine.cowork_client.register_module", new_callable=AsyncMock) as mock_reg:
        mock_state.store.init = AsyncMock()
        mock_state.store.close = AsyncMock()
        mock_reg.return_value = {"status": "success"}
        async with lifespan(mock_app):
            pass
        mock_reg.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_register_failure():
    mock_app = MagicMock()
    with patch("fsb.app.app_state") as mock_state, \
         patch("fsb.engine.cowork_client.register_module", new_callable=AsyncMock) as mock_reg:
        mock_state.store.init = AsyncMock()
        mock_state.store.close = AsyncMock()
        mock_reg.side_effect = Exception("connection refused")
        async with lifespan(mock_app):
            pass
        mock_reg.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_register_non_success():
    mock_app = MagicMock()
    with patch("fsb.app.app_state") as mock_state, \
         patch("fsb.engine.cowork_client.register_module", new_callable=AsyncMock) as mock_reg:
        mock_state.store.init = AsyncMock()
        mock_state.store.close = AsyncMock()
        mock_reg.return_value = {"status": "error", "message": "not available"}
        async with lifespan(mock_app):
            pass


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "fusion-smallbusiness"


@pytest.mark.asyncio
async def test_event_bus_publish_no_workspace_id():
    store = MagicMock()
    store.find_matching_subscriptions = AsyncMock(return_value=[
        {"subId": "s1", "workspaceId": "ws1", "workflowId": "wf1"},
    ])
    store.save_event = AsyncMock()
    bus = EventBus(store)
    event = EventTrigger(
        eventId="ev1",
        eventType="invoice.created",
        source="qbo",
        payload={"id": "inv1"},
        workspaceId="",
    )
    with patch("fsb.engine.runner.WorkflowRunner") as MockRunner:
        mock_run = MagicMock()
        mock_run.runId = "run1"
        MockRunner.return_value.start = AsyncMock(return_value=mock_run)
        result = await bus.publish(event)
    assert len(result) == 1
    assert result[0]["runId"] == "run1"
    assert event.workspaceId == "ws1"


@pytest.mark.asyncio
async def test_event_bus_publish_with_workspace_id():
    store = MagicMock()
    store.find_matching_subscriptions = AsyncMock(return_value=[
        {"subId": "s1", "workspaceId": "ws1", "workflowId": "wf1"},
        {"subId": "s2", "workspaceId": "ws2", "workflowId": "wf2"},
    ])
    store.save_event = AsyncMock()
    bus = EventBus(store)
    event = EventTrigger(
        eventId="ev2",
        eventType="invoice.created",
        source="qbo",
        payload={},
        workspaceId="ws1",
    )
    with patch("fsb.engine.runner.WorkflowRunner") as MockRunner:
        mock_run = MagicMock()
        mock_run.runId = "run2"
        MockRunner.return_value.start = AsyncMock(return_value=mock_run)
        result = await bus.publish(event)
    assert len(result) == 1
    assert result[0]["subId"] == "s1"


@pytest.mark.asyncio
async def test_event_bus_publish_trigger_error():
    store = MagicMock()
    store.find_matching_subscriptions = AsyncMock(return_value=[
        {"subId": "s1", "workspaceId": "ws1", "workflowId": "wf1"},
    ])
    store.save_event = AsyncMock()
    bus = EventBus(store)
    event = EventTrigger(
        eventId="ev3",
        eventType="invoice.created",
        source="qbo",
        payload={},
        workspaceId="ws1",
    )
    with patch("fsb.engine.runner.WorkflowRunner") as MockRunner:
        MockRunner.return_value.start = AsyncMock(side_effect=Exception("db error"))
        result = await bus.publish(event)
    assert len(result) == 1
    assert "error" in result[0]
    assert "db error" in result[0]["error"]


@pytest.mark.asyncio
async def test_event_bus_publish_sub_missing_fields():
    store = MagicMock()
    store.find_matching_subscriptions = AsyncMock(return_value=[
        {"subId": "s1", "workspaceId": "ws1"},
        {"subId": "s2", "workflowId": "wf1"},
    ])
    store.save_event = AsyncMock()
    bus = EventBus(store)
    event = EventTrigger(
        eventId="ev4",
        eventType="invoice.created",
        source="qbo",
        payload={},
        workspaceId="ws1",
    )
    result = await bus.publish(event)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_event_bus_publish_no_subs():
    store = MagicMock()
    store.find_matching_subscriptions = AsyncMock(return_value=[])
    store.save_event = AsyncMock()
    bus = EventBus(store)
    event = EventTrigger(
        eventId="ev5",
        eventType="invoice.created",
        source="qbo",
        payload={},
        workspaceId="",
    )
    result = await bus.publish(event)
    assert len(result) == 0
