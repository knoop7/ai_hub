"""Button platform for AI Hub WeChat notifications."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_entry_flow
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import device_registry as dr
from datetime import datetime

try:
    from ..const import DOMAIN
except ImportError:
    DOMAIN = "ai_hub"

_LOGGER = logging.getLogger(__name__)


class AIHubWeChatButton(ButtonEntity):
    """AI Hub WeChat test button."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:wechat"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, subentry: config_entry_flow.ConfigSubentry) -> None:
        """Initialize the button."""
        super().__init__()
        self._hass = hass
        self._subentry = subentry
        self._attr_unique_id = f"{subentry.subentry_id}_wechat_test"
        self._attr_name = "微信消息测试"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="老王杂谈说",
            model="WeChat Notification",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        """Press the button - send a test message."""
        try:
            await self._hass.services.async_call(
                "ai_hub",
                "send_wechat_message",
                {
                    "device_entity": "sun.sun",
                    "message": f"🤖 AI Hub 微信测试 - 时间: {datetime.now().strftime('%H:%M:%S')}",
                    "url": ""
                },
                blocking=True,
                return_response=True,
            )
        except Exception as e:
            _LOGGER.error("Failed to send test WeChat message: %s", e)


class AIHubTranslationButton(ButtonEntity):
    """AI Hub Translation button."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:translate"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, subentry: config_entry_flow.ConfigSubentry) -> None:
        """Initialize the button."""
        super().__init__()
        self._hass = hass
        self._subentry = subentry
        self._attr_unique_id = f"{subentry.subentry_id}_translate"
        self._attr_name = "一键汉化"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="老王杂谈说",
            model="Integration Localization",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        """Press the button - trigger translation."""
        try:
            await self._hass.services.async_call(
                "ai_hub",
                "translate_components",
                {
                    "list_components": False,
                    "target_component": "",
                    "force_translation": False
                },
                blocking=True,
                return_response=True,
            )
        except Exception as e:
            _LOGGER.error("Failed to run translation process: %s", e)


class AIHubBlueprintTranslationButton(ButtonEntity):
    """AI Hub Blueprint Translation button."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:file-document-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, subentry: config_entry_flow.ConfigSubentry) -> None:
        """Initialize the button."""
        super().__init__()
        self._hass = hass
        self._subentry = subentry
        self._attr_unique_id = f"{subentry.subentry_id}_blueprint_translate"
        self._attr_name = "蓝图汉化"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="老王杂谈说",
            model="Blueprint Translation",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        """Press the button - trigger blueprint translation."""
        try:
            await self._hass.services.async_call(
                "ai_hub",
                "translate_blueprints",
                {
                    "list_blueprints": False,
                    "target_blueprint": ""
                },
                blocking=True,
                return_response=True,
            )
        except Exception as e:
            _LOGGER.error("Failed to run blueprint translation process: %s", e)


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
            buttons.append(AIHubTranslationButton(hass, entry, subentry))
        elif subentry.subentry_type == "blueprint_translation":
            buttons.append(AIHubBlueprintTranslationButton(hass, entry, subentry))

    for button in buttons:
        async_add_entities([button], config_subentry_id=button._subentry.subentry_id)
