"""Constants for the AI Hub integration.

This module contains all constants organized by category:
- Domain and API URLs
- Timeouts and Retry Configuration
- Cache and Audio Limits
- Configuration Keys
- Model Lists
- Default Values and Recommended Options
- Services
"""

from __future__ import annotations

import logging
from typing import Any, Final

from homeassistant.core import HomeAssistant

# Import llm for API constants
try:
    from homeassistant.helpers import llm
    LLM_API_ASSIST = llm.LLM_API_ASSIST
    DEFAULT_INSTRUCTIONS_PROMPT = llm.DEFAULT_INSTRUCTIONS_PROMPT
except ImportError:
    LLM_API_ASSIST = "assist"
    DEFAULT_INSTRUCTIONS_PROMPT = "You are a helpful AI assistant."

_LOGGER = logging.getLogger(__name__)
LOGGER = _LOGGER  # Backwards compatibility


def get_localized_name(hass: HomeAssistant, zh_name: str, en_name: str) -> str:
    """Return localized name based on Home Assistant language setting."""
    language = hass.config.language
    chinese_languages = ["zh", "zh-cn", "zh-hans", "zh-hant", "zh-tw", "zh-hk"]
    if language and language.lower() in chinese_languages:
        return zh_name
    return en_name


# =============================================================================
# Domain and API URLs
# =============================================================================

DOMAIN: Final = "ai_hub"

# API Endpoints
API_URLS: Final = {
    "chat": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
    "image": "https://open.bigmodel.cn/api/paas/v4/images/generations",
    "siliconflow_base": "https://api.siliconflow.cn/v1",
    "siliconflow_asr": "https://api.siliconflow.cn/v1/audio/transcriptions",
    "bemfa_wechat": "https://apis.bemfa.com/vb/wechat/v1/wechatAlertJson",
}

# Keep legacy constants for backwards compatibility
AI_HUB_CHAT_URL: Final = API_URLS["chat"]
AI_HUB_IMAGE_GEN_URL: Final = API_URLS["image"]
SILICONFLOW_API_BASE: Final = API_URLS["siliconflow_base"]
SILICONFLOW_ASR_URL: Final = API_URLS["siliconflow_asr"]
BEMFA_API_URL: Final = API_URLS["bemfa_wechat"]


# =============================================================================
# Timeouts Configuration (in seconds)
# =============================================================================

TIMEOUTS: Final = {
    "default": 30.0,
    "chat_api": 60.0,
    "image_api": 120.0,
    "stt_api": 30.0,
    "tts_api": 30.0,
    "wechat_api": 15.0,
    "translation_api": 60.0,
    "media_download": 30.0,
    "health_check": 10.0,
}

# Legacy timeout constants for backwards compatibility
DEFAULT_REQUEST_TIMEOUT: Final = 30000  # milliseconds
TIMEOUT_DEFAULT: Final = TIMEOUTS["default"]
TIMEOUT_CHAT_API: Final = TIMEOUTS["chat_api"]
TIMEOUT_IMAGE_API: Final = TIMEOUTS["image_api"]
TIMEOUT_STT_API: Final = TIMEOUTS["stt_api"]
TIMEOUT_TTS_API: Final = TIMEOUTS["tts_api"]
TIMEOUT_WECHAT_API: Final = TIMEOUTS["wechat_api"]
TIMEOUT_TRANSLATION_API: Final = TIMEOUTS["translation_api"]
TIMEOUT_MEDIA_DOWNLOAD: Final = TIMEOUTS["media_download"]
TIMEOUT_HEALTH_CHECK: Final = TIMEOUTS["health_check"]


# =============================================================================
# Retry Configuration
# =============================================================================

RETRY_CONFIG: Final = {
    "max_attempts": 3,
    "base_delay": 1.0,
    "max_delay": 30.0,
    "exponential_base": 2.0,
}

# Legacy retry constants
RETRY_MAX_ATTEMPTS: Final = RETRY_CONFIG["max_attempts"]
RETRY_BASE_DELAY: Final = RETRY_CONFIG["base_delay"]
RETRY_MAX_DELAY: Final = RETRY_CONFIG["max_delay"]
RETRY_EXPONENTIAL_BASE: Final = RETRY_CONFIG["exponential_base"]


# =============================================================================
# Cache Configuration
# =============================================================================

CACHE_CONFIG: Final = {
    "tts_max_size": 100,
    "tts_ttl": 3600,  # 1 hour
}

TTS_CACHE_MAX_SIZE: Final = CACHE_CONFIG["tts_max_size"]
TTS_CACHE_TTL: Final = CACHE_CONFIG["tts_ttl"]


# =============================================================================
# Audio Size Limits
# =============================================================================

