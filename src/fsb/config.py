import logging
import os
from typing import ClassVar

from fusion_core.config import gateway_base_url, service_data_dir, service_port

logger = logging.getLogger(__name__)

_APP = "smallbusiness"


def _resolve_mlx_url() -> str:
    if os.environ.get("FUSION_GATEWAY_BASE_URL"):
        return gateway_base_url()
    return os.environ.get("FSB_FUSION_MLX_URL", gateway_base_url())


def _resolve_server_port() -> int:
    if os.environ.get("FUSION_SMALLBUSINESS_PORT"):
        return service_port(_APP, default=11490)
    return int(os.environ.get("FSB_SERVER_PORT", "11490"))


def _resolve_db_path() -> str:
    if os.environ.get("FUSION_SMALLBUSINESS_DATA_DIR"):
        return str(service_data_dir(_APP))
    return os.environ.get("FSB_DB_PATH", "fsb_data.db")


class FSBConfig:
    ARTIFACTS_ENGINE_URL: str = os.environ.get("FSB_ARTIFACTS_ENGINE_URL", "http://127.0.0.1:11451")
    FUSION_MLX_URL: str = _resolve_mlx_url()
    FUSION_GATEWAY_URL: str = os.environ.get("FSB_FUSION_GATEWAY_URL", "http://localhost:11444")
    FUSION_COWORK_URL: str = os.environ.get("FSB_FUSION_COWORK_URL", "http://localhost:11437")
    FUSION_CHAT_URL: str = os.environ.get("FSB_FUSION_CHAT_URL", "http://127.0.0.1:11460")
    FUSION_RAG_URL: str = os.environ.get("FSB_FUSION_RAG_URL", "http://127.0.0.1:11436")
    FUSION_RAG_API_KEY: str = os.environ.get("FSB_FUSION_RAG_API_KEY", "")
    FUSION_IDENTITY_URL: str = os.environ.get("FSB_FUSION_IDENTITY_URL", "http://127.0.0.1:11470")
    FUSION_IDENTITY_SERVICE_TOKEN: str = os.environ.get("FSB_FUSION_IDENTITY_SERVICE_TOKEN", "")
    AUTH_REQUIRE_JWT: bool = os.environ.get("FSB_AUTH_REQUIRE_JWT", "true").lower() in ("true", "1", "yes")
    LLM_DEFAULT_MODEL: str = os.environ.get("FSB_LLM_DEFAULT_MODEL", "default")
    EMBEDDING_MODEL: str = os.environ.get("FSB_EMBEDDING_MODEL", "BGE-M3")
    HTTP_TIMEOUT: int = int(os.environ.get("FSB_HTTP_TIMEOUT", "10"))
    STANDALONE_MODE: bool = os.environ.get("FSB_STANDALONE_MODE", "false").lower() in ("true", "1", "yes")
    SERVER_HOST: str = os.environ.get("FSB_SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = _resolve_server_port()
    RATE_LIMIT_CAPACITY: int = int(os.environ.get("FSB_RATE_LIMIT_CAPACITY", "60"))
    RATE_LIMIT_REFILL: int = int(os.environ.get("FSB_RATE_LIMIT_REFILL", "10"))
    MAX_BODY_BYTES: int = int(os.environ.get("FSB_MAX_BODY_BYTES", str(2 * 1024 * 1024)))
    SECRET_KEY: str = os.environ.get("FSB_SECRET_KEY", "")
    RUN_RETENTION_DAYS: int = int(os.environ.get("FSB_RUN_RETENTION_DAYS", "30"))
    DB_BACKEND: str = os.environ.get("FSB_DB_BACKEND", "sqlite")
    DB_PATH: str = _resolve_db_path()
    DB_POOL_SIZE: int = int(os.environ.get("FSB_DB_POOL_SIZE", "8"))
    PG_DSN: str = os.environ.get("FSB_PG_DSN", "")
    PG_POOL_SIZE: int = int(os.environ.get("FSB_PG_POOL_SIZE", "10"))
    SCHEDULER_LEADER_TTL: int = int(os.environ.get("FSB_SCHEDULER_LEADER_TTL", "30"))
    EVENT_DEDUP_TTL: int = int(os.environ.get("FSB_EVENT_DEDUP_TTL", "120"))
    RATE_LIMIT_DISTRIBUTED: bool = os.environ.get("FSB_RATE_LIMIT_DISTRIBUTED", "false").lower() in ("true", "1", "yes")

    _FIELD_DEFAULTS: ClassVar[dict] = {
        "ARTIFACTS_ENGINE_URL": ("FSB_ARTIFACTS_ENGINE_URL", "http://127.0.0.1:11451", str),
        "FUSION_MLX_URL": ("FSB_FUSION_MLX_URL", "http://localhost:11432", str),
        "FUSION_GATEWAY_URL": ("FSB_FUSION_GATEWAY_URL", "http://localhost:11444", str),
        "FUSION_COWORK_URL": ("FSB_FUSION_COWORK_URL", "http://localhost:11437", str),
        "FUSION_CHAT_URL": ("FSB_FUSION_CHAT_URL", "http://127.0.0.1:11460", str),
        "FUSION_RAG_URL": ("FSB_FUSION_RAG_URL", "http://127.0.0.1:11436", str),
        "FUSION_RAG_API_KEY": ("FSB_FUSION_RAG_API_KEY", "", str),
        "FUSION_IDENTITY_URL": ("FSB_FUSION_IDENTITY_URL", "http://127.0.0.1:11470", str),
        "FUSION_IDENTITY_SERVICE_TOKEN": ("FSB_FUSION_IDENTITY_SERVICE_TOKEN", "", str),
        "AUTH_REQUIRE_JWT": ("FSB_AUTH_REQUIRE_JWT", "true", "bool"),
        "LLM_DEFAULT_MODEL": ("FSB_LLM_DEFAULT_MODEL", "default", str),
        "EMBEDDING_MODEL": ("FSB_EMBEDDING_MODEL", "BGE-M3", str),
        "HTTP_TIMEOUT": ("FSB_HTTP_TIMEOUT", "10", int),
        "STANDALONE_MODE": ("FSB_STANDALONE_MODE", "false", "bool"),
        "SERVER_HOST": ("FSB_SERVER_HOST", "0.0.0.0", str),
        "SERVER_PORT": ("FSB_SERVER_PORT", "11490", int),
        "RATE_LIMIT_CAPACITY": ("FSB_RATE_LIMIT_CAPACITY", "60", int),
        "RATE_LIMIT_REFILL": ("FSB_RATE_LIMIT_REFILL", "10", int),
        "MAX_BODY_BYTES": ("FSB_MAX_BODY_BYTES", str(2 * 1024 * 1024), int),
        "SECRET_KEY": ("FSB_SECRET_KEY", "", str),
        "RUN_RETENTION_DAYS": ("FSB_RUN_RETENTION_DAYS", "30", int),
        "DB_BACKEND": ("FSB_DB_BACKEND", "sqlite", str),
        "DB_PATH": ("FSB_DB_PATH", "fsb_data.db", str),
        "DB_POOL_SIZE": ("FSB_DB_POOL_SIZE", "8", int),
        "PG_DSN": ("FSB_PG_DSN", "", str),
        "PG_POOL_SIZE": ("FSB_PG_POOL_SIZE", "10", int),
        "SCHEDULER_LEADER_TTL": ("FSB_SCHEDULER_LEADER_TTL", "30", int),
        "EVENT_DEDUP_TTL": ("FSB_EVENT_DEDUP_TTL", "120", int),
        "RATE_LIMIT_DISTRIBUTED": ("FSB_RATE_LIMIT_DISTRIBUTED", "false", "bool"),
    }

    def reload(self) -> None:
        for field, (env, default, cast) in self._FIELD_DEFAULTS.items():
            raw = os.environ.get(env, default)
            if cast is int:
                value = int(raw)
            elif cast == "bool":
                value = str(raw).lower() in ("true", "1", "yes")
            else:
                value = str(raw)
            setattr(self, field, value)
        self.FUSION_MLX_URL = _resolve_mlx_url()
        self.SERVER_PORT = _resolve_server_port()
        self.DB_PATH = _resolve_db_path()
        logger.info("fsb config reloaded from env")


fsb_config = FSBConfig()

logger.info(
    "fsb config: artifacts=%s mlx=%s gateway=%s cowork=%s rag=%s model=%s standalone=%s",
    fsb_config.ARTIFACTS_ENGINE_URL,
    fsb_config.FUSION_MLX_URL,
    fsb_config.FUSION_GATEWAY_URL,
    fsb_config.FUSION_COWORK_URL,
    fsb_config.FUSION_RAG_URL,
    fsb_config.LLM_DEFAULT_MODEL,
    fsb_config.STANDALONE_MODE,
)
