from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fsb.config import FSBConfig


def _make_mock_client(method: str, return_value: dict):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = return_value
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    getattr(mock_client, method).return_value = mock_resp

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None

    return mock_cm, mock_resp


def _make_fail_client(method: str):
    import httpx
    mock_client = AsyncMock()
    getattr(mock_client, method).side_effect = httpx.ConnectError("connection refused")
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None
    return mock_cm


class TestArtifactClient:
    @pytest.mark.asyncio
    async def test_create_external_artifact_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "artifact_id": "art_123",
            "name": "test_output",
        })
        with patch("fsb.engine.artifact_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.artifact_client import create_external_artifact
            result = await create_external_artifact(
                source_module="fsb",
                workspace_id="ws_001",
                name="test_output",
                artifact_type="text",
                content="hello world",
            )
        assert result["artifact_id"] == "art_123"

    @pytest.mark.asyncio
    async def test_create_external_artifact_failure(self):
        mock_cm = _make_fail_client("post")
        with patch("fsb.engine.artifact_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.artifact_client import create_external_artifact
            result = await create_external_artifact(
                source_module="fsb",
                workspace_id="ws_001",
                name="test",
                artifact_type="text",
                content="fail",
            )
        assert result["status"] == "error"


class TestLLMClient:
    @pytest.mark.asyncio
    async def test_chat_completion_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"total_tokens": 10},
        })
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import chat_completion
            result = await chat_completion(
                model="test-model",
                messages=[{"role": "user", "content": "hi"}],
            )
        assert result["choices"][0]["message"]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_execute_skill_prompt_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "choices": [{"message": {"content": "skill result"}}],
            "usage": {"total_tokens": 50},
            "model": "test",
        })
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import execute_skill_prompt
            result = await execute_skill_prompt(
                skill_definition="analyze data",
                input_data={"key": "value"},
            )
        assert result["status"] == "success"
        assert result["content"] == "skill result"

    @pytest.mark.asyncio
    async def test_execute_skill_prompt_failure(self):
        mock_cm = _make_fail_client("post")
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import execute_skill_prompt
            result = await execute_skill_prompt(
                skill_definition="test",
                input_data={},
            )
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_list_models_success(self):
        mock_cm, _ = _make_mock_client("get", {
            "data": [
                {"id": "qwen3.5-9b", "object": "model"},
                {"id": "BGE-M3", "object": "model"},
            ],
        })
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import list_models
            result = await list_models()
        assert len(result["data"]) == 2

    @pytest.mark.asyncio
    async def test_get_model_info_success(self):
        mock_cm, _ = _make_mock_client("get", {
            "data": [
                {"id": "qwen3.5-9b", "object": "model", "owned_by": "mlx"},
                {"id": "BGE-M3", "object": "model", "owned_by": "mlx"},
            ],
        })
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import get_model_info
            result = await get_model_info("qwen3.5-9b")
        assert result["id"] == "qwen3.5-9b"

    @pytest.mark.asyncio
    async def test_create_embedding_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}],
            "model": "BGE-M3",
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        })
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import create_embedding
            result = await create_embedding(input="hello world", model="BGE-M3")
        assert len(result["data"]) == 1
        assert result["model"] == "BGE-M3"

    @pytest.mark.asyncio
    async def test_list_models_failure(self):
        mock_cm = _make_fail_client("get")
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import list_models
            result = await list_models()
        assert result["status"] == "error"


