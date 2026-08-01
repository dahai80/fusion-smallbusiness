import json
import logging
from typing import Any, Optional

import httpx

from ..config import fsb_config

logger = logging.getLogger(__name__)


async def list_models() -> dict[str, Any]:
    url = f"{fsb_config.FUSION_MLX_URL}/v1/models"
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            result = resp.json()
            logger.info("llm list models: count=%d", len(result.get("data", [])))
            return result
    except httpx.HTTPError as e:
        logger.error("llm list models failed: %s", e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error("llm list models unexpected error: %s", e)
        return {"status": "error", "message": str(e)}


async def get_model_info(model_id: str) -> dict[str, Any]:
    url = f"{fsb_config.FUSION_MLX_URL}/v1/models"
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            models = resp.json().get("data", [])
            for m in models:
                if m.get("id") == model_id:
                    logger.info("llm model info: id=%s", model_id)
                    return m
            logger.warning("llm model not found: id=%s", model_id)
            return {"status": "error", "message": f"model not found: {model_id}"}
    except httpx.HTTPError as e:
        logger.error("llm get model info failed: id=%s error=%s", model_id, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error("llm get model info unexpected error: %s", e)
        return {"status": "error", "message": str(e)}


async def create_embedding(
    input: str | list[str],
    model: str = "",
) -> dict[str, Any]:
    model = model or fsb_config.EMBEDDING_MODEL
    url = f"{fsb_config.FUSION_MLX_URL}/v1/embeddings"
    payload = {
        "model": model,
        "input": input,
    }
    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT * 2) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            logger.info("llm embedding: model=%s count=%d", model, len(result.get("data", [])))
            return result
    except httpx.HTTPError as e:
        logger.error("llm embedding failed: model=%s error=%s", model, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error("llm embedding unexpected error: %s", e)
        return {"status": "error", "message": str(e)}


async def chat_completion(
    model: str = "",
    messages: list[dict] = None,
    tools: list[dict] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    model = model or fsb_config.LLM_DEFAULT_MODEL
    url = f"{fsb_config.FUSION_MLX_URL}/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages or [],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools

    try:
        async with httpx.AsyncClient(timeout=fsb_config.HTTP_TIMEOUT * 2) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            logger.info("llm completion: model=%s tokens=%s", model, result.get("usage", {}))
            return result
    except httpx.HTTPError as e:
        logger.error("llm completion failed: model=%s error=%s", model, e)
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.error("llm completion unexpected error: %s", e)
        return {"status": "error", "message": str(e)}


async def execute_skill_prompt(
    skill_definition: str,
    input_data: dict,
    variables: dict = None,
    model: str = "",
) -> dict[str, Any]:
    user_content = json.dumps(input_data, ensure_ascii=False) if input_data else ""
    if variables:
        user_content += "\n\nVariables: " + json.dumps(variables, ensure_ascii=False)

    messages = [
        {"role": "system", "content": skill_definition},
        {"role": "user", "content": user_content},
    ]

    result = await chat_completion(model=model, messages=messages)
    if result.get("status") == "error":
        return result

    choices = result.get("choices", [])
    if not choices:
        return {"status": "error", "message": "no completion choices returned"}

    content = choices[0].get("message", {}).get("content", "")
    return {
        "status": "success",
        "content": content,
        "model": result.get("model", model),
        "usage": result.get("usage", {}),
    }
