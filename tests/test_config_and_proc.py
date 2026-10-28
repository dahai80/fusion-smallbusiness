
import pytest

from fsb.config import _resolve_db_path, _resolve_mlx_url, _resolve_server_port
from fsb.engine.llm_client import _auth_headers


def _clear_env(monkeypatch):
    for var in (
        "FUSION_GATEWAY_BASE_URL",
        "FUSION_GATEWAY_URL",
        "FUSION_MLX_URL",
        "FSB_FUSION_MLX_URL",
        "FUSION_SMALLBUSINESS_PORT",
        "FSB_SERVER_PORT",
        "FUSION_SMALLBUSINESS_DATA_DIR",
        "FSB_DB_PATH",
        "FUSION_CLIENT_KEY",
        "FUSION_MLX_API_KEY",
        "MLX_API_KEY",
        "FUSION_PROFILE",
    ):
        monkeypatch.delenv(var, raising=False)


class TestResolveServerPort:
    def test_canonical_env_wins(self, monkeypatch):
        _clear_env(monkeypatch)
        monkeypatch.setenv("FUSION_SMALLBUSINESS_PORT", "11555")
        monkeypatch.setenv("FSB_SERVER_PORT", "11499")
        assert _resolve_server_port() == 11555

    def test_legacy_fallback(self, monkeypatch):
        _clear_env(monkeypatch)
        monkeypatch.setenv("FSB_SERVER_PORT", "11499")
        assert _resolve_server_port() == 11499

    def test_default(self, monkeypatch):
        _clear_env(monkeypatch)
        assert _resolve_server_port() == 11490

    def test_canonical_malformed_raises(self, monkeypatch):
        _clear_env(monkeypatch)
        monkeypatch.setenv("FUSION_SMALLBUSINESS_PORT", "abc")
        with pytest.raises(ValueError):
            _resolve_server_port()


class TestResolveMlxUrl:
    def test_canonical_gateway_base_url_wins(self, monkeypatch):
        _clear_env(monkeypatch)
        monkeypatch.setenv("FUSION_GATEWAY_BASE_URL", "http://10.0.0.5:11432")
        monkeypatch.setenv("FSB_FUSION_MLX_URL", "http://legacy:11432")
        assert _resolve_mlx_url() == "http://10.0.0.5:11432"

    def test_legacy_fsb_env(self, monkeypatch):
        _clear_env(monkeypatch)
        monkeypatch.setenv("FSB_FUSION_MLX_URL", "http://legacy:11432")
        assert _resolve_mlx_url() == "http://legacy:11432"

    def test_default(self, monkeypatch):
        _clear_env(monkeypatch)
        assert _resolve_mlx_url() == "http://127.0.0.1:11432"


class TestResolveDbPath:
    def test_data_dir_env(self, monkeypatch, tmp_path):
        _clear_env(monkeypatch)
        monkeypatch.setenv("FUSION_SMALLBUSINESS_DATA_DIR", str(tmp_path))
        assert _resolve_db_path() == str(tmp_path)

    def test_legacy_fallback(self, monkeypatch):
        _clear_env(monkeypatch)
        monkeypatch.setenv("FSB_DB_PATH", "/tmp/legacy.db")
        assert _resolve_db_path() == "/tmp/legacy.db"

    def test_default(self, monkeypatch):
        _clear_env(monkeypatch)
        assert _resolve_db_path() == "fsb_data.db"


class TestLlmAuthHeaders:
    def test_empty_in_dev(self, monkeypatch):
        _clear_env(monkeypatch)
        assert _auth_headers() == {}

    def test_bearer_from_client_key(self, monkeypatch):
        _clear_env(monkeypatch)
        monkeypatch.setenv("FUSION_CLIENT_KEY", "fm-test-key")
        assert _auth_headers() == {"Authorization": "Bearer fm-test-key"}

    def test_prod_missing_key_raises(self, monkeypatch):
        _clear_env(monkeypatch)
        monkeypatch.setenv("FUSION_PROFILE", "prod")
        with pytest.raises(RuntimeError):
            _auth_headers()