class TestGatewayClient:
    @pytest.mark.asyncio
    async def test_execute_action_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "success": True,
            "code": 0,
            "data": {"invoice": "INV-001"},
            "message": "",
        })
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import execute_action
            result = await execute_action(
                connector_key="quickbooks",
                action_key="list_invoices",
                params={"limit": 10},
                connection_id="conn_001",
            )
        assert result["success"] is True
        assert result["data"]["invoice"] == "INV-001"

    @pytest.mark.asyncio
    async def test_list_connectors_success(self):
        mock_cm, _ = _make_mock_client("get", {
            "connectors": [{"connectorKey": "quickbooks", "displayName": "QuickBooks"}],
        })
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import list_connectors
            result = await list_connectors()
        assert "connectors" in result

    @pytest.mark.asyncio
    async def test_execute_action_failure(self):
        mock_cm = _make_fail_client("post")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import execute_action
            result = await execute_action("quickbooks", "list_invoices")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_create_connection_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "id": "conn_001",
            "connectorKey": "quickbooks",
            "authType": "oauth2",
            "status": "active",
        })
        mock_cm.__aenter__.return_value.post.return_value.status_code = 201
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import create_connection
            result = await create_connection(
                connection_id="conn_001",
                connector_key="quickbooks",
                auth_type="oauth2",
            )
        assert result["id"] == "conn_001"

    @pytest.mark.asyncio
    async def test_get_connection_success(self):
        mock_cm, _ = _make_mock_client("get", {
            "id": "conn_001",
            "connectorKey": "quickbooks",
            "status": "active",
        })
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import get_connection
            result = await get_connection("conn_001")
        assert result["id"] == "conn_001"

    @pytest.mark.asyncio
    async def test_delete_connection_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_client = AsyncMock()
        mock_client.delete.return_value = mock_resp
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_client
        mock_cm.__aexit__.return_value = None

        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import delete_connection
            result = await delete_connection("conn_001")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_refresh_connection_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "success": True,
            "code": 0,
            "message": "refreshed",
        })
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import refresh_connection
            result = await refresh_connection("conn_001")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_test_action_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "success": True,
            "code": 0,
            "data": {"result": "test_ok"},
        })
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import test_action
            result = await test_action("quickbooks", "list_invoices")
        assert result["success"] is True


class TestCoworkClient:
    @pytest.mark.asyncio
    async def test_register_module_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"id": "fsb", "name": "Small Business"},
        })
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import register_module
            result = await register_module(
                module_id="fsb",
                name="Small Business",
                icon="briefcase",
                route_path="/fsb",
            )
        assert result["status"] == "success"
        assert result["data"]["id"] == "fsb"

    @pytest.mark.asyncio
    async def test_push_notification_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"id": "notif_123"},
        })
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import push_notification
            result = await push_notification(
                space_id="ws_001",
                user_id="admin",
                notification_type="approval",
                title="Approval required",
            )
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_register_module_failure(self):
        mock_cm = _make_fail_client("post")
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import register_module
            result = await register_module("fsb", "test")
        assert result["status"] == "error"


class TestRAGClient:
    @pytest.mark.asyncio
    async def test_list_knowledge_bases_success(self):
        mock_cm, _ = _make_mock_client("get", [
            {"id": "kb_001", "name": "Sales KB"},
        ])
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import list_knowledge_bases
            result = await list_knowledge_bases()
        assert result["success"] is True
        assert len(result["data"]) == 1

    @pytest.mark.asyncio
    async def test_create_knowledge_base_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "id": "kb_002",
            "name": "Invoice KB",
            "status": "created",
        })
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import create_knowledge_base
            result = await create_knowledge_base(name="Invoice KB")
        assert result["success"] is True
        assert result["data"]["id"] == "kb_002"

    @pytest.mark.asyncio
    async def test_search_success(self):
        mock_cm, _ = _make_mock_client("post", [
            {"id": "chunk_1", "text": "invoice data", "score": 0.95},
        ])
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import search
            result = await search(kb_id="kb_001", query="overdue invoices")
        assert result["success"] is True
        assert len(result["data"]) == 1

    @pytest.mark.asyncio
    async def test_ask_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "answer": "You have 3 overdue invoices",
            "sources": [{"doc_name": "invoice_report.pdf", "score": 0.92}],
        })
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import ask
            result = await ask(kb_id="kb_001", question="How many overdue invoices?")
        assert result["success"] is True
        assert "overdue" in result["data"]["answer"]

    @pytest.mark.asyncio
    async def test_upload_document_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "doc_id": "doc_001",
            "chunks": 5,
            "chars": 1200,
        })
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import upload_document
            result = await upload_document(kb_id="kb_001", file_path="/tmp/test.json")
        assert result["success"] is True
        assert result["data"]["doc_id"] == "doc_001"

    @pytest.mark.asyncio
    async def test_delete_knowledge_base_success(self):
        mock_cm, _ = _make_mock_client("delete", {
            "id": "kb_001",
            "status": "deleted",
        })
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import delete_knowledge_base
            result = await delete_knowledge_base("kb_001")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_rag_health_success(self):
        mock_cm, _ = _make_mock_client("get", {
            "status": "ok",
            "knowledge_bases": 2,
            "embedding_available": True,
        })
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import rag_health
            result = await rag_health()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_search_failure(self):
        mock_cm = _make_fail_client("post")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import search
            result = await search(kb_id="kb_001", query="test")
        assert result["success"] is False


