"""Configuration keys for AI Hub."""

from __future__ import annotations

from typing import Final

CONF_API_KEY: Final = "api_key"
CONF_CUSTOM_API_KEY: Final = "custom_api_key"

CONF_CHAT_MODEL: Final = "chat_model"
CONF_CHAT_URL: Final = "chat_url"
CONF_LLM_PROVIDER: Final = "llm_provider"
CONF_IMAGE_MODEL: Final = "image_model"
CONF_IMAGE_URL: Final = "image_url"
CONF_STT_MODEL: Final = "model"
CONF_STT_URL: Final = "stt_url"
CONF_STT_FILE: Final = "file"

CONF_MAX_TOKENS: Final = "max_tokens"
CONF_PROMPT: Final = "prompt"
CONF_TEMPERATURE: Final = "temperature"
CONF_TOP_P: Final = "top_p"
CONF_TOP_K: Final = "top_k"
CONF_LLM_HASS_API: Final = "llm_hass_api"
CONF_RECOMMENDED: Final = "recommended"
CONF_MAX_HISTORY_MESSAGES: Final = "max_history_messages"
CONF_ENABLE_THINKING: Final = "enable_thinking"

CONF_TTS_VOICE: Final = "voice"
CONF_TTS_LANG: Final = "lang"

CONF_CUSTOM_COMPONENTS_PATH: Final = "custom_components_path"
CONF_FORCE_TRANSLATION: Final = "force_translation"
CONF_TARGET_COMPONENT: Final = "target_component"
CONF_LIST_COMPONENTS: Final = "list_components"
CONF_TARGET_BLUEPRINT: Final = "target_blueprint"
CONF_LIST_BLUEPRINTS: Final = "list_blueprints"
