"""Services for AI Hub integration - 精简版，实际处理委托给 services_lib 模块."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall

from .config_resolver import (
    get_effective_conversation_config,
    get_effective_image_config,
    get_effective_stt_config,
    get_effective_translation_config,
)
from .consts import (
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
_SERVICE_CONTEXTS_KEY = f"{DOMAIN}_service_contexts"
_SERVICES_REGISTERED_KEY = f"{DOMAIN}_services_registered"

_get_conversation_config = get_effective_conversation_config
_get_image_config = get_effective_image_config
_get_stt_config = get_effective_stt_config
_get_translation_config = get_effective_translation_config


def _has_configured_api_key(api_key: Any) -> bool:
    """Return whether the resolved API key is a non-empty string."""
    return isinstance(api_key, str) and bool(api_key.strip())


def _register_service(
    hass: HomeAssistant,
    service_name: str,
    handler,
    schema: dict[str, Any],
) -> None:
    """Register a response-capable AI Hub service."""
    hass.services.async_register(
        DOMAIN,
        service_name,
        handler,
        schema=vol.Schema(schema),
        supports_response=True,
    )


def _get_registered_context() -> tuple[HomeAssistant | None, object | None]:
    """Return the most recently registered service context."""
    return _REGISTERED_HASS, _REGISTERED_ENTRY


def _get_service_contexts(hass: HomeAssistant) -> dict[str, object]:
    """Return the service context registry for this Home Assistant instance."""
    return hass.data.setdefault(_SERVICE_CONTEXTS_KEY, {})


def _set_active_entry(hass: HomeAssistant) -> None:
    """Update the fallback active entry used by module-level test helpers."""
    global _REGISTERED_HASS, _REGISTERED_ENTRY

    contexts = _get_service_contexts(hass)
    _REGISTERED_HASS = hass
    _REGISTERED_ENTRY = next(reversed(contexts.values()), None) if contexts else None


def _entry_has_subentry_type(config_entry: Any, subentry_type: str) -> bool:
    """Return whether the config entry contains the requested subentry type."""
    return any(
        subentry.subentry_type == subentry_type
        for subentry in getattr(config_entry, "subentries", {}).values()
    )


def _resolve_service_entry(
    call: ServiceCall,
    subentry_type: str | None = None,
) -> tuple[HomeAssistant | None, Any | None, str | None]:
    """Resolve which config entry should handle a service call."""
    hass, fallback_entry = _get_registered_context()
    if hass is None:
        return None, None, "AI Hub 未初始化"

    contexts = _get_service_contexts(hass)
    explicit_entry_id = call.data.get("config_entry_id")

    if explicit_entry_id:
        config_entry = contexts.get(explicit_entry_id)
        if config_entry is None:
            return hass, None, f"未找到 AI Hub 配置项: {explicit_entry_id}"
        if subentry_type and not _entry_has_subentry_type(config_entry, subentry_type):
            return hass, None, f"指定的配置项不包含 {subentry_type} 子项"
        return hass, config_entry, None

    candidates = list(contexts.values())
    if subentry_type is not None:
        candidates = [
            config_entry
            for config_entry in candidates
            if _entry_has_subentry_type(config_entry, subentry_type)
        ]

    if not candidates:
        if fallback_entry is not None and (
            subentry_type is None or _entry_has_subentry_type(fallback_entry, subentry_type)
        ):
            return hass, fallback_entry, None
        return hass, None, "没有可用的 AI Hub 配置"

    if len(candidates) > 1:
        return hass, None, "检测到多个 AI Hub 配置，请在服务中指定 config_entry_id"

    return hass, candidates[0], None


def _resolve_service_config(
    call: ServiceCall,
    subentry_type: str,
    config_getter,
) -> tuple[HomeAssistant | None, Any | None, str | None]:
    """Resolve the active config entry and derived runtime config for a service."""
    hass, config_entry, error = _resolve_service_entry(call, subentry_type)
    if error is not None or hass is None or config_entry is None:
        return hass, None, error or "API密钥未配置"

    return hass, config_getter(config_entry), None


async def _handle_analyze_image(call: ServiceCall) -> dict:
    """Handle analyze image service calls."""
    hass, config, error = _resolve_service_config(call, "conversation", _get_conversation_config)
    if error is not None or hass is None or config is None:
        return {"success": False, "error": error or "API密钥未配置"}

    chat_url, _, effective_key = config
    if not _has_configured_api_key(effective_key):
        return {"success": False, "error": "API密钥未配置"}
    return await handle_analyze_image(hass, call, effective_key, chat_url)


async def _handle_generate_image(call: ServiceCall) -> dict:
    """Handle generate image service calls."""
    hass, config, error = _resolve_service_config(call, "ai_task_data", _get_image_config)
    if error is not None or hass is None or config is None:
        return {"success": False, "error": error or "API密钥未配置"}

    image_url, effective_key = config
    if not _has_configured_api_key(effective_key):
        return {"success": False, "error": "API密钥未配置"}
    return await handle_generate_image(hass, call, effective_key, image_url)


async def _handle_stt_transcribe(call: ServiceCall) -> dict:
    """Handle STT transcription service calls."""
    hass, config, error = _resolve_service_config(call, "stt", _get_stt_config)
    if error is not None or hass is None or config is None:
        return {"success": False, "error": error or "API密钥未配置"}

    stt_url, api_key = config
    if not _has_configured_api_key(api_key):
        return {"success": False, "error": "API密钥未配置"}
    return await handle_stt_transcribe(hass, call, api_key, stt_url)


async def async_setup_services(hass: HomeAssistant, config_entry) -> None:
    """Set up services for AI Hub integration."""

    contexts = _get_service_contexts(hass)
    contexts[config_entry.entry_id] = config_entry
    _set_active_entry(hass)

    if hass.data.get(_SERVICES_REGISTERED_KEY):
        _LOGGER.debug("AI Hub services already registered; updated active context")
        return

    # ========== 图像分析服务 ==========
    # ========== TTS 语音合成服务（统一） ==========
    async def _handle_tts_say(call: ServiceCall) -> dict:
        """Handle TTS service with optional streaming support."""
        stream = call.data.get("stream", False)
        if stream:
            return await handle_tts_stream(hass, call)
        return await handle_tts_speech(hass, call)

    # ========== STT 语音转文字服务 ==========
    # ========== 组件翻译服务 ==========
    async def _handle_translate_components(call: ServiceCall) -> dict:
        try:
            _, config, error = _resolve_service_config(call, "translation", _get_translation_config)
            if error is not None or config is None:
                return {"success": False, "error": error or "API密钥未配置"}

            list_components = call.data.get("list_components", False)
            target_component = call.data.get("target_component", "").strip()
            force_translation = call.data.get("force_translation", False)

            chat_url, model, effective_key = config

            if not list_components and not _has_configured_api_key(effective_key):
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
            _, config, error = _resolve_service_config(call, "translation", _get_translation_config)
            if error is not None or config is None:
                return {"success": False, "error": error or "API密钥未配置"}

            list_blueprints = call.data.get("list_blueprints", False)
            target_blueprint = call.data.get("target_blueprint", "").strip()
            retranslate = call.data.get("retranslate", False)
            blueprints_path = hass.config.path("blueprints")

            chat_url, model, effective_key = config

            if not list_blueprints and not _has_configured_api_key(effective_key):
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
    _register_service(hass, SERVICE_ANALYZE_IMAGE, _handle_analyze_image, IMAGE_ANALYZER_SCHEMA)
    _register_service(hass, SERVICE_GENERATE_IMAGE, _handle_generate_image, IMAGE_GENERATOR_SCHEMA)
    _register_service(hass, SERVICE_TTS_SAY, _handle_tts_say, TTS_SCHEMA)
    _register_service(hass, SERVICE_STT_TRANSCRIBE, _handle_stt_transcribe, STT_SCHEMA)
    _register_service(hass, SERVICE_TRANSLATE_COMPONENTS, _handle_translate_components, TRANSLATION_SCHEMA)
    _register_service(
        hass,
        SERVICE_TRANSLATE_BLUEPRINTS,
        _handle_translate_blueprints,
        BLUEPRINTS_TRANSLATION_SCHEMA,
    )

    hass.data[_SERVICES_REGISTERED_KEY] = True
    _LOGGER.info("AI Hub services registered successfully")


async def async_unload_services(hass: HomeAssistant, entry_id: str | None = None) -> None:
    """Unload all services for AI Hub integration.

    Args:
        hass: Home Assistant instance
    """
    contexts = _get_service_contexts(hass)
    if entry_id is not None:
        contexts.pop(entry_id, None)
        _set_active_entry(hass)
        if contexts:
            _LOGGER.debug("Skipping AI Hub service unload; other entries still active")
            return

    if not hass.data.get(_SERVICES_REGISTERED_KEY):
        return

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

    hass.data.pop(_SERVICES_REGISTERED_KEY, None)
    hass.data.pop(_SERVICE_CONTEXTS_KEY, None)

    _LOGGER.info("AI Hub services unloaded successfully")
