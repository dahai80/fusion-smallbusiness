import logging
import os

logger = logging.getLogger(__name__)


class FSBConfig:
    ARTIFACTS_ENGINE_URL: str = os.environ.get(
        "FSB_ARTIFACTS_ENGINE_URL", "http://127.0.0.1:11451"
    )
    FUSION_MLX_URL: str = os.environ.get(
        "FSB_FUSION_MLX_URL", "http://localhost:11432"
    )
    FUSION_GATEWAY_URL: str = os.environ.get(
        "FSB_FUSION_GATEWAY_URL", "http://localhost:11444"
    )
    FUSION_COWORK_URL: str = os.environ.get(
        "FSB_FUSION_COWORK_URL", "http://localhost:11437"
    )
    FUSION_RAG_URL: str = os.environ.get(
        "FSB_FUSION_RAG_URL", "http://127.0.0.1:11436"
    )
    FUSION_RAG_API_KEY: str = os.environ.get(
        "FSB_FUSION_RAG_API_KEY", ""
    )
    LLM_DEFAULT_MODEL: str = os.environ.get(
        "FSB_LLM_DEFAULT_MODEL", "default"
    )
    EMBEDDING_MODEL: str = os.environ.get(
        "FSB_EMBEDDING_MODEL", "BGE-M3"
    )
    HTTP_TIMEOUT: int = int(os.environ.get("FSB_HTTP_TIMEOUT", "10"))
    STANDALONE_MODE: bool = os.environ.get("FSB_STANDALONE_MODE", "true").lower() in ("true", "1", "yes")
    SERVER_HOST: str = os.environ.get("FSB_SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.environ.get("FSB_SERVER_PORT", "11456"))


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