AUDIO_LIMITS: Final = {
    "stt_min_size": 1000,  # 1KB
    "stt_max_size": 10 * 1024 * 1024,  # 10MB
    "stt_warning_size": 500 * 1024,  # 500KB
    "stt_max_file_size_mb": 25,
}

STT_MIN_AUDIO_SIZE: Final = AUDIO_LIMITS["stt_min_size"]
STT_MAX_AUDIO_SIZE: Final = AUDIO_LIMITS["stt_max_size"]
STT_WARNING_AUDIO_SIZE: Final = AUDIO_LIMITS["stt_warning_size"]
STT_MAX_FILE_SIZE_MB: Final = AUDIO_LIMITS["stt_max_file_size_mb"]


# =============================================================================
# Configuration Keys
# =============================================================================

# API Keys
CONF_API_KEY: Final = "api_key"
CONF_CUSTOM_API_KEY: Final = "custom_api_key"
CONF_SILICONFLOW_API_KEY: Final = "siliconflow_api_key"

# Model Configuration
CONF_CHAT_MODEL: Final = "chat_model"
CONF_CHAT_URL: Final = "chat_url"
CONF_IMAGE_MODEL: Final = "image_model"
CONF_IMAGE_URL: Final = "image_url"
CONF_STT_MODEL: Final = "model"
CONF_STT_FILE: Final = "file"

# LLM Parameters
CONF_MAX_TOKENS: Final = "max_tokens"
CONF_PROMPT: Final = "prompt"
CONF_TEMPERATURE: Final = "temperature"
CONF_TOP_P: Final = "top_p"
CONF_TOP_K: Final = "top_k"
CONF_LLM_HASS_API: Final = "llm_hass_api"
CONF_RECOMMENDED: Final = "recommended"
CONF_MAX_HISTORY_MESSAGES: Final = "max_history_messages"

# TTS Configuration
CONF_TTS_VOICE: Final = "voice"
CONF_TTS_LANG: Final = "lang"

# WeChat and Translation
CONF_BEMFA_UID: Final = "bemfa_uid"
CONF_CUSTOM_COMPONENTS_PATH: Final = "custom_components_path"
CONF_FORCE_TRANSLATION: Final = "force_translation"
CONF_TARGET_COMPONENT: Final = "target_component"
CONF_LIST_COMPONENTS: Final = "list_components"
CONF_TARGET_BLUEPRINT: Final = "target_blueprint"
CONF_LIST_BLUEPRINTS: Final = "list_blueprints"


# =============================================================================
# Recommended Values
# =============================================================================

RECOMMENDED: Final[dict[str, Any]] = {
    # Conversation
    "chat_model": "glm-4-flash",
    "temperature": 0.3,
    "top_p": 0.5,
    "top_k": 1,
    "max_tokens": 250,
    "max_history_messages": 30,
    # AI Task
    "ai_task_model": "glm-4-flash",
    "ai_task_temperature": 0.95,
    "ai_task_top_p": 0.7,
    "ai_task_max_tokens": 2000,
    # Image
    "image_model": "cogview-3-flash",
    "image_analysis_model": "glm-4v-flash",
    # TTS
    "tts_voice": "zh-CN-XiaoxiaoNeural",
    # STT
    "stt_model": "FunAudioLLM/SenseVoiceSmall",
}

# Legacy recommended constants for backwards compatibility
RECOMMENDED_CHAT_MODEL: Final = RECOMMENDED["chat_model"]
RECOMMENDED_TEMPERATURE: Final = RECOMMENDED["temperature"]
RECOMMENDED_TOP_P: Final = RECOMMENDED["top_p"]
RECOMMENDED_TOP_K: Final = RECOMMENDED["top_k"]
RECOMMENDED_MAX_TOKENS: Final = RECOMMENDED["max_tokens"]
RECOMMENDED_MAX_HISTORY_MESSAGES: Final = RECOMMENDED["max_history_messages"]
RECOMMENDED_AI_TASK_MODEL: Final = RECOMMENDED["ai_task_model"]
RECOMMENDED_AI_TASK_TEMPERATURE: Final = RECOMMENDED["ai_task_temperature"]
RECOMMENDED_AI_TASK_TOP_P: Final = RECOMMENDED["ai_task_top_p"]
RECOMMENDED_AI_TASK_MAX_TOKENS: Final = RECOMMENDED["ai_task_max_tokens"]
RECOMMENDED_IMAGE_MODEL: Final = RECOMMENDED["image_model"]
RECOMMENDED_IMAGE_ANALYSIS_MODEL: Final = RECOMMENDED["image_analysis_model"]
RECOMMENDED_TTS_MODEL: Final = RECOMMENDED["tts_voice"]
RECOMMENDED_STT_MODEL: Final = RECOMMENDED["stt_model"]


# =============================================================================
# Default Names
# =============================================================================

