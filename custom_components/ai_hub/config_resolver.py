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


def get_effective_api_key(entry: Any, subentry_type: str | None = None) -> str | None:
    """Return the effective API key for a subentry, falling back to the entry key."""
    if subentry_type:
        for subentry in entry.subentries.values():
            if subentry.subentry_type == subentry_type:
                custom_api_key = subentry.data.get(CONF_CUSTOM_API_KEY, "").strip()
                if custom_api_key:
                    return custom_api_key
                break
    return entry.runtime_data


def get_effective_conversation_config(entry: Any) -> tuple[str, str, str | None]:
    """Return effective conversation endpoint, model, and API key."""
    chat_url = AI_HUB_CHAT_URL
    model = RECOMMENDED_CHAT_MODEL
    for subentry in entry.subentries.values():
        if subentry.subentry_type == "conversation":
            chat_url = subentry.data.get(CONF_CHAT_URL, chat_url)
            model = subentry.data.get(CONF_CHAT_MODEL, model)
            break
    return chat_url, model, get_effective_api_key(entry, "conversation")


def get_effective_image_config(entry: Any) -> tuple[str, str | None]:
    """Return effective image endpoint and API key."""
    image_url = AI_HUB_IMAGE_GEN_URL
    for subentry in entry.subentries.values():
        if subentry.subentry_type == "ai_task_data":
            image_url = subentry.data.get(CONF_IMAGE_URL, image_url)
            break
    return image_url, get_effective_api_key(entry, "ai_task_data")


def get_effective_stt_config(entry: Any) -> tuple[str, str | None]:
    """Return effective STT endpoint and API key."""
    stt_url = SILICONFLOW_ASR_URL
    for subentry in entry.subentries.values():
        if subentry.subentry_type == "stt":
            stt_url = subentry.data.get(CONF_STT_URL, stt_url)
            break
    return stt_url, get_effective_api_key(entry, "stt")


def get_effective_translation_config(entry: Any) -> tuple[str, str, str | None]:
    """Return effective translation endpoint, model, and API key."""
    chat_url = AI_HUB_CHAT_URL
    model = RECOMMENDED_CHAT_MODEL
    for subentry in entry.subentries.values():
        if subentry.subentry_type == "translation":
            chat_url = subentry.data.get(CONF_CHAT_URL, chat_url)
            model = subentry.data.get(CONF_CHAT_MODEL, model)
            break
    return chat_url, model, get_effective_api_key(entry, "translation")
