"""Shared HTTP helpers for AI Hub."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from urllib.parse import urlparse
from typing import Any, Final

import aiohttp

_KNOWN_PROVIDER_NAMES: Final = {"openai_compatible", "anthropic_compatible", "ollama_compatible"}


def client_timeout(total: float) -> aiohttp.ClientTimeout:
    """Build a client timeout with a total timeout only."""
    return aiohttp.ClientTimeout(total=total)


async def async_post_json(
    url: str,
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
    ssl: bool | None,
    timeout: float,
    error_label: str,
    response_decoder: Callable[[aiohttp.ClientResponse], Awaitable[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """POST JSON and decode a JSON response."""
    async with aiohttp.ClientSession(timeout=client_timeout(timeout)) as session:
        async with session.post(url, json=payload, headers=headers, ssl=ssl) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"{error_label}: {error_text}")

            if response_decoder is not None:
                return await response_decoder(response)

            return await response.json()


async def async_stream_response_text(
    url: str,
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
    ssl: bool | None,
    timeout: float,
    error_label: str,
) -> AsyncGenerator[str, None]:
    """POST JSON and yield decoded response chunks."""
    async with aiohttp.ClientSession(timeout=client_timeout(timeout)) as session:
        async with session.post(url, json=payload, headers=headers, ssl=ssl) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"{error_label}: {error_text}")

            async for chunk in response.content:
                if chunk:
                    yield chunk.decode("utf-8", errors="ignore")


async def async_check_endpoint_health(
    url: str,
    *,
    ssl: bool | None,
    timeout: float = 10,
) -> bool:
    """Check whether an endpoint base URL is reachable."""
    async with aiohttp.ClientSession(timeout=client_timeout(timeout)) as session:
        async with session.get(url, ssl=ssl) as response:
            return response.status < 500


def build_json_headers(api_key: str | None = None) -> dict[str, str]:
    """Build standard JSON request headers."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def resolve_ssl_setting(api_url: str, default_url: str | None = None) -> bool | None:
    """Return request SSL behavior for AI Hub HTTP calls."""
    parsed = urlparse(api_url)
    if parsed.scheme == "http":
        return False
    return None


def resolve_provider_name(api_url: str, configured_provider: str | None = None) -> str:
    """Select provider implementation from URL or explicit config."""
    if configured_provider in _KNOWN_PROVIDER_NAMES:
        return configured_provider

    parsed = urlparse(api_url)
    if parsed.path.lower().endswith("/api/chat") or parsed.netloc.startswith("localhost:11434"):
        return "ollama_compatible"
    if "anthropic" in parsed.path.lower() or parsed.netloc == "api.anthropic.com":
        return "anthropic_compatible"
    return "openai_compatible"
