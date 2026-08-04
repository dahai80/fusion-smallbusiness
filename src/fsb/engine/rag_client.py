import logging
from typing import Any

import httpx

from ..config import fsb_config

logger = logging.getLogger(__name__)


def _rag_url(path: str) -> str:
    return f"{fsb_config.FUSION_RAG_URL}{path}"


def _api_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if fsb_config.FUSION_RAG_API_KEY:
        headers["X-API-Key"] = fsb_config.FUSION_RAG_API_KEY
    return headers


async def list_knowledge_bases() -> dict[str, Any]:
    url = _rag_url("/kb/bases")
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return {"success": True, "data": resp.json()}
    except httpx.HTTPError as e:
        logger.error("rag list knowledge bases failed: %s", e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("rag list knowledge bases unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def create_knowledge_base(
    name: str,
    description: str = "",
    chunk_strategy: str = "semantic",
    embedding_model: str = "BGE-M3",
) -> dict[str, Any]:
    url = _rag_url("/kb/bases")
    payload = {
        "name": name,
        "description": description,
        "chunk_strategy": chunk_strategy,
        "embedding_model": embedding_model,
    }
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=_api_headers())
            resp.raise_for_status()
            result = resp.json()
            logger.info("rag knowledge base created: id=%s name=%s", result.get("id"), name)
            return {"success": True, "data": result}
    except httpx.HTTPError as e:
        logger.error("rag create knowledge base failed: name=%s error=%s", name, e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("rag create knowledge base unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def get_knowledge_base(kb_id: str) -> dict[str, Any]:
    url = _rag_url(f"/kb/bases/{kb_id}")
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return {"success": True, "data": resp.json()}
    except httpx.HTTPError as e:
        logger.error("rag get knowledge base failed: id=%s error=%s", kb_id, e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("rag get knowledge base unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def delete_knowledge_base(kb_id: str) -> dict[str, Any]:
    url = _rag_url(f"/kb/bases/{kb_id}")
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.delete(url, headers=_api_headers())
            resp.raise_for_status()
            result = resp.json()
            logger.info("rag knowledge base deleted: id=%s", kb_id)
            return {"success": True, "data": result}
    except httpx.HTTPError as e:
        logger.error("rag delete knowledge base failed: id=%s error=%s", kb_id, e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("rag delete knowledge base unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def get_knowledge_base_stats(kb_id: str) -> dict[str, Any]:
    url = _rag_url(f"/kb/bases/{kb_id}/stats")
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return {"success": True, "data": resp.json()}
    except httpx.HTTPError as e:
        logger.error("rag get knowledge base stats failed: id=%s error=%s", kb_id, e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("rag get knowledge base stats unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def upload_document(
    kb_id: str,
    file_path: str,
    contextualize: bool = True,
) -> dict[str, Any]:
    url = _rag_url(f"/kb/bases/{kb_id}/documents")
    payload = {
        "file_path": file_path,
        "contextualize": contextualize,
    }
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT * 3) as client:
            resp = await client.post(url, json=payload, headers=_api_headers())
            resp.raise_for_status()
            result = resp.json()
            logger.info("rag document uploaded: kb=%s doc=%s chunks=%d",
                        kb_id, result.get("doc_id"), result.get("chunks", 0))
            return {"success": True, "data": result}
    except httpx.HTTPError as e:
        logger.error("rag upload document failed: kb=%s file=%s error=%s", kb_id, file_path, e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("rag upload document unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def upload_documents_batch(
    kb_id: str,
    file_paths: list[str],
    contextualize: bool = True,
) -> dict[str, Any]:
    url = _rag_url(f"/kb/bases/{kb_id}/documents/batch")
    payload = {
        "file_paths": file_paths,
        "contextualize": contextualize,
    }
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT * 5) as client:
            resp = await client.post(url, json=payload, headers=_api_headers())
            resp.raise_for_status()
            result = resp.json()
            logger.info("rag batch upload: kb=%s indexed=%d", kb_id, result.get("indexed", 0))
            return {"success": True, "data": result}
    except httpx.HTTPError as e:
        logger.error("rag batch upload failed: kb=%s error=%s", kb_id, e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("rag batch upload unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def list_documents(kb_id: str) -> dict[str, Any]:
    url = _rag_url(f"/kb/bases/{kb_id}/documents")
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return {"success": True, "data": resp.json()}
    except httpx.HTTPError as e:
        logger.error("rag list documents failed: kb=%s error=%s", kb_id, e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("rag list documents unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def delete_document(kb_id: str, doc_id: str) -> dict[str, Any]:
    url = _rag_url(f"/kb/bases/{kb_id}/documents/{doc_id}")
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.delete(url, headers=_api_headers())
            resp.raise_for_status()
            result = resp.json()
            logger.info("rag document deleted: kb=%s doc=%s", kb_id, doc_id)
            return {"success": True, "data": result}
    except httpx.HTTPError as e:
        logger.error("rag delete document failed: kb=%s doc=%s error=%s", kb_id, doc_id, e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("rag delete document unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def search(
    kb_id: str,
    query: str,
    top_k: int = 5,
    threshold: float = 0.0,
    hybrid: bool = False,
    rerank: bool = False,
    folder_prefix: str | None = None,
) -> dict[str, Any]:
    url = _rag_url(f"/kb/bases/{kb_id}/search")
    payload: dict[str, Any] = {
        "query": query,
        "top_k": top_k,
        "threshold": threshold,
        "hybrid": hybrid,
        "rerank": rerank,
    }
    if folder_prefix:
        payload["folder_prefix"] = folder_prefix

    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT * 2) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            results = resp.json()
            logger.info("rag search: kb=%s query=%s results=%d", kb_id, query[:50], len(results))
            return {"success": True, "data": results}
    except httpx.HTTPError as e:
        logger.error("rag search failed: kb=%s query=%s error=%s", kb_id, query[:50], e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("rag search unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def ask(
    kb_id: str,
    question: str,
    top_k: int = 5,
    model: str = "",
    hybrid: bool = False,
    rerank: bool = False,
    folder_prefix: str | None = None,
    history: list | None = None,
) -> dict[str, Any]:
    url = _rag_url(f"/kb/bases/{kb_id}/ask")
    payload: dict[str, Any] = {
        "question": question,
        "top_k": top_k,
        "hybrid": hybrid,
        "rerank": rerank,
    }
    if model:
        payload["model"] = model
    if folder_prefix:
        payload["folder_prefix"] = folder_prefix
    if history:
        payload["history"] = history

    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT * 3) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            logger.info("rag ask: kb=%s question=%s sources=%d",
                        kb_id, question[:50], len(result.get("sources", [])))
            return {"success": True, "data": result}
    except httpx.HTTPError as e:
        logger.error("rag ask failed: kb=%s question=%s error=%s", kb_id, question[:50], e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("rag ask unexpected error: %s", e)
        return {"success": False, "message": str(e)}


async def rag_health() -> dict[str, Any]:
    url = _rag_url("/kb/status")
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return {"success": True, "data": resp.json()}
    except httpx.HTTPError as e:
        logger.error("rag health check failed: %s", e)
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error("rag health check unexpected error: %s", e)
        return {"success": False, "message": str(e)}
