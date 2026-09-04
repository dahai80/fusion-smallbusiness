import os
import subprocess

import pytest

pytestmark = pytest.mark.asyncio

PG_HOST = os.environ.get("FSB_TEST_PG_HOST", "localhost")
PG_PORT = os.environ.get("FSB_TEST_PG_PORT", "5432")
PG_USER = os.environ.get("FSB_TEST_PG_USER", "dahai")
PG_DB = "fsb_test_autotest"
PG_DSN = f"postgresql://{PG_USER}@{PG_HOST}:{PG_PORT}/{PG_DB}"


def _pg_available() -> bool:
    try:
        subprocess.run(
            ["pg_isready", "-h", PG_HOST, "-p", str(PG_PORT)],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        return False


@pytest.fixture
async def pg_store():
    if not _pg_available():
        pytest.skip(f"postgres not available on {PG_HOST}:{PG_PORT}")
    subprocess.run(
        ["psql", "-h", PG_HOST, "-p", str(PG_PORT), "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {PG_DB};"],
        check=True,
        capture_output=True,
        timeout=10,
    )
    subprocess.run(
        ["psql", "-h", PG_HOST, "-p", str(PG_PORT), "-d", "postgres", "-c", f"CREATE DATABASE {PG_DB};"],
        check=True,
        capture_output=True,
        timeout=10,
    )
    from fsb.db.pg_store import PostgresStore

    store = PostgresStore(dsn=PG_DSN, pool_size=4)
    await store.init()
    yield store
    await store.close()
    subprocess.run(
        ["psql", "-h", PG_HOST, "-p", str(PG_PORT), "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {PG_DB};"],
        check=True,
        capture_output=True,
        timeout=10,
    )


async def test_pg_workspace_crud(pg_store):
    await pg_store.save_workspace("ws_a", {"wsId": "ws_a", "title": "Alpha"})
    ws = await pg_store.get_workspace("ws_a")
    assert ws is not None and ws["title"] == "Alpha"
    listed = await pg_store.list_workspaces()
    assert any(w["wsId"] == "ws_a" for w in listed)
    await pg_store.delete_workspace("ws_a")
    assert await pg_store.get_workspace("ws_a") is None


async def test_pg_connector_workflow_crud(pg_store):
    await pg_store.save_workspace("ws_b", {"wsId": "ws_b", "title": "Beta"})
    await pg_store.save_connector("c1", "ws_b", {"connId": "c1", "wsId": "ws_b", "name": "slack"})
    conn = await pg_store.get_connector("c1")
    assert conn is not None and conn["name"] == "slack"
    conns = await pg_store.list_connectors("ws_b")
    assert len(conns) == 1
    await pg_store.save_workflow("wf1", "ws_b", {"wfId": "wf1", "wsId": "ws_b", "name": "w"})
    wf = await pg_store.get_workflow("wf1")
    assert wf is not None and wf["name"] == "w"
    await pg_store.delete_connector("c1")
    assert await pg_store.get_connector("c1") is None
    await pg_store.delete_workspace("ws_b")
    assert await pg_store.list_connectors("ws_b") == []


async def test_pg_run_traces(pg_store):
    await pg_store.save_workspace("ws_c", {"wsId": "ws_c", "title": "Gamma"})
    await pg_store.save_workflow("wf2", "ws_c", {"wfId": "wf2", "wsId": "ws_c", "name": "w2"})
    await pg_store.save_run("r1", "ws_c", "wf2", {"runId": "r1", "wsId": "ws_c", "status": "running", "nodeTrace": []})
    await pg_store.append_run_trace("r1", 0, {"nodeId": "n0", "status": "ok"})
    await pg_store.append_run_trace("r1", 1, {"nodeId": "n1", "status": "ok"})
    run = await pg_store.get_run("r1")
    assert run is not None and len(run["nodeTrace"]) == 2
    assert run["nodeTrace"][0]["nodeId"] == "n0"
    runs = await pg_store.list_runs("ws_c")
    assert len(runs) == 1 and len(runs[0]["nodeTrace"]) == 2
    runs_wf = await pg_store.list_runs("ws_c", wf_id="wf2")
    assert len(runs_wf) == 1
    await pg_store.delete_run_traces("r1")
    assert await pg_store.list_run_traces("r1") == []
    await pg_store.delete_workspace("ws_c")


async def test_pg_cas_run_status(pg_store):
    await pg_store.save_workspace("ws_d", {"wsId": "ws_d", "title": "Delta"})
    await pg_store.save_workflow("wf3", "ws_d", {"wfId": "wf3", "wsId": "ws_d", "name": "w3"})
    await pg_store.save_run("r2", "ws_d", "wf3", {"runId": "r2", "wsId": "ws_d", "status": "paused"})
    ok = await pg_store.cas_run_status(
        "r2", "ws_d", "wf3", {"runId": "r2", "wsId": "ws_d", "status": "running"}, "paused"
    )
    assert ok is True
    fail = await pg_store.cas_run_status(
        "r2", "ws_d", "wf3", {"runId": "r2", "wsId": "ws_d", "status": "done"}, "paused"
    )
    assert fail is False
    run = await pg_store.get_run("r2")
    assert run["status"] == "running"
    await pg_store.delete_workspace("ws_d")


async def test_pg_subscriptions_webhooks(pg_store):
    await pg_store.save_workspace("ws_e", {"wsId": "ws_e", "title": "Epsilon"})
    await pg_store.save_subscription(
        "s1",
        "ws_e",
        {"subId": "s1", "wsId": "ws_e", "eventType": "invoice.created", "workflowId": "wfX", "enabled": True},
    )
    subs = await pg_store.find_matching_subscriptions("invoice.created", ws_id="ws_e")
    assert len(subs) == 1
    await pg_store.save_webhook(
        "wh1",
        "ws_e",
        {"webhookId": "wh1", "wsId": "ws_e", "events": ["run.completed"], "enabled": True, "url": "http://x"},
    )
    whs = await pg_store.find_webhooks_for_event("ws_e", "run.completed")
    assert len(whs) == 1
    await pg_store.delete_workspace("ws_e")


async def test_pg_leader_election(pg_store):
    got = await pg_store.try_acquire_leader("holder_a", 30)
    assert got is True
    assert await pg_store.is_leader("holder_a") is True
    assert await pg_store.is_leader("holder_b") is False
    ok = await pg_store.renew_leader("holder_a", 30)
    assert ok is True
    await pg_store.release_leader("holder_a")
    assert await pg_store.is_leader("holder_a") is False


async def test_pg_event_dedup(pg_store):
    first = await pg_store.event_seen("evt_dup_1", "ws_dedup", 120)
    assert first is False
    second = await pg_store.event_seen("evt_dup_1", "ws_dedup", 120)
    assert second is True


async def test_pg_rate_limit(pg_store):
    key = "rl_tenant_1"
    cap = 5
    allowed = 0
    for _ in range(cap):
        if await pg_store.rate_limit_consume(key, cap, 1):
            allowed += 1
    assert allowed == cap
    over = await pg_store.rate_limit_consume(key, cap, 1)
    assert over is False


async def test_pg_health(pg_store):
    assert await pg_store.is_healthy() is True
