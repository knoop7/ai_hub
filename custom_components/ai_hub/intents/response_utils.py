"""Shared response formatting helpers for local intents."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers import intent


def format_response_message(template: str, **kwargs: Any) -> str:
    """Format a response template with common safe defaults."""
    values = {
        "area": kwargs.get("area", ""),
        "device": kwargs.get("device", ""),
        "count": kwargs.get("count", 0),
        "temperature": kwargs.get("temperature", ""),
        "brightness": kwargs.get("brightness", ""),
        "color": kwargs.get("color", ""),
        "volume": kwargs.get("volume", ""),
        "position": kwargs.get("position", ""),
        "speed": kwargs.get("speed", ""),
        "query": kwargs.get("query", ""),
        "fail_msg": kwargs.get("fail_msg", ""),
        "error": kwargs.get("error", ""),
    }
    return template.format(**values)


def create_intent_result(language: str, message: str, *, is_error: bool = False) -> dict[str, Any]:
    """Create the standard local intent service result payload."""
    response = intent.IntentResponse(language=language)
    if is_error:
        response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, message)
    else:
        response.async_set_speech(message)

    return {
        "response": response,
        "success": not is_error,
        "message": message,
    }
