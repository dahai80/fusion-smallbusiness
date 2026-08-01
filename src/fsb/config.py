import logging
import os

logger = logging.getLogger(__name__)


class FSBConfig:
    ARTIFACTS_ENGINE_URL: str = os.environ.get(
        "FSB_ARTIFACTS_ENGINE_URL", "http://127.0.0.1:8892"
    )
    FUSION_MLX_URL: str = os.environ.get(
        "FSB_FUSION_MLX_URL", "http://localhost:11434"
    )
    FUSION_GATEWAY_URL: str = os.environ.get(
        "FSB_FUSION_GATEWAY_URL", "http://localhost:8080"
    )
    FUSION_COWORK_URL: str = os.environ.get(
        "FSB_FUSION_COWORK_URL", "http://localhost:9760"
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


fsb_config = FSBConfig()

logger.info(
    "fsb config: artifacts=%s mlx=%s gateway=%s cowork=%s rag=%s model=%s",
    fsb_config.ARTIFACTS_ENGINE_URL,
    fsb_config.FUSION_MLX_URL,
    fsb_config.FUSION_GATEWAY_URL,
    fsb_config.FUSION_COWORK_URL,
    fsb_config.FUSION_RAG_URL,
    fsb_config.LLM_DEFAULT_MODEL,
)
