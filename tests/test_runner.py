from unittest.mock import AsyncMock, patch

import pytest

from fsb.db.store import Store
from fsb.engine.runner import WorkflowRunner
from fsb.models.common import RunStatus, TriggerType
from fsb.models.execution import RunInstance


def _simple_graph():
    return {
        "nodes": [
            {"id": "n_start", "type": "START_NODE"},
            {"id": "n_end", "type": "END_NODE"},
        ],
        "edges": [
            {"source": "n_start", "target": "n_end"},
        ],
        "entryNode": "n_start",
    }


def _graph_with_all_types():
    return {
        "nodes": [
            {"id": "n_start", "type": "START_NODE"},
            {"id": "n_conn", "type": "CONNECTOR_NODE", "config": {"connectorId": "qbo", "action": "query", "permission": "read"}},
            {"id": "n_skill", "type": "SKILL_NODE", "config": {"skillId": "test-skill", "extra": {}}},
            {"id": "n_cond", "type": "CONDITION_NODE", "config": {"conditionExpr": "amount>100"}},
            {"id": "n_output", "type": "OUTPUT_NODE", "config": {"outputKey": "result", "extra": {}}},
            {"id": "n_end", "type": "END_NODE"},
        ],
        "edges": [
            {"source": "n_start", "target": "n_conn"},
            {"source": "n_conn", "target": "n_skill"},
            {"source": "n_skill", "target": "n_cond"},
            {"source": "n_cond", "target": "n_output", "condition": "default"},
            {"source": "n_output", "target": "n_end"},
        ],
        "entryNode": "n_start",
    }


def _graph_with_approval():
    return {
        "nodes": [
            {"id": "n_start", "type": "START_NODE"},
            {"id": "n_conn", "type": "CONNECTOR_NODE", "config": {"connectorId": "qbo", "action": "query", "permission": "read"}},
            {"id": "n_approval", "type": "APPROVAL_GATE_NODE", "config": {"title": "confirm"}},
            {"id": "n_send", "type": "CONNECTOR_NODE", "config": {"connectorId": "gmail", "action": "send_email", "permission": "write"}},
            {"id": "n_end", "type": "END_NODE"},
        ],
        "edges": [
            {"source": "n_start", "target": "n_conn"},
            {"source": "n_conn", "target": "n_approval"},
            {"source": "n_approval", "target": "n_send", "condition": "approved"},
            {"source": "n_approval", "target": "n_end", "condition": "denied"},
            {"source": "n_send", "target": "n_end"},
        ],
        "entryNode": "n_start",
    }


def _mock_store(wf_data=None, ws_data=None, connector_data=None, skill_data=None):
    store = AsyncMock(spec=Store)
    store.get_workflow.return_value = wf_data
    store.get_workspace.return_value = ws_data
    store.get_connector.return_value = connector_data
    store.get_skill.return_value = skill_data
    store.save_run = AsyncMock()
    store.save_task = AsyncMock()
    store.find_webhooks_for_event.return_value = []
    return store


def _wf_from_graph(graph_dict):
    wf_data = {
        "name": "test-wf",
        "workspaceId": "ws_test",
        "schedule": {"type": "manual"},
        "graphDefinition": graph_dict,
    }
    return wf_data


