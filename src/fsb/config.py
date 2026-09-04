import logging
import os
from typing import ClassVar

logger = logging.getLogger(__name__)


class FSBConfig:
    ARTIFACTS_ENGINE_URL: str = os.environ.get("FSB_ARTIFACTS_ENGINE_URL", "http://127.0.0.1:11451")
    FUSION_MLX_URL: str = os.environ.get("FSB_FUSION_MLX_URL", "http://localhost:11432")
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
    SERVER_PORT: int = int(os.environ.get("FSB_SERVER_PORT", "11490"))
    RATE_LIMIT_CAPACITY: int = int(os.environ.get("FSB_RATE_LIMIT_CAPACITY", "60"))
    RATE_LIMIT_REFILL: int = int(os.environ.get("FSB_RATE_LIMIT_REFILL", "10"))
    MAX_BODY_BYTES: int = int(os.environ.get("FSB_MAX_BODY_BYTES", str(2 * 1024 * 1024)))
    SECRET_KEY: str = os.environ.get("FSB_SECRET_KEY", "")
    RUN_RETENTION_DAYS: int = int(os.environ.get("FSB_RUN_RETENTION_DAYS", "30"))

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
