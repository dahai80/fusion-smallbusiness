import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fsb.db.store import Store
from fsb.engine.scheduler import WorkflowScheduler


def _mock_store(wf_data=None):
    store = AsyncMock(spec=Store)
    store.get_workflow.return_value = wf_data
    return store


@pytest.mark.asyncio
async def test_start_stop():
    store = _mock_store()
    scheduler = WorkflowScheduler(store)
    scheduler.start()
    assert scheduler._scheduler.running
    scheduler.stop()


@pytest.mark.asyncio
async def test_list_jobs_empty():
    store = _mock_store()
    scheduler = WorkflowScheduler(store)
    scheduler.start()
    jobs = scheduler.list_jobs()
    assert jobs == []
    scheduler.stop()


@pytest.mark.asyncio
async def test_register_workflow_not_found():
    store = _mock_store(wf_data=None)
    scheduler = WorkflowScheduler(store)
    scheduler.start()
    await scheduler.register("ws1", "wf_missing")
    jobs = scheduler.list_jobs()
    assert jobs == []
    scheduler.stop()


@pytest.mark.asyncio
async def test_register_non_cron_schedule_skipped():
    store = _mock_store(wf_data={"name": "wf1", "schedule": {"type": "manual"}, "graphDefinition": {
        "nodes": [{"id": "n1", "type": "START_NODE"}, {"id": "n2", "type": "END_NODE"}],
        "edges": [{"source": "n1", "target": "n2"}],
        "entryNode": "n1",
    }})
    scheduler = WorkflowScheduler(store)
    scheduler.start()
    await scheduler.register("ws1", "wf1")
    jobs = scheduler.list_jobs()
    assert jobs == []
    scheduler.stop()


@pytest.mark.asyncio
async def test_register_invalid_cron_format():
    store = _mock_store(wf_data={"name": "wf1", "schedule": {"type": "cron", "cron": "bad"}, "graphDefinition": {
        "nodes": [{"id": "n1", "type": "START_NODE"}, {"id": "n2", "type": "END_NODE"}],
        "edges": [{"source": "n1", "target": "n2"}],
        "entryNode": "n1",
    }})
    scheduler = WorkflowScheduler(store)
    scheduler.start()
    await scheduler.register("ws1", "wf1")
    jobs = scheduler.list_jobs()
    assert jobs == []
    scheduler.stop()


@pytest.mark.asyncio
async def test_register_valid_cron():
    store = _mock_store(wf_data={"name": "wf1", "schedule": {"type": "cron", "cron": "0 9 * * 1"}, "graphDefinition": {
        "nodes": [{"id": "n1", "type": "START_NODE"}, {"id": "n2", "type": "END_NODE"}],
        "edges": [{"source": "n1", "target": "n2"}],
        "entryNode": "n1",
    }})
    scheduler = WorkflowScheduler(store)
    scheduler.start()
    await scheduler.register("ws1", "wf1")
    jobs = scheduler.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["wfId"] == "wf1"
    scheduler.stop()


@pytest.mark.asyncio
async def test_unregister():
    store = _mock_store(wf_data={"name": "wf1", "schedule": {"type": "cron", "cron": "0 9 * * 1"}, "graphDefinition": {
        "nodes": [{"id": "n1", "type": "START_NODE"}, {"id": "n2", "type": "END_NODE"}],
        "edges": [{"source": "n1", "target": "n2"}],
        "entryNode": "n1",
    }})
    scheduler = WorkflowScheduler(store)
    scheduler.start()
    await scheduler.register("ws1", "wf1")
    await scheduler.unregister("ws1", "wf1")
    jobs = scheduler.list_jobs()
    assert jobs == []
    scheduler.stop()


@pytest.mark.asyncio
async def test_unregister_nonexistent():
    store = _mock_store()
    scheduler = WorkflowScheduler(store)
    scheduler.start()
    await scheduler.unregister("ws1", "wf_notexist")
    jobs = scheduler.list_jobs()
    assert jobs == []
    scheduler.stop()


@pytest.mark.asyncio
async def test_register_replaces_existing():
    store = _mock_store(wf_data={"name": "wf1", "schedule": {"type": "cron", "cron": "0 9 * * 1"}, "graphDefinition": {
        "nodes": [{"id": "n1", "type": "START_NODE"}, {"id": "n2", "type": "END_NODE"}],
        "edges": [{"source": "n1", "target": "n2"}],
        "entryNode": "n1",
    }})
    scheduler = WorkflowScheduler(store)
    scheduler.start()
    await scheduler.register("ws1", "wf1")
    await scheduler.register("ws1", "wf1")
    jobs = scheduler.list_jobs()
    assert len(jobs) == 1
    scheduler.stop()


@pytest.mark.asyncio
async def test_run_scheduled_workflow_error():
    store = _mock_store(wf_data={"name": "wf1", "graphDefinition": {
        "nodes": [{"id": "n1", "type": "START_NODE"}, {"id": "n2", "type": "END_NODE"}],
        "edges": [{"source": "n1", "target": "n2"}],
        "entryNode": "n1",
    }})
    scheduler = WorkflowScheduler(store)
    scheduler.start()
    with patch("fsb.engine.runner.WorkflowRunner") as MockRunner:
        MockRunner.return_value.start = AsyncMock(side_effect=Exception("db error"))
        await scheduler._run_scheduled_workflow("ws1", "wf1")
    scheduler.stop()