class TestWorkflowRunnerStart:
    @pytest.mark.asyncio
    async def test_start_workflow_not_found(self):
        store = _mock_store(wf_data=None)
        runner = WorkflowRunner(store)
        with pytest.raises(ValueError, match="workflow not found"):
            await runner.start("ws1", "wf_missing")

    @pytest.mark.asyncio
    async def test_start_simple_graph_completes(self):
        wf_data = _wf_from_graph(_simple_graph())
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        runner = WorkflowRunner(store)
        run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        assert run.status == RunStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_start_graph_with_all_node_types(self):
        wf_data = _wf_from_graph(_graph_with_all_types())
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data, skill_data={"skillId": "test-skill", "name": "test", "type": "prompt", "definition": ""})
        runner = WorkflowRunner(store)

        with patch("fsb.engine.gateway_client.execute_action", new_callable=AsyncMock) as mock_exec, \
             patch("fsb.engine.llm_client.execute_skill_prompt", new_callable=AsyncMock) as mock_skill, \
             patch("fsb.engine.artifact_client.create_external_artifact", new_callable=AsyncMock) as mock_artifact, \
             patch("fsb.engine.rag_client.upload_document", new_callable=AsyncMock) as mock_upload:
            mock_exec.return_value = {"success": True, "data": {"items": []}}
            mock_skill.return_value = {"status": "success", "data": {"text": "ok"}}
            mock_artifact.return_value = {"success": True}
            mock_upload.return_value = {"success": True, "data": {"doc_id": "d1"}}
            run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        assert run.status == RunStatus.COMPLETED
        node_types = {t.nodeId for t in run.nodeTrace}
        assert "n_conn" in node_types
        assert "n_skill" in node_types
        assert "n_cond" in node_types
        assert "n_output" in node_types

    @pytest.mark.asyncio
    async def test_start_workflow_with_variables(self):
        wf_data = _wf_from_graph(_simple_graph())
        ws_data = {"wsId": "ws1", "variables": [{"key": "company", "value": "ACME"}]}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        runner = WorkflowRunner(store)
        run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        assert run.contextSandbox.variables.get("company") == "ACME"

    @pytest.mark.asyncio
    async def test_start_with_invalid_graph_no_start(self):
        bad_graph = {
            "nodes": [{"id": "n_end", "type": "END_NODE"}],
            "edges": [],
            "entryNode": "n_start",
        }
        wf_data = _wf_from_graph(bad_graph)
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        runner = WorkflowRunner(store)
        with pytest.raises(ValueError, match="START_NODE"):
            await runner.start("ws1", wf_data.get("wfId", "wf1"))


class TestWorkflowRunnerResume:
    @pytest.mark.asyncio
    async def test_resume_not_found(self):
        store = _mock_store()
        store.get_run.return_value = None
        runner = WorkflowRunner(store)
        with pytest.raises(ValueError, match="run not found"):
            await runner.resume("run_missing", "approved")

    @pytest.mark.asyncio
    async def test_resume_not_paused(self):
        run_obj = RunInstance(
            runId="r1", workspaceId="ws1", workflowId="wf1",
            status=RunStatus.COMPLETED, triggerType=TriggerType.MANUAL,
            contextSandbox={"inputData": {}, "variables": {}, "artifacts": [], "snapshots": {}},
            nodeTrace=[], approvalRecord=[],
        )
        wf_data = _wf_from_graph(_simple_graph())
        store = _mock_store(wf_data=wf_data)
        store.get_run.return_value = run_obj.model_dump(mode="json")
        runner = WorkflowRunner(store)
        await runner.resume("r1", "approved")
        assert store.save_run.call_count == 0

    @pytest.mark.asyncio
    async def test_resume_workflow_not_found(self):
        run_obj = RunInstance(
            runId="r1", workspaceId="ws1", workflowId="wf1",
            status=RunStatus.PAUSED, triggerType=TriggerType.MANUAL,
            currentNodeId="n_approval",
            contextSandbox={"inputData": {}, "variables": {}, "artifacts": [], "snapshots": {}},
            nodeTrace=[], approvalRecord=[],
        )
        store = _mock_store(wf_data=None)
        store.get_run.return_value = run_obj.model_dump(mode="json")
        runner = WorkflowRunner(store)
        with pytest.raises(ValueError, match="workflow not found"):
            await runner.resume("r1", "approved")


