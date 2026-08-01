import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fsb.config import FSBConfig


def _make_mock_client(method: str, return_value, status_code: int = 200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = return_value
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    getattr(mock_client, method).return_value = mock_resp

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None

    return mock_cm, mock_resp


def _make_http_error_client(method: str):
    mock_client = AsyncMock()
    getattr(mock_client, method).side_effect = httpx.HTTPStatusError(
        "server error", request=MagicMock(), response=MagicMock(status_code=500)
    )
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None
    return mock_cm


def _make_generic_error_client(method: str):
    mock_client = AsyncMock()
    getattr(mock_client, method).side_effect = RuntimeError("unexpected crash")
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None
    return mock_cm


# ===== Gateway Client =====

class TestGatewayClientErrors:
    @pytest.mark.asyncio
    async def test_list_connectors_http_error(self):
        mock_cm = _make_http_error_client("get")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import list_connectors
            result = await list_connectors()
        assert result["success"] is False
        assert "code" in result

    @pytest.mark.asyncio
    async def test_list_connectors_generic_error(self):
        mock_cm = _make_generic_error_client("get")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import list_connectors
            result = await list_connectors()
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_action_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import execute_action
            result = await execute_action("qbo", "list")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_action_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import execute_action
            result = await execute_action("qbo", "list")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_action_unsuccessful_response(self):
        mock_cm, _ = _make_mock_client("post", {"success": False, "code": 1, "message": "auth failed"})
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import execute_action
            result = await execute_action("qbo", "list")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_test_action_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import test_action
            result = await test_action("qbo", "list")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_test_action_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import test_action
            result = await test_action("qbo", "list")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_list_connections_http_error(self):
        mock_cm = _make_http_error_client("get")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import list_connections
            result = await list_connections()
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_list_connections_generic_error(self):
        mock_cm = _make_generic_error_client("get")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import list_connections
            result = await list_connections()
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_list_connections_success(self):
        mock_cm, _ = _make_mock_client("get", {"connections": [{"id": "c1"}]})
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import list_connections
            result = await list_connections()
        assert "connections" in result

    @pytest.mark.asyncio
    async def test_create_connection_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import create_connection
            result = await create_connection("c1", "qbo")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_create_connection_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import create_connection
            result = await create_connection("c1", "qbo")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_create_connection_with_expires(self):
        mock_cm, _ = _make_mock_client("post", {"id": "c1", "status": "active"})
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import create_connection
            result = await create_connection("c1", "qbo", expires_at="2026-12-31")
        assert result["id"] == "c1"

    @pytest.mark.asyncio
    async def test_get_connection_http_error(self):
        mock_cm = _make_http_error_client("get")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import get_connection
            result = await get_connection("c1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_connection_generic_error(self):
        mock_cm = _make_generic_error_client("get")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import get_connection
            result = await get_connection("c1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_connection_http_error(self):
        mock_cm = _make_http_error_client("delete")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import delete_connection
            result = await delete_connection("c1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_connection_generic_error(self):
        mock_cm = _make_generic_error_client("delete")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import delete_connection
            result = await delete_connection("c1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_connection_non_204(self):
        mock_cm, _ = _make_mock_client("delete", {"success": True}, status_code=200)
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import delete_connection
            result = await delete_connection("c1")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_refresh_connection_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import refresh_connection
            result = await refresh_connection("c1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_refresh_connection_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import refresh_connection
            result = await refresh_connection("c1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_initiate_oauth2_success(self):
        mock_cm, _ = _make_mock_client("get", {
            "success": True, "authorizeUrl": "https://auth.example.com", "state": "abc"
        })
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import initiate_oauth2
            result = await initiate_oauth2("qbo", "https://cb.com", state="abc", scope="read")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_initiate_oauth2_http_error(self):
        mock_cm = _make_http_error_client("get")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import initiate_oauth2
            result = await initiate_oauth2("qbo", "https://cb.com")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_initiate_oauth2_generic_error(self):
        mock_cm = _make_generic_error_client("get")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import initiate_oauth2
            result = await initiate_oauth2("qbo", "https://cb.com")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_handle_oauth2_callback_success(self):
        mock_cm, _ = _make_mock_client("get", {
            "success": True, "connectionId": "conn_123"
        })
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import handle_oauth2_callback
            result = await handle_oauth2_callback(code="abc123", state="xyz")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_handle_oauth2_callback_http_error(self):
        mock_cm = _make_http_error_client("get")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import handle_oauth2_callback
            result = await handle_oauth2_callback(code="abc123")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_handle_oauth2_callback_generic_error(self):
        mock_cm = _make_generic_error_client("get")
        with patch("fsb.engine.gateway_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.gateway_client import handle_oauth2_callback
            result = await handle_oauth2_callback(code="abc123")
        assert result["success"] is False


# ===== RAG Client =====

class TestRAGClientErrors:
    @pytest.mark.asyncio
    async def test_list_knowledge_bases_http_error(self):
        mock_cm = _make_http_error_client("get")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import list_knowledge_bases
            result = await list_knowledge_bases()
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_list_knowledge_bases_generic_error(self):
        mock_cm = _make_generic_error_client("get")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import list_knowledge_bases
            result = await list_knowledge_bases()
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_create_knowledge_base_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import create_knowledge_base
            result = await create_knowledge_base("test")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_create_knowledge_base_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import create_knowledge_base
            result = await create_knowledge_base("test")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_knowledge_base_success(self):
        mock_cm, _ = _make_mock_client("get", {"id": "kb1", "name": "test"})
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import get_knowledge_base
            result = await get_knowledge_base("kb1")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_knowledge_base_http_error(self):
        mock_cm = _make_http_error_client("get")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import get_knowledge_base
            result = await get_knowledge_base("kb1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_knowledge_base_generic_error(self):
        mock_cm = _make_generic_error_client("get")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import get_knowledge_base
            result = await get_knowledge_base("kb1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_knowledge_base_http_error(self):
        mock_cm = _make_http_error_client("delete")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import delete_knowledge_base
            result = await delete_knowledge_base("kb1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_knowledge_base_generic_error(self):
        mock_cm = _make_generic_error_client("delete")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import delete_knowledge_base
            result = await delete_knowledge_base("kb1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_knowledge_base_stats_success(self):
        mock_cm, _ = _make_mock_client("get", {"documents": 10, "chunks": 50})
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import get_knowledge_base_stats
            result = await get_knowledge_base_stats("kb1")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_knowledge_base_stats_http_error(self):
        mock_cm = _make_http_error_client("get")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import get_knowledge_base_stats
            result = await get_knowledge_base_stats("kb1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_knowledge_base_stats_generic_error(self):
        mock_cm = _make_generic_error_client("get")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import get_knowledge_base_stats
            result = await get_knowledge_base_stats("kb1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_upload_document_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import upload_document
            result = await upload_document("kb1", "/tmp/test.json")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_upload_document_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import upload_document
            result = await upload_document("kb1", "/tmp/test.json")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_upload_documents_batch_success(self):
        mock_cm, _ = _make_mock_client("post", {"indexed": 3, "failed": 0})
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import upload_documents_batch
            result = await upload_documents_batch("kb1", ["/tmp/a.json", "/tmp/b.json"])
        assert result["success"] is True
        assert result["data"]["indexed"] == 3

    @pytest.mark.asyncio
    async def test_upload_documents_batch_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import upload_documents_batch
            result = await upload_documents_batch("kb1", ["/tmp/a.json"])
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_upload_documents_batch_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import upload_documents_batch
            result = await upload_documents_batch("kb1", ["/tmp/a.json"])
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_list_documents_success(self):
        mock_cm, _ = _make_mock_client("get", [{"id": "doc1"}, {"id": "doc2"}])
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import list_documents
            result = await list_documents("kb1")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_list_documents_http_error(self):
        mock_cm = _make_http_error_client("get")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import list_documents
            result = await list_documents("kb1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_list_documents_generic_error(self):
        mock_cm = _make_generic_error_client("get")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import list_documents
            result = await list_documents("kb1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_document_success(self):
        mock_cm, _ = _make_mock_client("delete", {"id": "doc1", "status": "deleted"})
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import delete_document
            result = await delete_document("kb1", "doc1")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delete_document_http_error(self):
        mock_cm = _make_http_error_client("delete")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import delete_document
            result = await delete_document("kb1", "doc1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_document_generic_error(self):
        mock_cm = _make_generic_error_client("delete")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import delete_document
            result = await delete_document("kb1", "doc1")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_search_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import search
            result = await search("kb1", "test query")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_search_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import search
            result = await search("kb1", "test query")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_search_with_folder_prefix(self):
        mock_cm, _ = _make_mock_client("post", [{"id": "c1", "score": 0.9}])
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import search
            result = await search("kb1", "test", folder_prefix="invoices")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_ask_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import ask
            result = await ask("kb1", "what?")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ask_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import ask
            result = await ask("kb1", "what?")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_ask_with_model_and_history(self):
        mock_cm, _ = _make_mock_client("post", {
            "answer": "yes", "sources": []
        })
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import ask
            result = await ask("kb1", "what?", model="qwen3", history=[{"q": "hi"}], folder_prefix="docs")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_rag_health_http_error(self):
        mock_cm = _make_http_error_client("get")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import rag_health
            result = await rag_health()
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_rag_health_generic_error(self):
        mock_cm = _make_generic_error_client("get")
        with patch("fsb.engine.rag_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.rag_client import rag_health
            result = await rag_health()
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_rag_helpers(self):
        from fsb.engine.rag_client import _rag_url, _api_headers
        url = _rag_url("/kb/bases")
        assert "/kb/bases" in url
        headers = _api_headers()
        assert isinstance(headers, dict)


# ===== Cowork Client =====

class TestCoworkClientErrors:
    @pytest.mark.asyncio
    async def test_push_notification_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import push_notification
            result = await push_notification("ws1", "admin", "approval", "title")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_push_notification_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import push_notification
            result = await push_notification("ws1", "admin", "approval", "title")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_register_module_rpc_error(self):
        mock_cm, _ = _make_mock_client("post", {
            "jsonrpc": "2.0", "id": 1,
            "error": {"code": -32600, "message": "invalid request"}
        })
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import register_module
            result = await register_module("fsb", "test")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_register_module_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import register_module
            result = await register_module("fsb", "test")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_sync_knowledge_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "jsonrpc": "2.0", "id": 3, "result": {"syncedCount": 2}
        })
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import sync_knowledge
            result = await sync_knowledge("sp1", [{"name": "doc.pdf", "content": "base64"}])
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_sync_knowledge_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import sync_knowledge
            result = await sync_knowledge("sp1", [])
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_sync_knowledge_rpc_error(self):
        mock_cm, _ = _make_mock_client("post", {
            "jsonrpc": "2.0", "id": 3,
            "error": {"code": -32602, "message": "Invalid params"}
        })
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import sync_knowledge
            result = await sync_knowledge("sp1", [])
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_import_snapshot_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "jsonrpc": "2.0", "id": 4, "result": {"importedCount": 1}
        })
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import import_snapshot
            result = await import_snapshot("sp1", {"title": "PRD"})
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_import_snapshot_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import import_snapshot
            result = await import_snapshot("sp1", {"title": "PRD"})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_export_to_project_success(self):
        mock_cm, _ = _make_mock_client("post", {
            "jsonrpc": "2.0", "id": 5, "result": {"exportedItems": ["file1"]}
        })
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import export_to_project
            result = await export_to_project("sp1", {"files": True}, "proj1")
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_export_to_project_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.cowork_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.cowork_client import export_to_project
            result = await export_to_project("sp1", {"files": True}, "proj1")
        assert result["status"] == "error"


# ===== LLM Client =====

class TestLLMClientErrors:
    @pytest.mark.asyncio
    async def test_list_models_http_error(self):
        mock_cm = _make_http_error_client("get")
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import list_models
            result = await list_models()
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_list_models_generic_error(self):
        mock_cm = _make_generic_error_client("get")
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import list_models
            result = await list_models()
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_model_info_http_error(self):
        mock_cm = _make_http_error_client("get")
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import get_model_info
            result = await get_model_info("test")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_get_model_info_generic_error(self):
        mock_cm = _make_generic_error_client("get")
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import get_model_info
            result = await get_model_info("test")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_create_embedding_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import create_embedding
            result = await create_embedding("hello")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_create_embedding_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import create_embedding
            result = await create_embedding("hello")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_chat_completion_http_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import chat_completion
            result = await chat_completion("test", [{"role": "user", "content": "hi"}])
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_chat_completion_generic_error(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.llm_client.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.llm_client import chat_completion
            result = await chat_completion("test", [{"role": "user", "content": "hi"}])
        assert result["status"] == "error"


# ===== Webhook Dispatcher =====

class TestWebhookDispatcher:
    @pytest.mark.asyncio
    async def test_dispatch_success(self):
        mock_cm, _ = _make_mock_client("post", {"ok": True}, status_code=200)
        with patch("fsb.engine.webhook_dispatcher.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.webhook_dispatcher import dispatch_webhook
            result = await dispatch_webhook(
                {"webhookId": "wh1", "url": "https://example.com/hook"},
                "run.completed",
                {"runId": "r1", "endTime": "2026-01-01"},
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_dispatch_with_secret(self):
        mock_cm, _ = _make_mock_client("post", {"ok": True}, status_code=200)
        with patch("fsb.engine.webhook_dispatcher.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.webhook_dispatcher import dispatch_webhook
            result = await dispatch_webhook(
                {"webhookId": "wh1", "url": "https://example.com/hook", "secret": "mysecret"},
                "run.completed",
                {"runId": "r1", "endTime": "2026-01-01"},
            )
        assert result is True
        call_args = mock_cm.__aenter__.return_value.post.call_args
        assert "X-FSB-Signature" in call_args.kwargs.get("headers", call_args[1].get("headers", {}))

    @pytest.mark.asyncio
    async def test_dispatch_server_error(self):
        mock_cm, _ = _make_mock_client("post", {"error": "bad"}, status_code=500)
        with patch("fsb.engine.webhook_dispatcher.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.webhook_dispatcher import dispatch_webhook
            result = await dispatch_webhook(
                {"webhookId": "wh1", "url": "https://example.com/hook"},
                "run.failed",
                {"runId": "r1"},
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_dispatch_connection_error(self):
        mock_cm = _make_http_error_client("post")
        with patch("fsb.engine.webhook_dispatcher.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.webhook_dispatcher import dispatch_webhook
            result = await dispatch_webhook(
                {"webhookId": "wh1", "url": "https://example.com/hook"},
                "run.completed",
                {"runId": "r1"},
            )
        assert result is False

    @pytest.mark.asyncio
    async def test_dispatch_no_url(self):
        from fsb.engine.webhook_dispatcher import dispatch_webhook
        result = await dispatch_webhook(
            {"webhookId": "wh1", "url": ""},
            "run.completed",
            {"runId": "r1"},
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_dispatch_generic_exception(self):
        mock_cm = _make_generic_error_client("post")
        with patch("fsb.engine.webhook_dispatcher.httpx.AsyncClient", return_value=mock_cm):
            from fsb.engine.webhook_dispatcher import dispatch_webhook
            result = await dispatch_webhook(
                {"webhookId": "wh1", "url": "https://example.com/hook"},
                "run.completed",
                {"runId": "r1"},
            )
        assert result is False
