from unittest.mock import AsyncMock, patch

import pytest


def _simple_graph():
    return {
        "nodes": [
            {"id": "n_start", "type": "START_NODE"},
            {"id": "n_end", "type": "END_NODE"},
        ],
        "edges": [{"source": "n_start", "target": "n_end"}],
        "entryNode": "n_start",
    }


async def _make_workflow(client, ws, name="canvas-wf"):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow",
        json={"name": name, "slashCommand": f"/{name}", "graphDefinition": _simple_graph()},
    )
    assert resp.status_code == 200
    return resp.json()["wfId"]


# --- G10: canvas layout ---


@pytest.mark.asyncio
async def test_canvas_layout_update(client, ws):
    wf_id = await _make_workflow(client, ws)
    layout = {"n_start": {"x": 100.0, "y": 50.0}, "n_end": {"x": 300.0, "y": 200.0}}
    resp = await client.put(
        f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}/canvas-layout",
        json={"layout": layout},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["updated"] == 2

    get = await client.get(f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}")
    nodes = {n["id"]: n for n in get.json()["graphDefinition"]["nodes"]}
    assert nodes["n_start"]["position"] == {"x": 100.0, "y": 50.0}
    assert nodes["n_end"]["position"] == {"x": 300.0, "y": 200.0}


@pytest.mark.asyncio
async def test_canvas_layout_404(client, ws):
    resp = await client.put(
        f"/api/v1/fsb/workspace/{ws}/workflow/wf_nonexist/canvas-layout",
        json={"layout": {}},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_canvas_layout_bad_body(client, ws):
    wf_id = await _make_workflow(client, ws, "bad-layout-wf")
    resp = await client.put(
        f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}/canvas-layout",
        json={"layout": "not-a-dict"},
    )
    assert resp.status_code == 400


# --- G11: agent bind / unbind ---


@pytest.mark.asyncio
async def test_agent_bind(client, ws):
    with patch("fsb.engine.chat_client.bind_agent", new=AsyncMock(return_value={"status": "success"})):
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/agent/bind",
            json={"agentId": "agent_abc"},
        )
    assert resp.status_code == 200
    assert resp.json()["bindAgentId"] == "agent_abc"
    get = await client.get(f"/api/v1/fsb/workspace/{ws}")
    assert get.json()["bindAgentId"] == "agent_abc"


@pytest.mark.asyncio
async def test_agent_unbind(client, ws):
    with patch("fsb.engine.chat_client.bind_agent", new=AsyncMock(return_value={"status": "success"})):
        await client.post(f"/api/v1/fsb/workspace/{ws}/agent/bind", json={"agentId": "agent_xyz"})
    with patch("fsb.engine.chat_client.unbind_agent", new=AsyncMock(return_value={"status": "success"})):
        resp = await client.post(f"/api/v1/fsb/workspace/{ws}/agent/unbind")
    assert resp.status_code == 200
    get = await client.get(f"/api/v1/fsb/workspace/{ws}")
    assert get.json()["bindAgentId"] is None


@pytest.mark.asyncio
async def test_agent_bind_404(client):
    resp = await client.post(
        "/api/v1/fsb/workspace/ws_nonexist/agent/bind",
        json={"agentId": "agent_a"},
    )
    assert resp.status_code == 404


# --- G11: chat run (NL -> intent -> run) ---


@pytest.mark.asyncio
async def test_chat_run_match(client, ws):
    wf_id = await _make_workflow(client, ws, "chatrun")
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/chat/run",
        json={"query": "/chatrun"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["matched"] is True
    assert body["run"]["workflowId"] == wf_id
    assert body["run"]["triggeredBy"].startswith("chat:")


@pytest.mark.asyncio
async def test_chat_run_no_match(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/chat/run",
        json={"query": "/definitely-no-such-command"},
    )
    assert resp.status_code == 404


# --- G11: chat_client unit (fail-soft) ---


@pytest.mark.asyncio
async def test_chat_client_notify_fail_soft():
    from fsb.engine.chat_client import notify_run_completed

    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=Exception("conn refused"))):
        result = await notify_run_completed("ws_1", "agent_1", {"runId": "r1"})
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_chat_client_notify_no_agent():
    from fsb.engine.chat_client import notify_run_completed

    result = await notify_run_completed("ws_1", "", {"runId": "r1"})
    assert result["status"] == "skipped"