class TestWorkflowRunnerConnectorExecution:
    @pytest.mark.asyncio
    async def test_connector_gateway_success(self):
        wf_data = _wf_from_graph({
            "nodes": [
                {"id": "n_start", "type": "START_NODE"},
                {"id": "n_conn", "type": "CONNECTOR_NODE", "config": {"connectorId": "qbo", "action": "query", "permission": "read"}},
                {"id": "n_end", "type": "END_NODE"},
            ],
            "edges": [
                {"source": "n_start", "target": "n_conn"},
                {"source": "n_conn", "target": "n_end"},
            ],
            "entryNode": "n_start",
        })
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data, connector_data={"data": {"connectionId": "conn1"}})
        runner = WorkflowRunner(store)

        with patch("fsb.engine.gateway_client.execute_action", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"success": True, "data": {"invoices": []}}
            run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        assert run.status == RunStatus.COMPLETED
        conn_trace = next(t for t in run.nodeTrace if t.nodeId == "n_conn")
        assert conn_trace.status == "success"

    @pytest.mark.asyncio
    async def test_connector_gateway_failure_fallback_stub(self):
        wf_data = _wf_from_graph({
            "nodes": [
                {"id": "n_start", "type": "START_NODE"},
                {"id": "n_conn", "type": "CONNECTOR_NODE", "config": {"connectorId": "qbo", "action": "query", "permission": "read"}},
                {"id": "n_end", "type": "END_NODE"},
            ],
            "edges": [
                {"source": "n_start", "target": "n_conn"},
                {"source": "n_conn", "target": "n_end"},
            ],
            "entryNode": "n_start",
        })
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        runner = WorkflowRunner(store)

        with patch("fsb.engine.gateway_client.execute_action", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"success": False, "message": "auth failed"}
            run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        conn_trace = next(t for t in run.nodeTrace if t.nodeId == "n_conn")
        assert conn_trace.output.get("status") == "simulated"

    @pytest.mark.asyncio
    async def test_connector_gateway_exception_fallback_stub(self):
        wf_data = _wf_from_graph({
            "nodes": [
                {"id": "n_start", "type": "START_NODE"},
                {"id": "n_conn", "type": "CONNECTOR_NODE", "config": {"connectorId": "qbo", "action": "query", "permission": "read"}},
                {"id": "n_end", "type": "END_NODE"},
            ],
            "edges": [
                {"source": "n_start", "target": "n_conn"},
                {"source": "n_conn", "target": "n_end"},
            ],
            "entryNode": "n_start",
        })
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        runner = WorkflowRunner(store)

        with patch("fsb.engine.gateway_client.execute_action", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = RuntimeError("network down")
            run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        conn_trace = next(t for t in run.nodeTrace if t.nodeId == "n_conn")
        assert conn_trace.output.get("status") == "simulated"


class TestWorkflowRunnerSkillExecution:
    @pytest.mark.asyncio
    async def test_skill_llm_success(self):
        wf_data = _wf_from_graph({
            "nodes": [
                {"id": "n_start", "type": "START_NODE"},
                {"id": "n_skill", "type": "SKILL_NODE", "config": {"skillId": "s1", "extra": {"model": "qwen3"}}},
                {"id": "n_end", "type": "END_NODE"},
            ],
            "edges": [
                {"source": "n_start", "target": "n_skill"},
                {"source": "n_skill", "target": "n_end"},
            ],
            "entryNode": "n_start",
        })
        ws_data = {"wsId": "ws1", "variables": []}
        skill_data = {"skillId": "s1", "name": "test-skill", "type": "prompt", "definition": "summarize this"}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data, skill_data=skill_data)
        runner = WorkflowRunner(store)

        with patch("fsb.engine.llm_client.execute_skill_prompt", new_callable=AsyncMock) as mock_skill:
            mock_skill.return_value = {"status": "success", "data": {"text": "summary"}}
            run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        skill_trace = next(t for t in run.nodeTrace if t.nodeId == "n_skill")
        assert skill_trace.output.get("status") == "success"

    @pytest.mark.asyncio
    async def test_skill_llm_failure_fallback_stub(self):
        wf_data = _wf_from_graph({
            "nodes": [
                {"id": "n_start", "type": "START_NODE"},
                {"id": "n_skill", "type": "SKILL_NODE", "config": {"skillId": "s1", "extra": {}}},
                {"id": "n_end", "type": "END_NODE"},
            ],
            "edges": [
                {"source": "n_start", "target": "n_skill"},
                {"source": "n_skill", "target": "n_end"},
            ],
            "entryNode": "n_start",
        })
        ws_data = {"wsId": "ws1", "variables": []}
        skill_data = {"skillId": "s1", "name": "test-skill", "type": "prompt", "definition": "summarize"}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data, skill_data=skill_data)
        runner = WorkflowRunner(store)

        with patch("fsb.engine.llm_client.execute_skill_prompt", new_callable=AsyncMock) as mock_skill:
            mock_skill.return_value = {"status": "error", "message": "model unavailable"}
            run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        skill_trace = next(t for t in run.nodeTrace if t.nodeId == "n_skill")
        assert skill_trace.output.get("status") == "simulated"

    @pytest.mark.asyncio
    async def test_skill_no_definition_fallback_stub(self):
        wf_data = _wf_from_graph({
            "nodes": [
                {"id": "n_start", "type": "START_NODE"},
                {"id": "n_skill", "type": "SKILL_NODE", "config": {"skillId": "s1", "extra": {}}},
                {"id": "n_end", "type": "END_NODE"},
            ],
            "edges": [
                {"source": "n_start", "target": "n_skill"},
                {"source": "n_skill", "target": "n_end"},
            ],
            "entryNode": "n_start",
        })
        ws_data = {"wsId": "ws1", "variables": []}
        skill_data = {"skillId": "s1", "name": "test-skill", "type": "prompt", "definition": ""}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data, skill_data=skill_data)
        runner = WorkflowRunner(store)
        run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        skill_trace = next(t for t in run.nodeTrace if t.nodeId == "n_skill")
        assert skill_trace.output.get("status") == "simulated"

    @pytest.mark.asyncio
    async def test_skill_not_found_fallback_stub(self):
        wf_data = _wf_from_graph({
            "nodes": [
                {"id": "n_start", "type": "START_NODE"},
                {"id": "n_skill", "type": "SKILL_NODE", "config": {"skillId": "s1", "extra": {}}},
                {"id": "n_end", "type": "END_NODE"},
            ],
            "edges": [
                {"source": "n_start", "target": "n_skill"},
                {"source": "n_skill", "target": "n_end"},
            ],
            "entryNode": "n_start",
        })
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data, skill_data=None)
        runner = WorkflowRunner(store)
        run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        skill_trace = next(t for t in run.nodeTrace if t.nodeId == "n_skill")
        assert skill_trace.output.get("status") == "simulated"


