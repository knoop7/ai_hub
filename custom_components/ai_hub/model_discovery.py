"""Best-effort remote model discovery for config flows."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse, urlunparse

import aiohttp

from .consts import CONF_CHAT_URL, CONF_CUSTOM_API_KEY, CONF_LLM_PROVIDER, SILICONFLOW_STT_MODELS
from .http import build_json_headers, client_timeout
from .providers.openai_compatible import _normalize_openai_api_url

_LOGGER = logging.getLogger(__name__)
_MODEL_DISCOVERY_TIMEOUT = 8.0


def _build_openai_models_url(url: str) -> str:
    """Build a /models URL from an OpenAI-compatible chat URL."""
    normalized = _normalize_openai_api_url(url)
    parsed = urlparse(normalized)
    path = parsed.path.rstrip("/")

    for suffix in ("/chat/completions", "/completions", "/responses"):
        if path.endswith(suffix):
            path = f"{path[:-len(suffix)]}/models"
            break
    else:
        if path.endswith("/v1"):
            path = f"{path}/models"
        elif not path:
            path = "/v1/models"
        else:
            path = f"{path}/models"

    return urlunparse(parsed._replace(path=path, params="", query="", fragment=""))


def _build_ollama_models_url(url: str) -> str:
    """Build an Ollama /api/tags URL from an Ollama endpoint."""
    parsed = urlparse(url.rstrip("/"))
    path = parsed.path.rstrip("/")
    if path.endswith("/api/chat"):
        path = f"{path[:-len('/api/chat')]}/api/tags"
    elif not path:
        path = "/api/tags"
    else:
        path = f"{path}/api/tags"
    return urlunparse(parsed._replace(path=path, params="", query="", fragment=""))


async def _fetch_json(url: str, headers: dict[str, str]) -> dict[str, Any] | None:
    """Fetch JSON best-effort and return None on any failure."""
    try:
        async with aiohttp.ClientSession(timeout=client_timeout(_MODEL_DISCOVERY_TIMEOUT)) as session:
            async with session.get(url, headers=headers, ssl=False if url.startswith("http://") else None) as response:
                if response.status != 200:
                    return None
                return await response.json()
    except Exception as err:
        _LOGGER.debug("Model discovery failed for %s: %s", url, err)
        return None


def _extract_openai_models(data: dict[str, Any]) -> list[str]:
    """Extract model ids from OpenAI-style /models payloads."""
    models: list[str] = []
    for item in data.get("data", []):
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip():
            models.append(item["id"])
    return models


def _extract_ollama_models(data: dict[str, Any]) -> list[str]:
    """Extract model ids from Ollama /api/tags payloads."""
    models: list[str] = []
    for item in data.get("models", []):
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip():
            models.append(item["name"])
    return models


async def async_discover_chat_models(options: dict[str, Any]) -> list[str] | None:
    """Discover chat models best-effort without raising exceptions."""
    provider = options.get(CONF_LLM_PROVIDER)
    api_key = str(options.get(CONF_CUSTOM_API_KEY, "") or "").strip()
    chat_url = options.get(CONF_CHAT_URL)
    if not isinstance(chat_url, str) or not chat_url.strip():
        return None

    if provider == "openai_compatible":
        data = await _fetch_json(_build_openai_models_url(chat_url), build_json_headers(api_key))
        models = _extract_openai_models(data) if data else []
        return sorted(set(models)) or None

    if provider == "ollama_compatible":
        data = await _fetch_json(_build_ollama_models_url(chat_url), {})
        models = _extract_ollama_models(data) if data else []
        return sorted(set(models)) or None

    return None


async def async_discover_stt_models(options: dict[str, Any]) -> list[str] | None:
    """Discover STT models best-effort without raising exceptions."""
    del options
    return list(SILICONFLOW_STT_MODELS)
