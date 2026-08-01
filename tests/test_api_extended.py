import pytest
from unittest.mock import patch, AsyncMock


# --- Workflow Run with Valid Graph ---


@pytest.mark.asyncio
async def test_workflow_run_valid_graph(client, ws):
    graph = {
        "nodes": [
            {"id": "n_start", "type": "START_NODE"},
            {"id": "n_end", "type": "END_NODE"},
        ],
        "edges": [{"source": "n_start", "target": "n_end"}],
        "entryNode": "n_start",
    }
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow",
        json={"name": "run-wf", "slashCommand": "/run", "graphDefinition": graph},
    )
    wf_id = resp.json()["wfId"]
    run_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}/run",
        json={"inputData": {"test": "val"}, "triggeredBy": "tester"},
    )
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert run_data["status"] in ("COMPLETED", "RUNNING")


# --- Workflow 404 paths ---


@pytest.mark.asyncio
async def test_workflow_get_404(client, ws):
    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/workflow/wf_notexist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_workflow_update_404(client, ws):
    resp = await client.put(
        f"/api/v1/fsb/workspace/{ws}/workflow/wf_notexist",
        json={"description": "x"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_workflow_delete_404(client, ws):
    resp = await client.delete(f"/api/v1/fsb/workspace/{ws}/workflow/wf_notexist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_workflow_run_404(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow/wf_notexist/run",
        json={"inputData": {}},
    )
    assert resp.status_code == 404


# --- Workflow Schedule ---


@pytest.mark.asyncio
async def test_workflow_set_schedule(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow",
        json={"name": "sched-wf"},
    )
    wf_id = resp.json()["wfId"]
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}/schedule",
        json={"type": "cron", "cron": "0 9 * * 1"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_workflow_set_schedule_404(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow/wf_notexist/schedule",
        json={"type": "cron", "cron": "0 9 * * 1"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_workflow_delete_schedule(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow",
        json={"name": "del-sched-wf"},
    )
    wf_id = resp.json()["wfId"]
    resp = await client.delete(
        f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}/schedule/sched1",
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_workflow_delete_schedule_404(client, ws):
    resp = await client.delete(
        f"/api/v1/fsb/workspace/{ws}/workflow/wf_notexist/schedule/sched1",
    )
    assert resp.status_code == 404


# --- Workflow Import/Export ---


@pytest.mark.asyncio
async def test_workflow_import(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow/import",
        json={"name": "imported-wf", "slashCommand": "/imp"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "imported-wf"


@pytest.mark.asyncio
async def test_workflow_import_404(client):
    resp = await client.post(
        "/api/v1/fsb/workspace/ws_notexist/workflow/import",
        json={"name": "x"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_workflow_export(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow",
        json={"name": "export-wf"},
    )
    wf_id = resp.json()["wfId"]
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}/export",
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_workflow_export_404(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow/wf_notexist/export",
    )
    assert resp.status_code == 404


# --- Connector 404 paths ---


@pytest.mark.asyncio
async def test_connector_update_404(client, ws):
    resp = await client.put(
        f"/api/v1/fsb/workspace/{ws}/connector/conn_notexist",
        json={"authConfig": {}},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_connector_disconnect_404(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/connector/conn_notexist/disconnect",
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_connector_refresh_404(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/connector/conn_notexist/refresh",
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_connector_delete_404(client, ws):
    resp = await client.delete(
        f"/api/v1/fsb/workspace/{ws}/connector/conn_notexist",
    )
    assert resp.status_code == 404


# --- Connector Meta ---


@pytest.mark.asyncio
async def test_connector_meta_list(client):
    resp = await client.get("/api/v1/fsb/connector-meta")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_connector_meta_get_404(client):
    resp = await client.get("/api/v1/fsb/connector-meta/nonexistent_connector")
    assert resp.status_code == 404


# --- OAuth2 502 paths ---


@pytest.mark.asyncio
async def test_oauth2_authorize_502(client, ws):
    conn_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/connector",
        json={"connectorKey": "quickbooks", "authType": "oauth2"},
    )
    conn_id = conn_resp.json()["connId"]
    with patch("fsb.routes.connector.fsb_config") as mock_cfg, \
         patch("fsb.engine.gateway_client.initiate_oauth2", new_callable=AsyncMock) as mock_oauth:
        mock_cfg.STANDALONE_MODE = False
        mock_oauth.return_value = {"success": False, "message": "gateway unreachable"}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/connector/{conn_id}/oauth2/authorize",
            json={"connectorKey": "quickbooks", "redirectUri": "https://cb.com"},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_oauth2_callback_502(client, ws):
    conn_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/connector",
        json={"connectorKey": "hubspot", "authType": "oauth2"},
    )
    conn_id = conn_resp.json()["connId"]
    with patch("fsb.routes.connector.fsb_config") as mock_cfg, \
         patch("fsb.engine.gateway_client.handle_oauth2_callback", new_callable=AsyncMock) as mock_cb:
        mock_cfg.STANDALONE_MODE = False
        mock_cb.return_value = {"success": False, "message": "token exchange failed"}
        resp = await client.get(
            f"/api/v1/fsb/workspace/{ws}/connector/{conn_id}/oauth2/callback?code=abc&state=xyz",
        )
    assert resp.status_code == 502


# --- Skill test endpoint + 404 ---


@pytest.mark.asyncio
async def test_skill_test(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/skill",
        json={"name": "testable-skill", "type": "prompt"},
    )
    skill_id = resp.json()["skillId"]
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/skill/{skill_id}/test",
        json={"input": "hello"},
    )
    assert resp.status_code == 200
    assert resp.json()["dryRun"] is True


@pytest.mark.asyncio
async def test_skill_test_404(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/skill/skill_notexist/test",
        json={},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_skill_update_404(client, ws):
    resp = await client.put(
        f"/api/v1/fsb/workspace/{ws}/skill/skill_notexist",
        json={"definition": "x"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_skill_delete_404(client, ws):
    resp = await client.delete(
        f"/api/v1/fsb/workspace/{ws}/skill/skill_notexist",
    )
    assert resp.status_code == 404


# --- Variable & Template ---


@pytest.mark.asyncio
async def test_variable_list_404(client):
    resp = await client.get("/api/v1/fsb/workspace/ws_notexist/variable")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_variable_update_404(client):
    resp = await client.put(
        "/api/v1/fsb/workspace/ws_notexist/variable",
        json=[{"key": "k", "value": "v", "scope": "workspace"}],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_template_delete(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/template",
        json={"name": "del-tpl", "category": "test"},
    )
    tpl_id = resp.json()["templateId"]
    resp = await client.delete(
        f"/api/v1/fsb/workspace/{ws}/template/{tpl_id}",
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_template_delete_404(client, ws):
    resp = await client.delete(
        f"/api/v1/fsb/workspace/{ws}/template/tpl_notexist",
    )
    assert resp.status_code == 404


# --- Workspace 404/duplicate/export/import ---


@pytest.mark.asyncio
async def test_workspace_duplicate_404(client):
    resp = await client.post("/api/v1/fsb/workspace/ws_notexist/duplicate")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_workspace_export_404(client):
    resp = await client.post("/api/v1/fsb/workspace/ws_notexist/export")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_workspace_delete_404(client):
    resp = await client.delete("/api/v1/fsb/workspace/ws_notexist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_workspace_get_404(client):
    resp = await client.get("/api/v1/fsb/workspace/ws_notexist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_workspace_update_404(client):
    resp = await client.put(
        "/api/v1/fsb/workspace/ws_notexist",
        json={"title": "x"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_workspace_import_simple(client):
    resp = await client.post(
        "/api/v1/fsb/workspace/import",
        json={"name": "simple-import", "description": "test"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "simple-import"


@pytest.mark.asyncio
async def test_workspace_import_full(client):
    resp = await client.post(
        "/api/v1/fsb/workspace",
        json={"title": "full-import-src"},
    )
    ws_data = resp.json()
    export_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws_data['wsId']}/export",
    )
    exported = export_resp.json()
    resp = await client.post(
        "/api/v1/fsb/workspace/import",
        json=exported,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_workspace_import_invalid(client):
    resp = await client.post(
        "/api/v1/fsb/workspace/import",
        json={},
    )
    assert resp.status_code == 422


# --- Execution routes: approve/deny/edit tasks ---


async def _create_paused_task(ws, title="test task"):
    from fsb.app import app_state
    from fsb.models.execution import PendingTask, RunInstance
    from fsb.models.common import RunStatus, TriggerType
    store = app_state.store
    run = RunInstance(
        workspaceId=ws, workflowId="wf1", status=RunStatus.PAUSED,
        triggerType=TriggerType.MANUAL, currentNodeId="n_approval",
    )
    await store.save_run(run.runId, ws, "wf1", run.model_dump(mode="json"))
    task = PendingTask(
        workspaceId=ws, runId=run.runId, nodeId="n_approval",
        title=title, content={},
    )
    await store.save_task(task.taskId, ws, run.runId, task.model_dump(mode="json"))
    return task


@pytest.mark.asyncio
async def test_execution_list_pending_tasks(client, ws):
    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/task/pending")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_execution_approve_task_404(client, ws):
    resp = await client.post(f"/api/v1/fsb/workspace/{ws}/task/task_notexist/approve")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_execution_deny_task_404(client, ws):
    resp = await client.post(f"/api/v1/fsb/workspace/{ws}/task/task_notexist/deny")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_execution_edit_task_404(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/task/task_notexist/edit",
        json={"editContent": {"key": "val"}},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_execution_approve_task(client, ws):
    task = await _create_paused_task(ws, "approve test")
    with patch("fsb.engine.runner.WorkflowRunner") as MockRunner:
        MockRunner.return_value.resume = AsyncMock()
        resp = await client.post(f"/api/v1/fsb/workspace/{ws}/task/{task.taskId}/approve")
    assert resp.status_code == 200
    assert resp.json()["action"] == "approved"


@pytest.mark.asyncio
async def test_execution_deny_task(client, ws):
    task = await _create_paused_task(ws, "deny test")
    with patch("fsb.engine.runner.WorkflowRunner") as MockRunner:
        MockRunner.return_value.resume = AsyncMock()
        resp = await client.post(f"/api/v1/fsb/workspace/{ws}/task/{task.taskId}/deny")
    assert resp.status_code == 200
    assert resp.json()["action"] == "denied"


@pytest.mark.asyncio
async def test_execution_edit_task(client, ws):
    task = await _create_paused_task(ws, "edit test")
    with patch("fsb.engine.runner.WorkflowRunner") as MockRunner:
        MockRunner.return_value.resume = AsyncMock()
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/task/{task.taskId}/edit",
            json={"editContent": {"amount": 500}},
        )
    assert resp.status_code == 200
    assert resp.json()["action"] == "edit"


@pytest.mark.asyncio
async def test_execution_history(client, ws):
    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/execution/history")
    assert resp.status_code == 200



@pytest.mark.asyncio
async def test_execution_export_log(client, ws):
    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/execution/export")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_execution_404(client, ws):
    resp = await client.get(f"/api/v1/fsb/workspace/{ws}/execution/run_notexist")
    assert resp.status_code == 404


# --- External routes ---


@pytest.mark.asyncio
async def test_external_trigger_404(client):
    resp = await client.post(
        "/api/v1/fsb/external/workflow/wf_notexist/trigger",
        json={"inputData": {}},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_external_status_404(client):
    resp = await client.get("/api/v1/fsb/external/workflow/wf_notexist/status")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_external_post_event(client, ws):
    resp = await client.post(
        "/api/v1/fsb/external/event",
        json={"eventType": "invoice.created", "source": "qbo", "payload": {"id": "inv1"}, "workspaceId": ws},
    )
    assert resp.status_code == 200
    assert resp.json()["eventId"] is not None


@pytest.mark.asyncio
async def test_external_post_event_no_type(client):
    resp = await client.post(
        "/api/v1/fsb/external/event",
        json={"source": "qbo", "payload": {}},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_event_subscription_crud(client, ws):
    resp = await client.post(
        "/api/v1/fsb/external/event/subscription",
        json={"workspaceId": ws, "workflowId": "wf1", "eventType": "invoice.created"},
    )
    assert resp.status_code == 200
    sub_id = resp.json()["subId"]

    resp = await client.get(
        "/api/v1/fsb/external/event/subscription",
        params={"wsId": ws},
    )
    assert resp.status_code == 200

    resp = await client.delete(f"/api/v1/fsb/external/event/subscription/{sub_id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_event_subscription_missing_fields(client):
    resp = await client.post(
        "/api/v1/fsb/external/event/subscription",
        json={"workspaceId": "ws1"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_event_subscription_delete_404(client):
    resp = await client.delete("/api/v1/fsb/external/event/subscription/sub_notexist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_webhook_register_missing_fields(client):
    resp = await client.post(
        "/api/v1/fsb/external/webhook/register",
        json={"workspaceId": "ws1"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_list(client):
    resp = await client.get(
        "/api/v1/fsb/external/webhook",
        params={"wsId": "ws_test"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_webhook_delete_404(client):
    resp = await client.delete("/api/v1/fsb/external/webhook/wh_notexist")
    assert resp.status_code == 404


# --- Integration error paths ---


@pytest.mark.asyncio
async def test_send_to_canvas_export_failure(client, ws):
    wf_resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/workflow",
        json={"name": "canvas-fail"},
    )
    wf_id = wf_resp.json()["wfId"]
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.artifact_client.export_session", new_callable=AsyncMock) as mock_export:
        mock_cfg.STANDALONE_MODE = False
        mock_export.return_value = {"success": False, "message": "service unavailable"}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/workflow/{wf_id}/send-to-canvas",
            json={"sessionId": "s1"},
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_sync_to_project_list_failure(client, ws):
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.artifact_client.list_artifacts_by_source", new_callable=AsyncMock) as mock_list:
        mock_cfg.STANDALONE_MODE = False
        mock_list.return_value = {"success": False, "message": "artifact svc down"}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/sync-to-project",
            json={"projectId": "p1"},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_sync_to_project_empty(client, ws):
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.artifact_client.list_artifacts_by_source", new_callable=AsyncMock) as mock_list:
        mock_cfg.STANDALONE_MODE = False
        mock_list.return_value = {"success": True, "data": []}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/sync-to-project",
            json={"projectId": "p1"},
        )
    assert resp.status_code == 200
    assert resp.json()["synced"] == 0


@pytest.mark.asyncio
async def test_sync_to_project_move_failure(client, ws):
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.artifact_client.list_artifacts_by_source", new_callable=AsyncMock) as mock_list, \
         patch("fsb.engine.artifact_client.move_artifact_to_kb", new_callable=AsyncMock) as mock_move:
        mock_cfg.STANDALONE_MODE = False
        mock_list.return_value = {"success": True, "data": [{"id": "art_1", "name": "report"}]}
        mock_move.return_value = {"success": False, "message": "kb unavailable"}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/sync-to-project",
            json={"projectId": "p1"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_artifact_standalone(client, ws):
    resp = await client.post(
        f"/api/v1/fsb/workspace/{ws}/create-artifact",
        json={"name": "test-artifact", "type": "text", "content": "hello"},
    )
    assert resp.status_code == 200
    assert resp.json()["standalone"] is True


@pytest.mark.asyncio
async def test_create_artifact_live(client, ws):
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.artifact_client.create_external_artifact", new_callable=AsyncMock) as mock_create:
        mock_cfg.STANDALONE_MODE = False
        mock_create.return_value = {"success": True, "data": {"id": "art_1"}}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/create-artifact",
            json={"name": "live-artifact", "type": "text", "content": "hello"},
        )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_create_artifact_error(client, ws):
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.artifact_client.create_external_artifact", new_callable=AsyncMock) as mock_create:
        mock_cfg.STANDALONE_MODE = False
        mock_create.return_value = {"status": "error", "message": "service down"}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/create-artifact",
            json={"name": "fail-artifact", "type": "text", "content": "hello"},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_sync_knowledge_cowork_error(client, ws):
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.cowork_client.sync_knowledge", new_callable=AsyncMock) as mock_sync:
        mock_cfg.STANDALONE_MODE = False
        mock_sync.return_value = {"status": "error", "message": "cowork down"}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/sync-knowledge",
            json={"spaceId": "sp1", "files": []},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_import_snapshot_cowork_error(client, ws):
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.cowork_client.import_snapshot", new_callable=AsyncMock) as mock_imp:
        mock_cfg.STANDALONE_MODE = False
        mock_imp.return_value = {"status": "error", "message": "cowork down"}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/import-snapshot",
            json={"spaceId": "sp1", "snapshot": {}},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_export_to_project_cowork_error(client, ws):
    with patch("fsb.routes.integration.fsb_config") as mock_cfg, \
         patch("fsb.engine.cowork_client.export_to_project", new_callable=AsyncMock) as mock_exp:
        mock_cfg.STANDALONE_MODE = False
        mock_exp.return_value = {"status": "error", "message": "cowork down"}
        resp = await client.post(
            f"/api/v1/fsb/workspace/{ws}/export-to-project",
            json={"spaceId": "sp1", "items": {}, "targetProjectId": "p1"},
        )
    assert resp.status_code == 502


# --- Workflow create in nonexistent workspace ---


@pytest.mark.asyncio
async def test_workflow_create_workspace_404(client):
    resp = await client.post(
        "/api/v1/fsb/workspace/ws_notexist/workflow",
        json={"name": "x"},
    )
    assert resp.status_code == 404


# --- Connector create in nonexistent workspace ---


@pytest.mark.asyncio
async def test_connector_create_workspace_404(client):
    resp = await client.post(
        "/api/v1/fsb/workspace/ws_notexist/connector",
        json={"connectorKey": "qbo", "authType": "oauth2"},
    )
    assert resp.status_code == 404


# --- Skill create in nonexistent workspace ---


@pytest.mark.asyncio
async def test_skill_create_workspace_404(client):
    resp = await client.post(
        "/api/v1/fsb/workspace/ws_notexist/skill",
        json={"name": "x", "type": "prompt"},
    )
    assert resp.status_code == 404