DEFAULT_NAMES: Final = {
    "title": "AI Hub",
    "conversation": {"zh": "AI Hub对话助手", "en": "AI Hub Assistant"},
    "ai_task": {"zh": "AI Hub AI任务", "en": "AI Hub Task"},
    "tts": {"zh": "AI Hub TTS语音", "en": "AI Hub TTS"},
    "stt": {"zh": "AI Hub STT语音", "en": "AI Hub STT"},
    "wechat": {"zh": "AI Hub 微信通知", "en": "AI Hub WeChat"},
    "translation": {"zh": "AI Hub 汉化", "en": "AI Hub Localization"},
}

# Legacy default name constants
DEFAULT_TITLE: Final = DEFAULT_NAMES["title"]
DEFAULT_CONVERSATION_NAME: Final = DEFAULT_NAMES["conversation"]["zh"]
DEFAULT_CONVERSATION_NAME_EN: Final = DEFAULT_NAMES["conversation"]["en"]
DEFAULT_AI_TASK_NAME: Final = DEFAULT_NAMES["ai_task"]["zh"]
DEFAULT_AI_TASK_NAME_EN: Final = DEFAULT_NAMES["ai_task"]["en"]
DEFAULT_TTS_NAME: Final = DEFAULT_NAMES["tts"]["zh"]
DEFAULT_TTS_NAME_EN: Final = DEFAULT_NAMES["tts"]["en"]
DEFAULT_STT_NAME: Final = DEFAULT_NAMES["stt"]["zh"]
DEFAULT_STT_NAME_EN: Final = DEFAULT_NAMES["stt"]["en"]
DEFAULT_WECHAT_NAME: Final = DEFAULT_NAMES["wechat"]["zh"]
DEFAULT_WECHAT_NAME_EN: Final = DEFAULT_NAMES["wechat"]["en"]
DEFAULT_TRANSLATION_NAME: Final = DEFAULT_NAMES["translation"]["zh"]
DEFAULT_TRANSLATION_NAME_EN: Final = DEFAULT_NAMES["translation"]["en"]


# =============================================================================
# TTS Default Values
# =============================================================================

TTS_DEFAULT_VOICE: Final = "zh-CN-XiaoxiaoNeural"
TTS_DEFAULT_LANG: Final = "zh-CN"
STT_DEFAULT_MODEL: Final = "FunAudioLLM/SenseVoiceSmall"

# Default voice per language
TTS_DEFAULT_VOICES: Final = {
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "zh-TW": "zh-TW-HsiaoChenNeural",
    "zh-HK": "zh-HK-HiuMaanNeural",
    "en-US": "en-US-JennyNeural",
    "en-GB": "en-GB-LibbyNeural",
    "en-AU": "en-AU-NatashaNeural",
    "ja-JP": "ja-JP-NanamiNeural",
    "ko-KR": "ko-KR-SunHiNeural",
    "fr-FR": "fr-FR-DeniseNeural",
    "de-DE": "de-DE-KatjaNeural",
    "es-ES": "es-ES-ElviraNeural",
    "it-IT": "it-IT-ElsaNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "ru-RU": "ru-RU-SvetlanaNeural",
}


# =============================================================================
# Model Lists
# =============================================================================

# Chat models (ZhipuAI)
AI_HUB_CHAT_MODELS: Final = [
    # Free models
    "glm-4.7-flash",
    "GLM-4-Flash",
    "glm-4.5-flash",
    "GLM-4-Flash-250414",
    "GLM-Z1-Flash",
    # Cost-effective models
    "GLM-4-FlashX-250414",
    "GLM-4-Long",
    "GLM-4-Air",
    "GLM-4-Air-250414",
    "GLM-4-AirX",
    "GLM-Z1-Air",
    "GLM-Z1-AirX",
    "GLM-Z1-FlashX-250414",
    # GLM-4.5 series
    "glm-4.5",
    "glm-4.5-x",
    "glm-4.5-air",
    "glm-4.5-airx",
    # Professional models
    "GLM-4-Plus",
    "GLM-4-0520",
    "GLM-4-AllTools",
    "GLM-4-Assistant",
    "GLM-4-CodeGeex-4",
    # Special models
    "CharGLM-4",
    "glm-zero-preview",
]

# Image generation models
AI_HUB_IMAGE_MODELS: Final = [
    "cogview-3-flash",  # Free
    "cogview-3-plus",
    "cogview-3",
]

# Vision models (support image analysis)
VISION_MODELS: Final = [
    "glm-4.6v-flash",  # Free (recommended)
    "glm-4v-flash",
    "glm-4v",
    "glm-4v-plus",
]

# Image sizes
IMAGE_SIZES: Final = [
    "1024x1024",
    "768x1344",
    "864x1152",
    "1344x768",
    "1152x864",
    "1440x720",
    "720x1440",
]

