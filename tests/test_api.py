from unittest.mock import AsyncMock, patch

import pytest


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

    resp = await client.delete(
        f"/api/v1/fsb/workspace/{ws}/connector/{conn_id}"
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/connector")
    remaining_ids = [c["connId"] for c in resp.json()]
    assert conn_id not in remaining_ids


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
async def test_send_to_canvas_standalone(client, ws):
    wf_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow",
        json={"name": "canvas-wf"},
    )
    assert wf_resp.status_code == 200
    wf_id = wf_resp.json()["wfId"]

    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}/send-to-canvas",
        json={"sessionId": "s1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["standalone"] is True


@pytest.mark.asyncio
async def test_send_to_canvas_live(client, ws):
    wf_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow",
        json={"name": "canvas-wf-live"},
    )
    assert wf_resp.status_code == 200
    wf_id = wf_resp.json()["wfId"]

    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.artifact_client.export_session", new_callable=AsyncMock) as mock_export:
        mock_cfg.STANDALONE_MODE = False
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
async def test_sync_to_project_standalone(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/sync-to-project",
        json={"projectId": "p1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["standalone"] is True


@pytest.mark.asyncio
async def test_sync_to_project_live(client, ws):
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.artifact_client.list_artifacts_by_source", new_callable=AsyncMock) as mock_list, \
         patch("fsb.engine.artifact_client.move_artifact_to_kb", new_callable=AsyncMock) as mock_move:
        mock_cfg.STANDALONE_MODE = False
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


# --- OAuth2 Flow ---


@pytest.mark.asyncio
async def test_oauth2_authorize_standalone(client, ws):
    conn_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/connector",
        json={"connectorKey": "quickbooks", "authType": "oauth2"},
    )
    assert conn_resp.status_code == 200
    conn_id = conn_resp.json()["connId"]

    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/connector/{conn_id}/oauth2/authorize",
        json={"connectorKey": "quickbooks", "redirectUri": "https://example.com/callback", "state": "abc"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["standalone"] is True
    assert data["state"] == "abc"


@pytest.mark.asyncio
async def test_oauth2_authorize_live(client, ws):
    conn_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/connector",
        json={"connectorKey": "quickbooks", "authType": "oauth2"},
    )
    assert conn_resp.status_code == 200
    conn_id = conn_resp.json()["connId"]

    with patch("fsb.routes.connector.fsb_config") as mock_cfg, \
         patch("fsb.engine.gateway_client.initiate_oauth2", new_callable=AsyncMock) as mock_oauth:
        mock_cfg.STANDALONE_MODE = False
        mock_oauth.return_value = {
            "success": True,
            "authorizeUrl": "https://auth.example.com/authorize?code=xyz",
            "state": "abc",
        }
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/connector/{conn_id}/oauth2/authorize",
            json={"connectorKey": "quickbooks", "redirectUri": "https://example.com/callback", "state": "abc"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "authorizeUrl" in data


@pytest.mark.asyncio
async def test_oauth2_callback_standalone(client, ws):
    conn_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/connector",
        json={"connectorKey": "hubspot", "authType": "oauth2"},
    )
    assert conn_resp.status_code == 200
    conn_id = conn_resp.json()["connId"]

    resp = await client.get(
        f"/api/v1/fsb/workspace/{ws}/connector/{conn_id}/oauth2/callback?code=test_code&state=abc",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["standalone"] is True


@pytest.mark.asyncio
async def test_oauth2_callback_live(client, ws):
    conn_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/connector",
        json={"connectorKey": "hubspot", "authType": "oauth2"},
    )
    assert conn_resp.status_code == 200
    conn_id = conn_resp.json()["connId"]

    with patch("fsb.routes.connector.fsb_config") as mock_cfg, \
         patch("fsb.engine.gateway_client.handle_oauth2_callback", new_callable=AsyncMock) as mock_cb:
        mock_cfg.STANDALONE_MODE = False
        mock_cb.return_value = {"success": True, "connectionId": "conn_live_123"}
        resp = await client.get(
            f"/api/v1/fsb/workspace/{ws}/connector/{conn_id}/oauth2/callback?code=test_code&state=abc",
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


# --- Cowork Project Integration ---


@pytest.mark.asyncio
async def test_sync_knowledge_standalone(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/sync-knowledge",
        json={"spaceId": "sp1", "files": [{"name": "doc.pdf", "content": "base64data", "folder": "docs"}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["standalone"] is True


@pytest.mark.asyncio
async def test_sync_knowledge_live(client, ws):
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.cowork_client.sync_knowledge", new_callable=AsyncMock) as mock_sync:
        mock_cfg.STANDALONE_MODE = False
        mock_sync.return_value = {"status": "success", "data": {"syncedCount": 1}}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/sync-knowledge",
            json={"spaceId": "sp1", "files": [{"name": "doc.pdf", "content": "base64data", "folder": "docs"}]},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_import_snapshot_standalone(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/import-snapshot",
        json={"spaceId": "sp1", "snapshot": {"title": "PRD Discussion", "messages": []}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["standalone"] is True


@pytest.mark.asyncio
async def test_import_snapshot_live(client, ws):
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.cowork_client.import_snapshot", new_callable=AsyncMock) as mock_imp:
        mock_cfg.STANDALONE_MODE = False
        mock_imp.return_value = {"status": "success", "data": {"importedCount": 1}}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/import-snapshot",
            json={"spaceId": "sp1", "snapshot": {"title": "PRD Discussion", "messages": []}},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_export_to_project_standalone(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/export-to-project",
        json={"spaceId": "sp1", "items": {"files": True, "chatHistory": True}, "targetProjectId": "proj1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["standalone"] is True


@pytest.mark.asyncio
async def test_export_to_project_live(client, ws):
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.cowork_client.export_to_project", new_callable=AsyncMock) as mock_exp:
        mock_cfg.STANDALONE_MODE = False
        mock_exp.return_value = {"status": "success", "data": {"exportedItems": ["file1", "chat1"]}}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/export-to-project",
            json={"spaceId": "sp1", "items": {"files": True, "chatHistory": True}, "targetProjectId": "proj1"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
