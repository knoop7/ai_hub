"""Shared helpers for image generation responses."""

from __future__ import annotations

import base64
from typing import Any

from homeassistant.exceptions import HomeAssistantError


def extract_generated_image_payload(result: dict[str, Any]) -> dict[str, str]:
    """Extract the first generated image payload from an API response."""
    data = result.get("data")
    if not isinstance(data, list) or not data:
        raise HomeAssistantError("No image data in response")

    image_data = data[0]
    if not isinstance(image_data, dict):
        raise HomeAssistantError("Invalid image data in response")

    image_url = image_data.get("url")
    if isinstance(image_url, str) and image_url:
        return {"url": image_url}

    b64_json = image_data.get("b64_json")
    if isinstance(b64_json, str) and b64_json:
        return {"image_base64": b64_json}

    raise HomeAssistantError("No image URL or base64 data in response")


def decode_base64_image(image_base64: str) -> bytes:
    """Decode base64-encoded generated image data."""
    return base64.b64decode(image_base64)
