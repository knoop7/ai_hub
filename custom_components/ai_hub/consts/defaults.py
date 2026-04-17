"""Default and recommended values for AI Hub."""

from __future__ import annotations

from typing import Any, Final

from .api import AI_HUB_CHAT_URL, AI_HUB_IMAGE_GEN_URL, SILICONFLOW_ASR_URL
from .base import DEFAULT_INSTRUCTIONS_PROMPT, LLM_API_ASSIST
from .config import (
    CONF_CHAT_MODEL,
    CONF_CHAT_URL,
    CONF_FORCE_TRANSLATION,
    CONF_IMAGE_MODEL,
    CONF_IMAGE_URL,
    CONF_LIST_BLUEPRINTS,
    CONF_LIST_COMPONENTS,
    CONF_LLM_HASS_API,
    CONF_LLM_PROVIDER,
    CONF_MAX_HISTORY_MESSAGES,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_STT_MODEL,
    CONF_STT_URL,
    CONF_TARGET_BLUEPRINT,
    CONF_TARGET_COMPONENT,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    CONF_TTS_LANG,
    CONF_TTS_VOICE,
)

RECOMMENDED: Final[dict[str, Any]] = {
    "chat_model": "Qwen/Qwen3-8B",
    "temperature": 0.3,
    "top_p": 0.5,
    "top_k": 1,
    "max_tokens": 250,
    "max_history_messages": 30,
    "ai_task_model": "Qwen/Qwen3-8B",
    "ai_task_temperature": 0.95,
    "ai_task_top_p": 0.7,
    "ai_task_max_tokens": 2000,
    "image_model": "Kwai-Kolors/Kolors",
    "image_analysis_model": "THUDM/GLM-4.1V-9B-Thinking",
    "tts_voice": "zh-CN-XiaoxiaoNeural",
    "stt_model": "FunAudioLLM/SenseVoiceSmall",
}

RECOMMENDED_CHAT_MODEL: Final = RECOMMENDED["chat_model"]
RECOMMENDED_LLM_PROVIDER: Final = "openai_compatible"
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

DEFAULT_NAMES: Final = {
    "title": "AI Hub",
    "conversation": {"zh": "AI Hub对话助手", "en": "AI Hub Assistant"},
    "ai_task": {"zh": "AI Hub AI任务", "en": "AI Hub Task"},
    "tts": {"zh": "AI Hub TTS语音", "en": "AI Hub TTS"},
    "stt": {"zh": "AI Hub STT语音", "en": "AI Hub STT"},
    "translation": {"zh": "AI Hub 汉化", "en": "AI Hub Localization"},
}

DEFAULT_TITLE: Final = DEFAULT_NAMES["title"]
DEFAULT_CONVERSATION_NAME: Final = DEFAULT_NAMES["conversation"]["zh"]
DEFAULT_AI_TASK_NAME: Final = DEFAULT_NAMES["ai_task"]["zh"]
DEFAULT_TTS_NAME: Final = DEFAULT_NAMES["tts"]["zh"]
DEFAULT_STT_NAME: Final = DEFAULT_NAMES["stt"]["zh"]
DEFAULT_TRANSLATION_NAME: Final = DEFAULT_NAMES["translation"]["zh"]

TTS_DEFAULT_VOICE: Final = "zh-CN-XiaoxiaoNeural"
TTS_DEFAULT_LANG: Final = "zh-CN"
STT_DEFAULT_MODEL: Final = "FunAudioLLM/SenseVoiceSmall"

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

RECOMMENDED_CONVERSATION_OPTIONS: Final = {
    CONF_RECOMMENDED: True,
    CONF_LLM_HASS_API: LLM_API_ASSIST,
    CONF_PROMPT: DEFAULT_INSTRUCTIONS_PROMPT,
    CONF_LLM_PROVIDER: RECOMMENDED_LLM_PROVIDER,
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
    CONF_STT_URL: SILICONFLOW_ASR_URL,
}

RECOMMENDED_TRANSLATION_OPTIONS: Final = {
    CONF_RECOMMENDED: True,
    CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
    CONF_CHAT_URL: AI_HUB_CHAT_URL,
    CONF_FORCE_TRANSLATION: False,
    CONF_TARGET_COMPONENT: "",
    CONF_LIST_COMPONENTS: False,
    CONF_TARGET_BLUEPRINT: "",
    CONF_LIST_BLUEPRINTS: False,
}
