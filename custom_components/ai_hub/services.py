"""Services for AI Hub integration - 精简版，实际处理委托给 services_lib 模块."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall

from .config_resolver import (
    get_effective_conversation_config,
    get_effective_image_config,
    get_effective_stt_config,
    get_effective_translation_config,
)
from .const import (
    DOMAIN,
    SERVICE_ANALYZE_IMAGE,
    SERVICE_GENERATE_IMAGE,
    SERVICE_STT_TRANSCRIBE,
    SERVICE_TRANSLATE_BLUEPRINTS,
    SERVICE_TRANSLATE_COMPONENTS,
    SERVICE_TTS_SAY,
)
from .services_lib import (
    BLUEPRINTS_TRANSLATION_SCHEMA,
    # Schemas
    IMAGE_ANALYZER_SCHEMA,
    IMAGE_GENERATOR_SCHEMA,
    STT_SCHEMA,
    TRANSLATION_SCHEMA,
    TTS_SCHEMA,
    async_translate_all_blueprints,
    async_translate_all_components,
    # Handlers
    handle_analyze_image,
    handle_generate_image,
    handle_stt_transcribe,
    handle_tts_speech,
    handle_tts_stream,
)

_LOGGER = logging.getLogger(__name__)

_REGISTERED_HASS: HomeAssistant | None = None
_REGISTERED_ENTRY = None


def _get_conversation_config(config_entry) -> tuple[str, str, str]:
    """Get chat URL, model and API key from Conversation Agent subentry."""
    chat_url, model, api_key = get_effective_conversation_config(config_entry)
    return chat_url, model, api_key


def _get_image_config(config_entry) -> tuple[str, str]:
    """Get image URL and API key from AI Task subentry."""
    image_url, api_key = get_effective_image_config(config_entry)
    return image_url, api_key


def _get_stt_config(config_entry) -> tuple[str, str]:
    """Get STT URL and API key from STT subentry."""
    stt_url, api_key = get_effective_stt_config(config_entry)
    return stt_url, api_key


def _get_translation_config(config_entry) -> tuple[str, str, str]:
    """Get translation URL, model and API key from translation subentry."""
    chat_url, model, api_key = get_effective_translation_config(config_entry)
    return chat_url, model, api_key


def _get_registered_context() -> tuple[HomeAssistant | None, object | None]:
    """Return the most recently registered service context."""
    return _REGISTERED_HASS, _REGISTERED_ENTRY


async def _handle_analyze_image(call: ServiceCall) -> dict:
    """Handle analyze image service calls."""
    hass, config_entry = _get_registered_context()
    if hass is None or config_entry is None:
        return {"success": False, "error": "API密钥未配置"}

    chat_url, _, effective_key = _get_conversation_config(config_entry)
    if not effective_key or not effective_key.strip():
        return {"success": False, "error": "API密钥未配置"}
    return await handle_analyze_image(hass, call, effective_key, chat_url)


async def _handle_generate_image(call: ServiceCall) -> dict:
    """Handle generate image service calls."""
    hass, config_entry = _get_registered_context()
    if hass is None or config_entry is None:
        return {"success": False, "error": "API密钥未配置"}

    image_url, effective_key = _get_image_config(config_entry)
    if not effective_key or not effective_key.strip():
        return {"success": False, "error": "API密钥未配置"}
    return await handle_generate_image(hass, call, effective_key, image_url)


async def _handle_stt_transcribe(call: ServiceCall) -> dict:
    """Handle STT transcription service calls."""
    hass, config_entry = _get_registered_context()
    if hass is None or config_entry is None:
        return {"success": False, "error": "API密钥未配置"}

    stt_url, api_key = _get_stt_config(config_entry)
    if not api_key or not api_key.strip():
        return {"success": False, "error": "API密钥未配置"}
    return await handle_stt_transcribe(hass, call, api_key, stt_url)


async def async_setup_services(hass: HomeAssistant, config_entry) -> None:
    """Set up services for AI Hub integration."""

    global _REGISTERED_HASS, _REGISTERED_ENTRY
    _REGISTERED_HASS = hass
    _REGISTERED_ENTRY = config_entry

    api_key = config_entry.runtime_data
    def has_api_key() -> bool:
        """Check if any API key is available (main or custom)."""
        return api_key is not None and api_key.strip() != ""

    # ========== 图像分析服务 ==========
    # ========== TTS 语音合成服务（统一） ==========
    async def _handle_tts_say(call: ServiceCall) -> dict:
        """Handle TTS service with optional streaming support."""
        stream = call.data.get("stream", False)
        if stream:
            return await handle_tts_stream(hass, call)
        else:
            if not has_api_key():
                return {"success": False, "error": "API密钥未配置"}
            return await handle_tts_speech(hass, call, api_key)

    # ========== STT 语音转文字服务 ==========
    # ========== 组件翻译服务 ==========
    async def _handle_translate_components(call: ServiceCall) -> dict:
        try:
            list_components = call.data.get("list_components", False)
            target_component = call.data.get("target_component", "").strip()
            force_translation = call.data.get("force_translation", False)

            chat_url, model, effective_key = _get_translation_config(config_entry)

            if not list_components and (not effective_key or not effective_key.strip()):
                return {"success": False, "error": "API密钥未配置"}

            result = await async_translate_all_components(
                custom_components_path="custom_components",
                api_key=effective_key if not list_components else None,
                force_translation=force_translation,
                target_component=target_component,
                list_components=list_components,
                api_url=chat_url,
                model=model
            )
            return {"success": True, "result": result}
        except Exception as exc:
            _LOGGER.error("Translation service error: %s", exc)
            return {"success": False, "error": f"Translation service error: {exc}"}

    # ========== 蓝图翻译服务 ==========
    async def _handle_translate_blueprints(call: ServiceCall) -> dict:
        try:
            list_blueprints = call.data.get("list_blueprints", False)
            target_blueprint = call.data.get("target_blueprint", "").strip()
            retranslate = call.data.get("retranslate", False)
            blueprints_path = hass.config.path("blueprints")

            chat_url, model, effective_key = _get_translation_config(config_entry)

            if not list_blueprints and (not effective_key or not effective_key.strip()):
                return {"success": False, "error": "API密钥未配置"}

            result = await async_translate_all_blueprints(
                api_key=effective_key if not list_blueprints else None,
                retranslate=retranslate,
                target_blueprint=target_blueprint,
                list_blueprints=list_blueprints,
                blueprints_path=blueprints_path,
                api_url=chat_url,
                model=model
            )
            return {"success": True, "result": result}
        except Exception as exc:
            _LOGGER.error("Blueprint translation service error: %s", exc)
            return {"success": False, "error": f"Blueprint translation service error: {exc}"}

    # ========== 注册所有服务 ==========
    hass.services.async_register(
        DOMAIN, SERVICE_ANALYZE_IMAGE, _handle_analyze_image,
        schema=vol.Schema(IMAGE_ANALYZER_SCHEMA), supports_response=True
    )

    hass.services.async_register(
        DOMAIN, SERVICE_GENERATE_IMAGE, _handle_generate_image,
        schema=vol.Schema(IMAGE_GENERATOR_SCHEMA), supports_response=True
    )

    hass.services.async_register(
        DOMAIN, SERVICE_TTS_SAY, _handle_tts_say,
        schema=vol.Schema(TTS_SCHEMA), supports_response=True
    )

    hass.services.async_register(
        DOMAIN, SERVICE_STT_TRANSCRIBE, _handle_stt_transcribe,
        schema=vol.Schema(STT_SCHEMA), supports_response=True
    )

    hass.services.async_register(
        DOMAIN, SERVICE_TRANSLATE_COMPONENTS, _handle_translate_components,
        schema=vol.Schema(TRANSLATION_SCHEMA), supports_response=True
    )

    hass.services.async_register(
        DOMAIN, SERVICE_TRANSLATE_BLUEPRINTS, _handle_translate_blueprints,
        schema=vol.Schema(BLUEPRINTS_TRANSLATION_SCHEMA), supports_response=True
    )

    _LOGGER.info("AI Hub services registered successfully")


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload all services for AI Hub integration.

    Args:
        hass: Home Assistant instance
    """
    hass.services.async_remove(DOMAIN, SERVICE_ANALYZE_IMAGE)
    hass.services.async_remove(DOMAIN, SERVICE_GENERATE_IMAGE)
    hass.services.async_remove(DOMAIN, SERVICE_TTS_SAY)
    hass.services.async_remove(DOMAIN, SERVICE_STT_TRANSCRIBE)
    hass.services.async_remove(DOMAIN, SERVICE_TRANSLATE_COMPONENTS)
    hass.services.async_remove(DOMAIN, SERVICE_TRANSLATE_BLUEPRINTS)

    global _REGISTERED_HASS, _REGISTERED_ENTRY
    if _REGISTERED_HASS is hass:
        _REGISTERED_HASS = None
        _REGISTERED_ENTRY = None

    _LOGGER.info("AI Hub services unloaded successfully")