class TestWorkflowRunnerApproval:
    @pytest.mark.asyncio
    async def test_approval_gate_pauses_run(self):
        wf_data = _wf_from_graph(_graph_with_approval())
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        runner = WorkflowRunner(store)

        with patch("fsb.engine.gateway_client.execute_action", new_callable=AsyncMock) as mock_exec, \
             patch("fsb.engine.cowork_client.push_notification", new_callable=AsyncMock):
            mock_exec.return_value = {"success": True, "data": {}}
            run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        assert run.status == RunStatus.PAUSED

    @pytest.mark.asyncio
    async def test_push_approval_notification_failure(self):
        wf_data = _wf_from_graph(_graph_with_approval())
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        runner = WorkflowRunner(store)

        with patch("fsb.engine.gateway_client.execute_action", new_callable=AsyncMock) as mock_exec, \
             patch("fsb.engine.cowork_client.push_notification", new_callable=AsyncMock) as mock_push:
            mock_exec.return_value = {"success": True, "data": {}}
            mock_push.side_effect = RuntimeError("cowork down")
            run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        assert run.status == RunStatus.PAUSED


class TestWorkflowRunnerOutputNode:
    @pytest.mark.asyncio
    async def test_output_node_creates_artifact_and_rag(self):
        wf_data = _wf_from_graph({
            "nodes": [
                {"id": "n_start", "type": "START_NODE"},
                {"id": "n_output", "type": "OUTPUT_NODE", "config": {"outputKey": "report", "extra": {"artifactName": "sales_report", "artifactType": "text", "knowledgeBaseId": "kb1"}}},
                {"id": "n_end", "type": "END_NODE"},
            ],
            "edges": [
                {"source": "n_start", "target": "n_output"},
                {"source": "n_output", "target": "n_end"},
            ],
            "entryNode": "n_start",
        })
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        runner = WorkflowRunner(store)

        with patch("fsb.engine.artifact_client.create_external_artifact", new_callable=AsyncMock) as mock_artifact, \
             patch("fsb.engine.rag_client.upload_document", new_callable=AsyncMock) as mock_upload:
            mock_artifact.return_value = {"success": True}
            mock_upload.return_value = {"success": True, "data": {"doc_id": "d1"}}
            run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        assert run.status == RunStatus.COMPLETED
        assert len(run.contextSandbox.artifacts) == 1
        assert run.contextSandbox.artifacts[0]["key"] == "report"

    @pytest.mark.asyncio
    async def test_output_node_no_kbid_skips_rag(self):
        wf_data = _wf_from_graph({
            "nodes": [
                {"id": "n_start", "type": "START_NODE"},
                {"id": "n_output", "type": "OUTPUT_NODE", "config": {"outputKey": "report", "extra": {}}},
                {"id": "n_end", "type": "END_NODE"},
            ],
            "edges": [
                {"source": "n_start", "target": "n_output"},
                {"source": "n_output", "target": "n_end"},
            ],
            "entryNode": "n_start",
        })
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        runner = WorkflowRunner(store)

        with patch("fsb.engine.artifact_client.create_external_artifact", new_callable=AsyncMock) as mock_artifact, \
             patch("fsb.engine.rag_client.upload_document", new_callable=AsyncMock) as mock_upload:
            mock_artifact.return_value = {"success": True}
            await runner.start("ws1", wf_data.get("wfId", "wf1"))
        mock_upload.assert_not_called()

    @pytest.mark.asyncio
    async def test_output_node_artifact_failure_continues(self):
        wf_data = _wf_from_graph({
            "nodes": [
                {"id": "n_start", "type": "START_NODE"},
                {"id": "n_output", "type": "OUTPUT_NODE", "config": {"outputKey": "report", "extra": {}}},
                {"id": "n_end", "type": "END_NODE"},
            ],
            "edges": [
                {"source": "n_start", "target": "n_output"},
                {"source": "n_output", "target": "n_end"},
            ],
            "entryNode": "n_start",
        })
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        runner = WorkflowRunner(store)

        with patch("fsb.engine.artifact_client.create_external_artifact", new_callable=AsyncMock) as mock_artifact, \
             patch("fsb.engine.rag_client.upload_document", new_callable=AsyncMock):
            mock_artifact.side_effect = RuntimeError("artifact svc down")
            run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        assert run.status == RunStatus.COMPLETED


