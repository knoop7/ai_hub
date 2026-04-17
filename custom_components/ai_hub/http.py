"""Shared HTTP helpers for AI Hub."""

from __future__ import annotations

from urllib.parse import urlparse

import aiohttp


def client_timeout(total: float) -> aiohttp.ClientTimeout:
    """Build a client timeout with a total timeout only."""
    return aiohttp.ClientTimeout(total=total)


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
    if default_url and api_url != default_url and parsed.scheme == "https":
        return False
    return None