# SiliconFlow STT models
SILICONFLOW_STT_MODELS: Final = [
    "TeleAI/TeleSpeechASR",
    "FunAudioLLM/SenseVoiceSmall",  # Recommended
]

# SiliconFlow audio formats
SILICONFLOW_STT_AUDIO_FORMATS: Final = [
    "mp3", "wav", "flac", "m4a", "ogg", "webm",
]

# Backwards compatibility aliases
AI_HUB_STT_AUDIO_FORMATS: Final = SILICONFLOW_STT_AUDIO_FORMATS
AI_HUB_STT_MODELS: Final = SILICONFLOW_STT_MODELS


# =============================================================================
# Error Messages
# =============================================================================

ERRORS: Final = {
    "getting_response": "Error getting response",
    "invalid_api_key": "Invalid API key",
    "cannot_connect": "Cannot connect to AI Hub service",
}

ERROR_GETTING_RESPONSE: Final = ERRORS["getting_response"]
ERROR_INVALID_API_KEY: Final = ERRORS["invalid_api_key"]
ERROR_CANNOT_CONNECT: Final = ERRORS["cannot_connect"]


# =============================================================================
# Services
# =============================================================================

SERVICES: Final = {
    "generate_image": "generate_image",
    "analyze_image": "analyze_image",
    "tts_speech": "tts_speech",
    "tts_stream": "tts_stream",
    "stt_transcribe": "stt_transcribe",
    "send_wechat_message": "send_wechat_message",
    "translate_components": "translate_components",
    "translate_blueprints": "translate_blueprints",
}

# Legacy service constants
SERVICE_GENERATE_IMAGE: Final = SERVICES["generate_image"]
SERVICE_ANALYZE_IMAGE: Final = SERVICES["analyze_image"]
SERVICE_TTS_SPEECH: Final = SERVICES["tts_speech"]
SERVICE_TTS_STREAM: Final = SERVICES["tts_stream"]
SERVICE_STT_TRANSCRIBE: Final = SERVICES["stt_transcribe"]
SERVICE_SEND_WECHAT_MESSAGE: Final = SERVICES["send_wechat_message"]
SERVICE_TRANSLATE_COMPONENTS: Final = SERVICES["translate_components"]
SERVICE_TRANSLATE_BLUEPRINTS: Final = SERVICES["translate_blueprints"]


# =============================================================================
# Recommended Options (Pre-built configurations)
# =============================================================================

RECOMMENDED_CONVERSATION_OPTIONS: Final = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: LLM_API_ASSIST,
    CONF_PROMPT: DEFAULT_INSTRUCTIONS_PROMPT,
    CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
    CONF_CHAT_URL: AI_HUB_CHAT_URL,
    CONF_TEMPERATURE: RECOMMENDED_TEMPERATURE,
    CONF_TOP_P: RECOMMENDED_TOP_P,
    CONF_TOP_K: RECOMMENDED_TOP_K,
    CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
    CONF_MAX_HISTORY_MESSAGES: RECOMMENDED_MAX_HISTORY_MESSAGES,
}

RECOMMENDED_AI_TASK_OPTIONS: Final = {
    CONF_RECOMMENDED: True,
    CONF_IMAGE_MODEL: RECOMMENDED_IMAGE_MODEL,
    CONF_IMAGE_URL: AI_HUB_IMAGE_GEN_URL,
    CONF_TEMPERATURE: RECOMMENDED_AI_TASK_TEMPERATURE,
    CONF_TOP_P: RECOMMENDED_AI_TASK_TOP_P,
    CONF_MAX_TOKENS: RECOMMENDED_AI_TASK_MAX_TOKENS,
}

RECOMMENDED_TTS_OPTIONS: Final = {
    CONF_RECOMMENDED: True,
    CONF_TTS_VOICE: TTS_DEFAULT_VOICE,
    CONF_TTS_LANG: TTS_DEFAULT_LANG,
}

RECOMMENDED_STT_OPTIONS: Final = {
    CONF_RECOMMENDED: True,
    CONF_STT_MODEL: STT_DEFAULT_MODEL,
}

RECOMMENDED_WECHAT_OPTIONS: Final = {
    CONF_RECOMMENDED: True,
    CONF_BEMFA_UID: "",
}

RECOMMENDED_TRANSLATION_OPTIONS: Final = {
    CONF_RECOMMENDED: True,
    CONF_FORCE_TRANSLATION: False,
    CONF_TARGET_COMPONENT: "",
    CONF_LIST_COMPONENTS: False,
    CONF_TARGET_BLUEPRINT: "",
    CONF_LIST_BLUEPRINTS: False,
}


# =============================================================================
# Edge TTS Voices (moved to separate file for cleanliness)
# =============================================================================

# Import from separate file to keep this file manageable
from .voices import EDGE_TTS_VOICES  # noqa: E402, F401
