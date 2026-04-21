"""Health check sensor for AI Hub integration.

This module provides a sensor that monitors the health and status
of the AI Hub integration and its connected APIs.

Features:
- API connectivity monitoring
- Latency tracking
- Error rate monitoring
- Automatic status updates
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .consts import (
    DOMAIN,
    EDGE_TTS_BASE_URL,
    SILICONFLOW_ROOT_URL,
    SUBENTRY_AI_TASK,
    SUBENTRY_CONVERSATION,
    SUBENTRY_STT,
    SUBENTRY_TRANSLATION,
    SUBENTRY_TTS,
    TIMEOUT_HEALTH_CHECK,
)
from .api_health import async_probe_url
from .diagnostics import collect_api_monitor_targets

_LOGGER = logging.getLogger(__name__)

# Update interval for health checks (5 minutes)
SCAN_INTERVAL = timedelta(minutes=5)

# Diagnostic device identifier
DIAGNOSTIC_DEVICE_ID = "diagnostic"


def _has_subentry_type(entry: ConfigEntry, *subentry_types: str) -> bool:
    """Return whether the config entry contains any of the requested subentry types."""
    return any(
        subentry.subentry_type in subentry_types
        for subentry in entry.subentries.values()
    )


def _get_diagnostic_device_info(entry: ConfigEntry) -> dr.DeviceInfo:
    """Get device info for the diagnostic service."""
    return dr.DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{DIAGNOSTIC_DEVICE_ID}")},
        name="AI Hub Diagnostic",
        manufacturer="老王杂谈说",
        model="Diagnostic Service",
        entry_type=dr.DeviceEntryType.SERVICE,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up health check sensor entities."""
    entities = []

    # Main integration health sensor (always added)
    entities.append(AIHubHealthCheckSensor(hass, entry))

    if _has_subentry_type(entry, SUBENTRY_TTS):
        entities.append(EdgeTTSHealthSensor(hass, entry))

    if _has_subentry_type(
        entry,
        SUBENTRY_CONVERSATION,
        SUBENTRY_AI_TASK,
        SUBENTRY_STT,
        SUBENTRY_TRANSLATION,
    ):
        entities.append(SiliconFlowHealthSensor(hass, entry))

    async_add_entities(entities)


class AIHubHealthCheckSensor(SensorEntity):
    """Sensor for overall AI Hub health status."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_icon = "mdi:heart-pulse"
    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the health sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_health_sensor"
        self._attr_name = "Health Status"
        self._attr_device_info = _get_diagnostic_device_info(entry)

        self._api_statuses: dict[str, dict[str, Any]] = {}
        self._last_check: datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Run initial update when entity is added."""
        await super().async_added_to_hass()
        # Trigger immediate update on startup
        await self.async_update()

    @property
    def native_value(self) -> str:
        """Return the health status."""
        if not self._api_statuses:
            return "unknown"

        # Check if all APIs are healthy
        all_healthy = all(
            status.get("status") == "healthy"
            for status in self._api_statuses.values()
        )

        if all_healthy:
            return "healthy"

        # Check if any API is down
        any_down = any(
            status.get("status") == "unreachable"
            for status in self._api_statuses.values()
        )

        if any_down:
            return "degraded"

        return "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs: dict[str, Any] = {
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "apis": self._api_statuses,
        }

        return attrs

    async def async_update(self) -> None:
        """Update the health status."""
        session = async_get_clientsession(self.hass)
        self._api_statuses = {}

        current_entry = self.hass.config_entries.async_get_entry(self._entry.entry_id)
        if current_entry is not None:
            self._entry = current_entry

        for target in collect_api_monitor_targets(self._entry):
            api_status = await self._check_api(session, target["monitor_url"], target["label"])
            api_status["url"] = target["url"]
            api_status["monitor_url"] = target["monitor_url"]
            api_status["sources"] = target["sources"]
            self._api_statuses[target["key"]] = api_status

        self._last_check = datetime.now()

    async def _check_api(
        self,
        session: aiohttp.ClientSession,
        url: str,
        name: str,
    ) -> dict[str, Any]:
        """Check if an API endpoint is reachable.

        Args:
            session: aiohttp session
            url: URL to check
            name: Name of the API for logging

        Returns:
            Status dictionary
        """
        probe = await async_probe_url(session, url, timeout_seconds=TIMEOUT_HEALTH_CHECK)
        if probe.get("reachable"):
            return {
                "status": "healthy" if probe["http_status"] < 500 else "degraded",
                "http_status": probe["http_status"],
                "latency_ms": probe["latency_ms"],
                "checked_at": probe["checked_at"],
            }

        if probe.get("error_type") == "client":
            _LOGGER.debug("%s health check failed: %s", name, probe["error"])
            return {
                "status": "unreachable",
                "error": probe["error"],
                "checked_at": probe["checked_at"],
            }

        if probe.get("error_type") == "timeout":
            return {
                "status": "timeout",
                "error": probe["error"],
                "checked_at": probe["checked_at"],
            }

        return {
            "status": "error",
            "error": probe.get("error", "Unknown error"),
            "checked_at": probe["checked_at"],
        }


class _BaseHealthSensor(SensorEntity):
    """Base class for API health check sensors.

    This class provides common functionality for all health sensors that check
    API endpoints and measure latency. Subclasses only need to define the
    check URL and optional customizations.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "ms"
    _attr_icon = "mdi:api"
    _attr_should_poll = True

    # Subclasses should override these
    _check_url: str
    _name_suffix: str

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{self._name_suffix}_latency"
        self._attr_name = f"{self._name_suffix.replace('_', ' ').title()} Latency"
        self._attr_device_info = _get_diagnostic_device_info(entry)

        self._latency: float | None = None
        self._status: str = "unknown"
        self._last_check: datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Run initial update when entity is added."""
        await super().async_added_to_hass()
        await self.async_update()

    @property
    def native_value(self) -> float | None:
        """Return the latency in milliseconds."""
        return self._latency

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "status": self._status,
            "last_check": self._last_check.isoformat() if self._last_check else None,
        }

    async def async_update(self) -> None:
        """Update the sensor."""
        session = async_get_clientsession(self.hass)

        probe = await async_probe_url(session, self._check_url, timeout_seconds=TIMEOUT_HEALTH_CHECK)
        if probe.get("reachable"):
            self._latency = probe["latency_ms"]
            self._status = "healthy" if probe["http_status"] < 500 else "degraded"
        else:
            if probe.get("error_type") in {"client", "timeout"}:
                _LOGGER.debug("%s latency check failed: %s", self._name_suffix, probe["error"])
            self._latency = None
            self._status = "unreachable"

        self._last_check = datetime.fromisoformat(probe["checked_at"])


class SiliconFlowHealthSensor(_BaseHealthSensor):
    """Sensor for SiliconFlow API health and latency."""

    _check_url = SILICONFLOW_ROOT_URL
    _name_suffix = "siliconflow"


class EdgeTTSHealthSensor(_BaseHealthSensor):
    """Sensor for Edge TTS API health and latency."""

    _check_url = EDGE_TTS_BASE_URL
    _name_suffix = "edge_tts"
    _attr_icon = "mdi:text-to-speech"