class TestArtifactClientExtended:
    @pytest.mark.asyncio
    async def test_export_session_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"count": 3, "path": "/tmp/exports/session_001"},
        })
        with patch("fsb.engine.artifact_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.artifact_client import export_session
            result = await export_session(session_id="session_001", output_dir="/tmp/exports/session_001")
        assert result["success"] is True
        assert result["data"]["count"] == 3

    @pytest.mark.asyncio
    async def test_export_session_rpc_error(self):
        mock_cm, _ = _make_mock_client("post", {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32602, "message": "Invalid params"},
        })
        with patch("fsb.engine.artifact_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.artifact_client import export_session
            result = await export_session(session_id="bad_session", output_dir="/tmp/x")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_export_session_failure(self):
        mock_cm = _make_fail_client("post")
        with patch("fsb.engine.artifact_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.artifact_client import export_session
            result = await export_session(session_id="s1", output_dir="/tmp/x")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_move_artifact_to_kb_success(self):
        mock_cm, _ = _make_mock_client("post", {"ok": True})
        with patch("fsb.engine.artifact_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.artifact_client import move_artifact_to_kb
            result = await move_artifact_to_kb(artifact_id="art_001", project_id="proj_001")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_move_artifact_to_kb_failure(self):
        mock_cm = _make_fail_client("post")
        with patch("fsb.engine.artifact_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.artifact_client import move_artifact_to_kb
            result = await move_artifact_to_kb(artifact_id="art_001", project_id="proj_001")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_list_artifacts_by_source_success(self):
        mock_cm, _ = _make_mock_client("get", {
            "artifacts": [
                {"id": "art_001", "name": "report", "source_module": "fsb"},
                {"id": "art_002", "name": "invoice", "source_module": "fsb"},
            ],
        })
        with patch("fsb.engine.artifact_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.artifact_client import list_artifacts_by_source
            result = await list_artifacts_by_source(source_module="fsb", workspace_id="ws_001")
        assert result["success"] is True
        assert len(result["data"]) == 2

    @pytest.mark.asyncio
    async def test_list_artifacts_by_source_failure(self):
        mock_cm = _make_fail_client("get")
        with patch("fsb.engine.artifact_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.artifact_client import list_artifacts_by_source
            result = await list_artifacts_by_source(source_module="fsb")
        assert result["success"] is False


class TestFSBConfig:
    def test_default_values(self):
        config = FSBConfig()
        assert "127.0.0.1" in config.ARTIFACTS_ENGINE_URL
        assert "11432" in config.FUSION_MLX_URL
        assert "11444" in config.FUSION_GATEWAY_URL
        assert "11437" in config.FUSION_COWORK_URL
        assert "11436" in config.FUSION_RAG_URL
        assert config.HTTP_TIMEOUT > 0
        assert config.EMBEDDING_MODEL == "BGE-M3"
        assert isinstance(config.STANDALONE_MODE, bool)
