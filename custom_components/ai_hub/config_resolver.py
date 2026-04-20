"""Helpers to resolve effective config for an entry and subentries."""

from __future__ import annotations

from typing import Any

from .consts import (
    AI_HUB_CHAT_URL,
    AI_HUB_IMAGE_GEN_URL,
    CONF_CHAT_MODEL,
    CONF_CHAT_URL,
    CONF_CUSTOM_API_KEY,
    CONF_IMAGE_URL,
    CONF_STT_URL,
    RECOMMENDED_CHAT_MODEL,
    SILICONFLOW_ASR_URL,
)


def _get_subentry_by_type(entry: Any, subentry_type: str) -> Any | None:
    """Return the first subentry matching the requested type."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type == subentry_type:
            return subentry
    return None


def get_effective_api_key(entry: Any, subentry_type: str | None = None) -> str | None:
    """Return the effective API key for a subentry, falling back to the entry key."""
    if subentry_type:
        subentry = _get_subentry_by_type(entry, subentry_type)
        if subentry is not None:
            custom_api_key = subentry.data.get(CONF_CUSTOM_API_KEY, "").strip()
            if custom_api_key:
                return custom_api_key
    return entry.runtime_data


def _get_subentry_value(entry: Any, subentry_type: str, key: str, default: Any) -> Any:
    """Return a value from the first matching subentry, or the default."""
    subentry = _get_subentry_by_type(entry, subentry_type)
    if subentry is None:
        return default
    return subentry.data.get(key, default)


def get_effective_conversation_config(entry: Any) -> tuple[str, str, str | None]:
    """Return effective conversation endpoint, model, and API key."""
    chat_url = _get_subentry_value(entry, "conversation", CONF_CHAT_URL, AI_HUB_CHAT_URL)
    model = _get_subentry_value(entry, "conversation", CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
    return chat_url, model, get_effective_api_key(entry, "conversation")


def get_effective_image_config(entry: Any) -> tuple[str, str | None]:
    """Return effective image endpoint and API key."""
    image_url = _get_subentry_value(entry, "ai_task_data", CONF_IMAGE_URL, AI_HUB_IMAGE_GEN_URL)
    return image_url, get_effective_api_key(entry, "ai_task_data")


def get_effective_stt_config(entry: Any) -> tuple[str, str | None]:
    """Return effective STT endpoint and API key."""
    stt_url = _get_subentry_value(entry, "stt", CONF_STT_URL, SILICONFLOW_ASR_URL)
    return stt_url, get_effective_api_key(entry, "stt")


def get_effective_translation_config(entry: Any) -> tuple[str, str, str | None]:
    """Return effective translation endpoint, model, and API key."""
    chat_url = _get_subentry_value(entry, "translation", CONF_CHAT_URL, AI_HUB_CHAT_URL)
    model = _get_subentry_value(entry, "translation", CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
    return chat_url, model, get_effective_api_key(entry, "translation")
