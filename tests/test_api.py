import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "fusion-smallbusiness"


# --- Workspace CRUD ---


@pytest.mark.asyncio
async def test_workspace_crud(client):
    resp = await client.post("/api/v1/fsb/workspace", json={"title": "ws1"})
    assert resp.status_code == 200
    ws = resp.json()
    assert ws["title"] == "ws1"
    assert ws["wsId"].startswith("fsb_ws_")
    ws_id = ws["wsId"]

    resp = await client.get(f"/api/v1/fsb/workspace/{ws_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "ws1"

    resp = await client.put(f"/api/v1/fsb/workspace/{ws_id}", json={"title": "ws1-updated"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "ws1-updated"

    resp = await client.get("/api/v1/fsb/workspace")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    resp = await client.delete(f"/api/v1/fsb/workspace/{ws_id}")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/fsb/workspace/{ws_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_workspace_duplicate(client):
    resp = await client.post("/api/v1/fsb/workspace", json={"title": "orig"})
    ws_id = resp.json()["wsId"]
    resp = await client.post(f"/api/v1/fsb/workspace/{ws_id}/duplicate")
    assert resp.status_code == 200
    dup = resp.json()
    assert dup["wsId"] != ws_id
    assert "copy" in dup["title"].lower() or dup["title"] == "orig"


@pytest.mark.asyncio
async def test_workspace_export_import(client):
    resp = await client.post("/api/v1/fsb/workspace", json={"title": "export-test"})
    ws_id = resp.json()["wsId"]
    resp = await client.post(f"/api/v1/fsb/workspace/{ws_id}/export")
    assert resp.status_code == 200
    exported = resp.json()

    resp = await client.post("/api/v1/fsb/workspace/import", json=exported)
    assert resp.status_code == 200


# --- Connector CRUD ---


@pytest.mark.asyncio
async def test_connector_crud(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/connector",
        json={"connectorKey": "quickbooks", "authType": "oauth2"},
    )
    assert resp.status_code == 200
    conn = resp.json()
    assert conn["connectorKey"] == "quickbooks"
    assert conn["authType"] == "oauth2"
    conn_id = conn["connId"]

    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/connector")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    resp = await client.put(
        f"/api/v1/fsb/workspace/{ws}/connector/{conn_id}",
        json={"authConfig": {"token": "abc"}},
    )
    assert resp.status_code == 200

    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/connector/{conn_id}/refresh"
    )
    assert resp.status_code == 200

    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/connector/{conn_id}/disconnect"
    )
    assert resp.status_code == 200


# --- Skill CRUD ---


@pytest.mark.asyncio
async def test_skill_crud(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/skill",
        json={"name": "my-skill", "type": "prompt"},
    )
    assert resp.status_code == 200
    skill = resp.json()
    assert skill["name"] == "my-skill"
    assert skill["type"] == "prompt"
    skill_id = skill["skillId"]

    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/skill")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/skill/{skill_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "my-skill"

    resp = await client.put(
        f"/api/v1/fsb/workspace/{ws}/skill/{skill_id}",
        json={"definition": "extract revenue from {{input}}"},
    )
    assert resp.status_code == 200

    resp = await client.delete(f"/api/v1/fsb/workspace/{ws}/skill/{skill_id}")
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/skill/{skill_id}")
    assert resp.status_code == 404


# --- Workflow CRUD ---


@pytest.mark.asyncio
async def test_workflow_crud(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow",
        json={"name": "test-wf", "slashCommand": "/test"},
    )
    assert resp.status_code == 200
    wf = resp.json()
    assert wf["name"] == "test-wf"
    assert wf["slashCommand"] == "/test"
    wf_id = wf["wfId"]

    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/workflow")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}")
    assert resp.status_code == 200

    resp = await client.put(
        f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}",
        json={"description": "updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "updated"

    resp = await client.delete(f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}")
    assert resp.status_code == 200


# --- Workflow run ---


@pytest.mark.asyncio
async def test_workflow_run_invalid_graph(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow",
        json={"name": "empty-wf", "slashCommand": "/empty"},
    )
    wf_id = resp.json()["wfId"]
    run_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}/run",
        json={"inputData": {}},
    )
    assert run_resp.status_code in (400, 422, 500)


# --- Execution / Pending Tasks ---


@pytest.mark.asyncio
async def test_pending_tasks_empty(client, ws):
    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/task/pending")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_execution_history_empty(client, ws):
    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/execution/history")
    assert resp.status_code == 200
    assert resp.json() == []


# --- Variables & Templates ---


@pytest.mark.asyncio
async def test_variable_list_update(client, ws):
    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/variable")
    assert resp.status_code == 200

    resp = await client.put(
        f"/api/v1/fsb/workspace/{ws}/variable",
        json=[{"key": "company_name", "value": "ACME Corp", "scope": "workspace"}],
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_template_crud(client, ws):
    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/template")
    assert resp.status_code == 200

    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/template",
        json={"name": "basic-template", "category": "finance"},
    )
    assert resp.status_code == 200


# --- External endpoints ---


@pytest.mark.asyncio
async def test_external_webhook_register(client):
    resp = await client.post(
        "/api/v1/fsb/external/webhook/register",
        json={"workspaceId": "ws_test", "url": "https://example.com/hook"},
    )
    assert resp.status_code == 200
    assert resp.json()["webhookId"] is not None


# --- Integration stubs ---


@pytest.mark.asyncio
async def test_send_to_canvas(client, ws):
    wf_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow",
        json={"name": "canvas-wf"},
    )
    assert wf_resp.status_code == 200
    wf_id = wf_resp.json()["wfId"]

    with patch("fsb.engine.artifact_client.export_session", new_callable=AsyncMock) as mock_export:
        mock_export.return_value = {"success": True, "data": {"count": 2, "path": "/tmp/exports/s1"}}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}/send-to-canvas",
            json={"sessionId": "s1"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["exportedCount"] == 2


@pytest.mark.asyncio
async def test_sync_to_project(client, ws):
    with patch("fsb.engine.artifact_client.list_artifacts_by_source", new_callable=AsyncMock) as mock_list, \
         patch("fsb.engine.artifact_client.move_artifact_to_kb", new_callable=AsyncMock) as mock_move:
        mock_list.return_value = {"success": True, "data": [
            {"id": "art_1", "name": "report"},
            {"id": "art_2", "name": "invoice"},
        ]}
        mock_move.return_value = {"success": True, "data": {"ok": True}}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/sync-to-project",
            json={"projectId": "p1"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["synced"] == 2