class TestWorkflowRunnerWebhooks:
    @pytest.mark.asyncio
    async def test_dispatch_webhooks_on_completion(self):
        wf_data = _wf_from_graph(_simple_graph())
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        store.find_webhooks_for_event.return_value = [
            {"webhookId": "wh1", "url": "https://hook.example.com", "events": ["run.completed"], "secret": ""}
        ]
        runner = WorkflowRunner(store)

        with patch("fsb.engine.webhook_dispatcher.dispatch_webhook", new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = True
            await runner.start("ws1", wf_data.get("wfId", "wf1"))
        mock_dispatch.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_webhooks_error_continues(self):
        wf_data = _wf_from_graph(_simple_graph())
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        store.find_webhooks_for_event.side_effect = RuntimeError("db error")
        runner = WorkflowRunner(store)
        run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        assert run.status == RunStatus.COMPLETED


class TestWorkflowRunnerEntryNodeMissing:
    @pytest.mark.asyncio
    async def test_missing_entry_node_fails_run(self):
        bad_graph = {
            "nodes": [
                {"id": "n_start", "type": "START_NODE"},
                {"id": "n_end", "type": "END_NODE"},
            ],
            "edges": [
                {"source": "n_start", "target": "n_end"},
            ],
            "entryNode": "nonexistent",
        }
        wf_data = _wf_from_graph(bad_graph)
        ws_data = {"wsId": "ws1", "variables": []}
        store = _mock_store(wf_data=wf_data, ws_data=ws_data)
        runner = WorkflowRunner(store)
        run = await runner.start("ws1", wf_data.get("wfId", "wf1"))
        assert run.status == RunStatus.FAILED
