"""Provider routing helpers."""

from __future__ import annotations

from urllib.parse import urlparse


def get_provider_name(api_url: str, configured_provider: str | None = None) -> str:
    """Select provider implementation from URL or explicit config."""
    if configured_provider in {"openai_compatible", "anthropic_compatible"}:
        return configured_provider

    parsed = urlparse(api_url)
    if "anthropic" in parsed.path.lower() or parsed.netloc == "api.anthropic.com":
        return "anthropic_compatible"
    return "openai_compatible"
