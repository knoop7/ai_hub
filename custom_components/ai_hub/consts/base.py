"""Base constants and helpers for AI Hub."""

from __future__ import annotations

import logging
from typing import Any, Final

try:
    from homeassistant.core import HomeAssistant
except ModuleNotFoundError:  # pragma: no cover
    HomeAssistant = Any  # type: ignore[assignment]

try:
    from homeassistant.helpers import llm

    LLM_API_ASSIST = llm.LLM_API_ASSIST
    DEFAULT_INSTRUCTIONS_PROMPT = llm.DEFAULT_INSTRUCTIONS_PROMPT
except ImportError:  # pragma: no cover
    LLM_API_ASSIST = "assist"
    DEFAULT_INSTRUCTIONS_PROMPT = "You are a helpful AI assistant."

_LOGGER = logging.getLogger(__name__)
LOGGER = _LOGGER

DOMAIN: Final = "ai_hub"


def get_localized_name(hass: HomeAssistant, zh_name: str, en_name: str) -> str:
    """Return localized name based on Home Assistant language setting."""
    language = hass.config.language
    chinese_languages = ["zh", "zh-cn", "zh-hans", "zh-hant", "zh-tw", "zh-hk"]
    if language and language.lower() in chinese_languages:
        return zh_name
    return en_name
