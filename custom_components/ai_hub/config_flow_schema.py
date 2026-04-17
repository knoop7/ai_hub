"""Schema builders for AI Hub config and subentry flows."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.const import CONF_NAME
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    AI_HUB_CHAT_MODELS,
    AI_HUB_CHAT_URL,
    AI_HUB_IMAGE_GEN_URL,
    AI_HUB_IMAGE_MODELS,
    CONF_CHAT_MODEL,
    CONF_CHAT_URL,
    CONF_CUSTOM_API_KEY,
    CONF_FORCE_TRANSLATION,
    CONF_IMAGE_MODEL,
    CONF_IMAGE_URL,
    CONF_LIST_COMPONENTS,
    CONF_LLM_HASS_API,
    CONF_LLM_PROVIDER,
    CONF_MAX_HISTORY_MESSAGES,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_STT_MODEL,
    CONF_STT_URL,
    CONF_TARGET_COMPONENT,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TTS_LANG,
    CONF_TTS_VOICE,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_STT_NAME,
    DEFAULT_TRANSLATION_NAME,
    DEFAULT_TTS_NAME,
    EDGE_TTS_VOICES,
    RECOMMENDED_AI_TASK_MAX_TOKENS,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_AI_TASK_TEMPERATURE,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_IMAGE_MODEL,
    RECOMMENDED_LLM_PROVIDER,
    RECOMMENDED_MAX_HISTORY_MESSAGES,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_STT_MODEL,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TRANSLATION_OPTIONS,
    RECOMMENDED_TTS_OPTIONS,
    SILICONFLOW_ASR_URL,
    SILICONFLOW_STT_MODELS,
    TTS_DEFAULT_LANG,
    TTS_DEFAULT_VOICE,
)

SUBENTRY_TYPES = {
    "conversation": "conversation",
    "ai_task_data": "ai_task_data",
    "tts": "tts",
    "stt": "stt",
    "translation": "translation",
}


def get_default_subentry_options(subentry_type: str) -> dict[str, Any]:
    """Return default options for a new subentry."""
    if subentry_type == SUBENTRY_TYPES["ai_task_data"]:
        return RECOMMENDED_AI_TASK_OPTIONS.copy()
    if subentry_type == SUBENTRY_TYPES["tts"]:
        return RECOMMENDED_TTS_OPTIONS.copy()
    if subentry_type == SUBENTRY_TYPES["stt"]:
        return RECOMMENDED_STT_OPTIONS.copy()
    if subentry_type == SUBENTRY_TYPES["translation"]:
        return RECOMMENDED_TRANSLATION_OPTIONS.copy()
    return RECOMMENDED_CONVERSATION_OPTIONS.copy()


def get_default_subentry_name(subentry_type: str, options: Mapping[str, Any]) -> str:
    """Return the default name shown for a new subentry."""
    if CONF_NAME in options:
        return str(options[CONF_NAME])
    if subentry_type == SUBENTRY_TYPES["ai_task_data"]:
        return DEFAULT_AI_TASK_NAME
    if subentry_type == SUBENTRY_TYPES["tts"]:
        return DEFAULT_TTS_NAME
    if subentry_type == SUBENTRY_TYPES["stt"]:
        return DEFAULT_STT_NAME
    if subentry_type == SUBENTRY_TYPES["translation"]:
        return DEFAULT_TRANSLATION_NAME
    return DEFAULT_CONVERSATION_NAME


async def ai_hub_config_option_schema(
    is_new: bool,
    subentry_type: str,
    options: Mapping[str, Any],
) -> dict:
    """Return a schema for AI Hub completion options."""
    schema: dict[Any, Any] = {}

    if is_new:
        schema[vol.Required(CONF_NAME, default=get_default_subentry_name(subentry_type, options))] = str

    schema[vol.Required(CONF_RECOMMENDED, default=options.get(CONF_RECOMMENDED, True))] = bool

    if options.get(CONF_RECOMMENDED):
        if subentry_type == SUBENTRY_TYPES["conversation"]:
            schema.update(_build_conversation_schema(options, recommended_only=True))
            options[CONF_LLM_HASS_API] = llm.LLM_API_ASSIST
        elif subentry_type == SUBENTRY_TYPES["ai_task_data"]:
            schema.update(_build_ai_task_schema(options, recommended_only=True))
        elif subentry_type == SUBENTRY_TYPES["stt"]:
            schema.update(_build_stt_schema(options))
        elif subentry_type == SUBENTRY_TYPES["translation"]:
            schema.update(_build_translation_schema(options))
        return schema

    if subentry_type == SUBENTRY_TYPES["conversation"]:
        options[CONF_LLM_HASS_API] = llm.LLM_API_ASSIST
        schema.update(_build_conversation_schema(options, recommended_only=False))
    elif subentry_type == SUBENTRY_TYPES["ai_task_data"]:
        schema.update(_build_ai_task_schema(options, recommended_only=False))
    elif subentry_type == SUBENTRY_TYPES["tts"]:
        schema.update(_build_tts_schema(options))
    elif subentry_type == SUBENTRY_TYPES["stt"]:
        schema.update(_build_stt_schema(options))
    elif subentry_type == SUBENTRY_TYPES["translation"]:
        schema.update(_build_translation_schema(options))

    return schema


def _build_conversation_schema(options: Mapping[str, Any], recommended_only: bool) -> dict[Any, Any]:
    schema = {
        vol.Optional(
            CONF_PROMPT,
            default=options.get(CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT),
            description={"suggested_value": options.get(CONF_PROMPT)},
        ): TemplateSelector(),
        vol.Optional(
            CONF_LLM_PROVIDER,
            default=options.get(CONF_LLM_PROVIDER, RECOMMENDED_LLM_PROVIDER),
            description={"suggested_value": options.get(CONF_LLM_PROVIDER)},
        ): SelectSelector(
            SelectSelectorConfig(
                options=["openai_compatible", "anthropic_compatible"],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(
            CONF_CHAT_MODEL,
            default=options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL),
            description={"suggested_value": options.get(CONF_CHAT_MODEL)},
        ): SelectSelector(
            SelectSelectorConfig(
                options=AI_HUB_CHAT_MODELS,
                mode=SelectSelectorMode.DROPDOWN,
                custom_value=True,
            )
        ),
        vol.Optional(
            CONF_CHAT_URL,
            default=options.get(CONF_CHAT_URL, AI_HUB_CHAT_URL),
            description={"suggested_value": options.get(CONF_CHAT_URL)},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Optional(
            CONF_CUSTOM_API_KEY,
            default=options.get(CONF_CUSTOM_API_KEY, ""),
            description={"suggested_value": options.get(CONF_CUSTOM_API_KEY)},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
    if not recommended_only:
        schema.update(
            {
                vol.Optional(
                    CONF_TEMPERATURE,
                    default=options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE),
                    description={"suggested_value": options.get(CONF_TEMPERATURE)},
                ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.01, mode=NumberSelectorMode.SLIDER)),
                vol.Optional(
                    CONF_TOP_K,
                    default=options.get(CONF_TOP_K, RECOMMENDED_TOP_K),
                    description={"suggested_value": options.get(CONF_TOP_K)},
                ): int,
                vol.Optional(
                    CONF_MAX_TOKENS,
                    default=options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
                    description={"suggested_value": options.get(CONF_MAX_TOKENS)},
                ): int,
                vol.Optional(
                    CONF_MAX_HISTORY_MESSAGES,
                    default=options.get(CONF_MAX_HISTORY_MESSAGES, RECOMMENDED_MAX_HISTORY_MESSAGES),
                    description={"suggested_value": options.get(CONF_MAX_HISTORY_MESSAGES)},
                ): int,
            }
        )
    return schema


def _build_ai_task_schema(options: Mapping[str, Any], recommended_only: bool) -> dict[Any, Any]:
    schema = {
        vol.Optional(
            CONF_IMAGE_MODEL,
            default=options.get(CONF_IMAGE_MODEL, RECOMMENDED_IMAGE_MODEL),
            description={"suggested_value": options.get(CONF_IMAGE_MODEL)},
        ): SelectSelector(
            SelectSelectorConfig(
                options=AI_HUB_IMAGE_MODELS,
                mode=SelectSelectorMode.DROPDOWN,
                custom_value=True,
            )
        ),
        vol.Optional(
            CONF_IMAGE_URL,
            default=options.get(CONF_IMAGE_URL, AI_HUB_IMAGE_GEN_URL),
            description={"suggested_value": options.get(CONF_IMAGE_URL)},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Optional(
            CONF_CUSTOM_API_KEY,
            default=options.get(CONF_CUSTOM_API_KEY, ""),
            description={"suggested_value": options.get(CONF_CUSTOM_API_KEY)},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
    if not recommended_only:
        schema.update(
            {
                vol.Optional(
                    CONF_TEMPERATURE,
                    default=options.get(CONF_TEMPERATURE, RECOMMENDED_AI_TASK_TEMPERATURE),
                    description={"suggested_value": options.get(CONF_TEMPERATURE)},
                ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.01, mode=NumberSelectorMode.SLIDER)),
                vol.Optional(
                    CONF_MAX_TOKENS,
                    default=options.get(CONF_MAX_TOKENS, RECOMMENDED_AI_TASK_MAX_TOKENS),
                    description={"suggested_value": options.get(CONF_MAX_TOKENS)},
                ): int,
            }
        )
    return schema


def _build_tts_schema(options: Mapping[str, Any]) -> dict[Any, Any]:
    unique_languages = sorted(list(set(EDGE_TTS_VOICES.values())))
    return {
        vol.Optional(
            CONF_TTS_LANG,
            default=options.get(CONF_TTS_LANG, TTS_DEFAULT_LANG),
            description={"suggested_value": options.get(CONF_TTS_LANG)},
        ): SelectSelector(SelectSelectorConfig(options=unique_languages, mode=SelectSelectorMode.DROPDOWN)),
        vol.Optional(
            CONF_TTS_VOICE,
            default=options.get(CONF_TTS_VOICE, TTS_DEFAULT_VOICE),
            description={"suggested_value": options.get(CONF_TTS_VOICE)},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
    }


def _build_stt_schema(options: Mapping[str, Any]) -> dict[Any, Any]:
    return {
        vol.Optional(
            CONF_STT_MODEL,
            default=options.get(CONF_STT_MODEL, RECOMMENDED_STT_MODEL),
            description={"suggested_value": options.get(CONF_STT_MODEL)},
        ): SelectSelector(SelectSelectorConfig(options=SILICONFLOW_STT_MODELS, mode=SelectSelectorMode.DROPDOWN)),
        vol.Optional(
            CONF_STT_URL,
            default=options.get(CONF_STT_URL, SILICONFLOW_ASR_URL),
            description={"suggested_value": options.get(CONF_STT_URL)},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Optional(
            CONF_CUSTOM_API_KEY,
            default=options.get(CONF_CUSTOM_API_KEY, ""),
            description={"suggested_value": options.get(CONF_CUSTOM_API_KEY)},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }


def _build_translation_schema(options: Mapping[str, Any]) -> dict[Any, Any]:
    return {
        vol.Optional(
            CONF_CHAT_MODEL,
            default=options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL),
            description={"suggested_value": options.get(CONF_CHAT_MODEL)},
        ): SelectSelector(
            SelectSelectorConfig(options=AI_HUB_CHAT_MODELS, mode=SelectSelectorMode.DROPDOWN, custom_value=True)
        ),
        vol.Optional(
            CONF_CHAT_URL,
            default=options.get(CONF_CHAT_URL, AI_HUB_CHAT_URL),
            description={"suggested_value": options.get(CONF_CHAT_URL)},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Optional(
            CONF_CUSTOM_API_KEY,
            default=options.get(CONF_CUSTOM_API_KEY, ""),
            description={"suggested_value": options.get(CONF_CUSTOM_API_KEY)},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        vol.Optional(
            CONF_LIST_COMPONENTS,
            default=options.get(CONF_LIST_COMPONENTS, False),
            description={"suggested_value": options.get(CONF_LIST_COMPONENTS)},
        ): bool,
        vol.Optional(
            CONF_FORCE_TRANSLATION,
            default=options.get(CONF_FORCE_TRANSLATION, False),
            description={"suggested_value": options.get(CONF_FORCE_TRANSLATION)},
        ): bool,
        vol.Optional(
            CONF_TARGET_COMPONENT,
            default=options.get(CONF_TARGET_COMPONENT, ""),
            description={"suggested_value": options.get(CONF_TARGET_COMPONENT)},
        ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
    }
