"""Button platform for AI Hub WeChat notifications."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# Button configuration registry
_BUTTON_CONFIGS: dict[str, dict[str, Any]] = {
    "wechat_test": {
        "name": "微信消息测试",
        "unique_id_suffix": "wechat_test",
        "icon": "mdi:wechat",
        "model": "WeChat Notification",
        "service": "send_wechat_message",
        "service_data": {
            "device_entity": "sun.sun",
            "message": "",
            "url": ""
        },
        "message_template": "🤖 AI Hub 微信测试 - 时间: {time}",
    },
    "translate": {
        "name": "一键汉化",
        "unique_id_suffix": "translate",
        "icon": "mdi:translate",
        "model": "Integration Localization",
        "service": "translate_components",
        "service_data": {
            "list_components": False,
            "target_component": "",
            "force_translation": False
        },
    },
    "blueprint_translate": {
        "name": "蓝图汉化",
        "unique_id_suffix": "blueprint_translate",
        "icon": "mdi:file-document-outline",
        "model": "Blueprint Translation",
        "service": "translate_blueprints",
        "service_data": {
            "list_blueprints": False,
            "target_blueprint": ""
        },
    },
}


class _AIHubServiceButton(ButtonEntity):
    """Base class for AI Hub service buttons.

    This class provides common functionality for all buttons that trigger
    AI Hub services. Button behavior is driven by configuration from
    _BUTTON_CONFIGS.
    """

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: config_entry_flow.ConfigSubentry,
        button_type: str,
    ) -> None:
        """Initialize the button."""
        self._hass = hass
        self._subentry = subentry
        self._button_type = button_type

        # Get configuration for this button type
        config = _BUTTON_CONFIGS[button_type]

        # Set attributes from configuration
        self._attr_unique_id = f"{subentry.subentry_id}_{config['unique_id_suffix']}"
        self._attr_name = config["name"]
        self._attr_icon = config["icon"]
        self._service = config["service"]
        self._service_data = config["service_data"].copy()
        self._model = config["model"]
        self._message_template = config.get("message_template")

        # Create device info
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="老王杂谈说",
            model=self._model,
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        """Press the button - trigger the configured service."""
        try:
            # Prepare service data
            service_data = self._service_data.copy()

            # Apply message template if configured
            if self._message_template:
                time_str = datetime.now().strftime('%H:%M:%S')
                service_data["message"] = self._message_template.format(time=time_str)

            await self._hass.services.async_call(
                "ai_hub",
                self._service,
                service_data,
                blocking=True,
                return_response=True,
            )
        except Exception as e:
            _LOGGER.error(
                "Failed to execute service %s for button %s: %s",
                self._service,
                self._button_type,
                e
            )


# Legacy aliases for backward compatibility
class AIHubWeChatButton(_AIHubServiceButton):
    """AI Hub WeChat test button - legacy wrapper."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: config_entry_flow.ConfigSubentry,
    ) -> None:
        super().__init__(hass, entry, subentry, "wechat_test")


class AIHubTranslationButton(_AIHubServiceButton):
    """AI Hub Translation button - legacy wrapper."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: config_entry_flow.ConfigSubentry,
    ) -> None:
        super().__init__(hass, entry, subentry, "translate")


class AIHubBlueprintTranslationButton(_AIHubServiceButton):
    """AI Hub Blueprint Translation button - legacy wrapper."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        subentry: config_entry_flow.ConfigSubentry,
    ) -> None:
        super().__init__(hass, entry, subentry, "blueprint_translate")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AI Hub button platform."""
    if not hasattr(entry, 'subentries') or not entry.subentries:
        return

    buttons = []
    for subentry in entry.subentries.values():
        if subentry.subentry_type == "wechat":
            buttons.append(AIHubWeChatButton(hass, entry, subentry))
        elif subentry.subentry_type == "translation":
            # Unified translation: add both component and blueprint translation buttons
            buttons.append(AIHubTranslationButton(hass, entry, subentry))
            buttons.append(AIHubBlueprintTranslationButton(hass, entry, subentry))

    for button in buttons:
        async_add_entities([button], config_subentry_id=button._subentry.subentry_id)
