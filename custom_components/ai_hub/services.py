"""Services for AI Hub integration - 精简版，实际处理委托给 services_lib 模块."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    CONF_BEMFA_UID,
    CONF_CHAT_MODEL,
    CONF_CHAT_URL,
    CONF_CUSTOM_API_KEY,
    CONF_IMAGE_URL,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
    SERVICE_ANALYZE_IMAGE,
    SERVICE_GENERATE_IMAGE,
    SERVICE_SEND_WECHAT_MESSAGE,
    SERVICE_STT_TRANSCRIBE,
    SERVICE_TRANSLATE_BLUEPRINTS,
    SERVICE_TRANSLATE_COMPONENTS,
    SERVICE_TTS_SPEECH,
    SERVICE_TTS_STREAM,
)
from .services_lib import (
    BLUEPRINTS_TRANSLATION_SCHEMA,
    # Schemas
    IMAGE_ANALYZER_SCHEMA,
    IMAGE_GENERATOR_SCHEMA,
    STT_SCHEMA,
    TRANSLATION_SCHEMA,
    TTS_SCHEMA,
    TTS_STREAM_SCHEMA,
    WECHAT_SCHEMA,
    async_translate_all_blueprints,
    async_translate_all_components,
    # Handlers
    handle_analyze_image,
    handle_generate_image,
    handle_send_wechat_message,
    handle_stt_transcribe,
    handle_tts_speech,
    handle_tts_stream,
)

_LOGGER = logging.getLogger(__name__)


def _get_conversation_config(config_entry) -> tuple[str, str, str]:
    """Get chat URL, model and API key from Conversation Agent subentry."""
    from .const import AI_HUB_CHAT_URL
    chat_url = AI_HUB_CHAT_URL
    model = RECOMMENDED_CHAT_MODEL
    custom_api_key = ""

    for subentry in config_entry.subentries.values():
        if subentry.subentry_type == "conversation":
            chat_url = subentry.data.get(CONF_CHAT_URL, chat_url)
            model = subentry.data.get(CONF_CHAT_MODEL, model)
            custom_api_key = subentry.data.get(CONF_CUSTOM_API_KEY, "").strip()
            break

    # Use custom key if provided, otherwise use main key
    api_key = custom_api_key if custom_api_key else config_entry.runtime_data
    return chat_url, model, api_key


def _get_image_config(config_entry) -> tuple[str, str]:
    """Get image URL and API key from AI Task subentry."""
    from .const import AI_HUB_IMAGE_GEN_URL
    image_url = AI_HUB_IMAGE_GEN_URL
    custom_api_key = ""

    for subentry in config_entry.subentries.values():
        if subentry.subentry_type == "ai_task_data":
            image_url = subentry.data.get(CONF_IMAGE_URL, image_url)
            custom_api_key = subentry.data.get(CONF_CUSTOM_API_KEY, "").strip()
            break

    # Use custom key if provided, otherwise use main key
    api_key = custom_api_key if custom_api_key else config_entry.runtime_data
    return image_url, api_key


async def async_setup_services(hass: HomeAssistant, config_entry) -> None:
    """Set up services for AI Hub integration."""

    api_key = config_entry.runtime_data
    bemfa_uid = config_entry.data.get(CONF_BEMFA_UID) if hasattr(config_entry, 'data') else None

    if bemfa_uid:
        setattr(config_entry, 'bemfa_uid', bemfa_uid)

    def has_api_key() -> bool:
        """Check if any API key is available (main or custom)."""
        return api_key is not None and api_key.strip() != ""

    # ========== 图像分析服务 ==========
    async def _handle_analyze_image(call: ServiceCall) -> dict:
        chat_url, _, effective_key = _get_conversation_config(config_entry)
        if not effective_key or not effective_key.strip():
            return {"success": False, "error": "API密钥未配置"}
        return await handle_analyze_image(hass, call, effective_key, chat_url)

    # ========== 图像生成服务 ==========
    async def _handle_generate_image(call: ServiceCall) -> dict:
        image_url, effective_key = _get_image_config(config_entry)
        if not effective_key or not effective_key.strip():
            return {"success": False, "error": "API密钥未配置"}
        return await handle_generate_image(hass, call, effective_key, image_url)

    # ========== TTS 语音合成服务 ==========
    async def _handle_tts_speech(call: ServiceCall) -> dict:
        if not has_api_key():
            return {"success": False, "error": "API密钥未配置"}
        return await handle_tts_speech(hass, call, api_key)

    # ========== TTS 流式语音服务 ==========
    async def _handle_tts_stream(call: ServiceCall) -> dict:
        return await handle_tts_stream(hass, call)

    # ========== STT 语音转文字服务 ==========
    async def _handle_stt_transcribe(call: ServiceCall) -> dict:
        api_key = config_entry.data.get(CONF_API_KEY) if hasattr(config_entry, 'data') else None
        if not api_key or not api_key.strip():
            return {"success": False, "error": "API密钥未配置"}
        return await handle_stt_transcribe(hass, call, api_key)

    # ========== 微信消息服务 ==========
    async def _handle_send_wechat_message(call: ServiceCall) -> dict:
        uid = getattr(config_entry, 'bemfa_uid', None) or call.data.get("bemfa_uid")
        return await handle_send_wechat_message(hass, call, uid)

    # ========== 组件翻译服务 ==========
    async def _handle_translate_components(call: ServiceCall) -> dict:
        try:
            list_components = call.data.get("list_components", False)
            target_component = call.data.get("target_component", "").strip()
            force_translation = call.data.get("force_translation", False)

            # Get chat URL, model and API key from Conversation Agent
            chat_url, model, effective_key = _get_conversation_config(config_entry)

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

            # Get chat URL, model and API key from Conversation Agent
            chat_url, model, effective_key = _get_conversation_config(config_entry)

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
        DOMAIN, SERVICE_TTS_SPEECH, _handle_tts_speech,
        schema=vol.Schema(TTS_SCHEMA), supports_response=True
    )

    hass.services.async_register(
        DOMAIN, SERVICE_TTS_STREAM, _handle_tts_stream,
        schema=vol.Schema(TTS_STREAM_SCHEMA), supports_response=True
    )

    hass.services.async_register(
        DOMAIN, SERVICE_STT_TRANSCRIBE, _handle_stt_transcribe,
        schema=vol.Schema(STT_SCHEMA), supports_response=True
    )

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_WECHAT_MESSAGE, _handle_send_wechat_message,
        schema=vol.Schema(WECHAT_SCHEMA), supports_response=True
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
    hass.services.async_remove(DOMAIN, SERVICE_TTS_SPEECH)
    hass.services.async_remove(DOMAIN, SERVICE_TTS_STREAM)
    hass.services.async_remove(DOMAIN, SERVICE_STT_TRANSCRIBE)
    hass.services.async_remove(DOMAIN, SERVICE_SEND_WECHAT_MESSAGE)
    hass.services.async_remove(DOMAIN, SERVICE_TRANSLATE_COMPONENTS)
    hass.services.async_remove(DOMAIN, SERVICE_TRANSLATE_BLUEPRINTS)

    _LOGGER.info("AI Hub services unloaded successfully")
