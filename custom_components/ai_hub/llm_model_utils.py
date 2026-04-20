"""Shared helpers for attachment-aware LLM model handling."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any


def chat_log_has_media_attachments(chat_log: Any) -> bool:
    """Return whether a chat log contains image or video attachments."""
    for content in getattr(chat_log, "content", []):
        attachments = getattr(content, "attachments", None)
        if not attachments:
            continue

        for attachment in attachments:
            mime_type = getattr(attachment, "mime_type", "")
            if isinstance(mime_type, str) and mime_type.startswith(("image/", "video/")):
                return True

    return False


def select_media_model(
    configured_model: str,
    supported_media_models: Iterable[str],
    fallback_model: str,
) -> str:
    """Return the model to use for media attachments."""
    return configured_model if configured_model in supported_media_models else fallback_model


def parse_structured_json_response(text: str) -> Any:
    """Extract and parse structured JSON returned by the model."""
    cleaned_text = text.strip()

    if cleaned_text.startswith("json"):
        cleaned_text = cleaned_text[4:].strip()
    elif cleaned_text.startswith("JSON"):
        cleaned_text = cleaned_text[4:].strip()

    if cleaned_text.startswith("```"):
        lines = cleaned_text.split("\n")
        if len(lines) > 1:
            cleaned_text = "\n".join(lines[1:-1]).strip()

    return json.loads(cleaned_text)
