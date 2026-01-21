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

from .const import (
    CONF_API_KEY,
    CONF_SILICONFLOW_API_KEY,
    DOMAIN,
    TIMEOUT_HEALTH_CHECK,
)
from .diagnostics import get_diagnostics_collector

_LOGGER = logging.getLogger(__name__)

# Update interval for health checks (5 minutes)
SCAN_INTERVAL = timedelta(minutes=5)

# Diagnostic device identifier
DIAGNOSTIC_DEVICE_ID = "diagnostic"


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
    entities.append(AIHubHealthSensor(hass, entry))

    # Edge TTS health sensor (always available, no API key needed)
    entities.append(EdgeTTSHealthSensor(hass, entry))

    # Bemfa health sensor (always check availability)
    entities.append(BemfaHealthSensor(hass, entry))

    # ZhipuAI health sensor (if API key configured)
    if entry.data.get(CONF_API_KEY):
        entities.append(ZhipuAIHealthSensor(hass, entry))

    # SiliconFlow health sensor (if API key configured)
    if entry.data.get(CONF_SILICONFLOW_API_KEY):
        entities.append(SiliconFlowHealthSensor(hass, entry))

    async_add_entities(entities)


class AIHubHealthSensor(SensorEntity):
    """Sensor for overall AI Hub health status."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
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
        self._attr_unique_id = f"{entry.entry_id}_health"
        self._attr_name = "Health Status"
        self._attr_device_info = _get_diagnostic_device_info(entry)

        self._api_statuses: dict[str, dict[str, Any]] = {}
        self._last_check: datetime | None = None
        self._diagnostics = get_diagnostics_collector()

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

        # Add diagnostics summary
        try:
            summary = self._diagnostics.get_summary()
            attrs["uptime_seconds"] = summary.get("uptime_seconds")
            attrs["total_errors"] = summary.get("total_errors", 0)
            attrs["api_summary"] = summary.get("api_summary", {})
        except Exception as e:
            _LOGGER.debug("Failed to get diagnostics summary: %s", e)

        return attrs

    async def async_update(self) -> None:
        """Update the health status."""
        session = async_get_clientsession(self.hass)

        # Check ZhipuAI
        if self._entry.data.get(CONF_API_KEY):
            self._api_statuses["zhipuai"] = await self._check_api(
                session,
                "https://open.bigmodel.cn",
                "ZhipuAI",
            )

        # Check SiliconFlow
        if self._entry.data.get(CONF_SILICONFLOW_API_KEY):
            self._api_statuses["siliconflow"] = await self._check_api(
                session,
                "https://api.siliconflow.cn",
                "SiliconFlow",
            )

        # Check Bemfa (WeChat)
        self._api_statuses["bemfa"] = await self._check_api(
            session,
            "https://apis.bemfa.com",
            "Bemfa",
        )

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
        try:
            start_time = datetime.now()
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_HEALTH_CHECK),
            ) as response:
                latency = (datetime.now() - start_time).total_seconds() * 1000

                return {
                    "status": "healthy" if response.status < 500 else "degraded",
                    "http_status": response.status,
                    "latency_ms": round(latency, 2),
                    "checked_at": datetime.now().isoformat(),
                }

        except aiohttp.ClientError as e:
            _LOGGER.debug("%s health check failed: %s", name, e)
            return {
                "status": "unreachable",
                "error": str(e),
                "checked_at": datetime.now().isoformat(),
            }

        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": f"Timeout after {TIMEOUT_HEALTH_CHECK}s",
                "checked_at": datetime.now().isoformat(),
            }

        except Exception as e:
            _LOGGER.warning("%s health check error: %s", name, e)
            return {
                "status": "error",
                "error": str(e),
                "checked_at": datetime.now().isoformat(),
            }


class ZhipuAIHealthSensor(SensorEntity):
    """Sensor for ZhipuAI API health and latency."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "ms"
    _attr_icon = "mdi:api"
    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_zhipuai_latency"
        self._attr_name = "ZhipuAI Latency"
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

        try:
            start_time = datetime.now()
            async with session.get(
                "https://open.bigmodel.cn",
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_HEALTH_CHECK),
            ) as response:
                self._latency = round(
                    (datetime.now() - start_time).total_seconds() * 1000,
                    2,
                )
                self._status = "healthy" if response.status < 500 else "degraded"

        except Exception as e:
            _LOGGER.debug("ZhipuAI latency check failed: %s", e)
            self._latency = None
            self._status = "unreachable"

        self._last_check = datetime.now()


class SiliconFlowHealthSensor(SensorEntity):
    """Sensor for SiliconFlow API health and latency."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "ms"
    _attr_icon = "mdi:api"
    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_siliconflow_latency"
        self._attr_name = "SiliconFlow Latency"
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

        try:
            start_time = datetime.now()
            async with session.get(
                "https://api.siliconflow.cn",
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_HEALTH_CHECK),
            ) as response:
                self._latency = round(
                    (datetime.now() - start_time).total_seconds() * 1000,
                    2,
                )
                self._status = "healthy" if response.status < 500 else "degraded"

        except Exception as e:
            _LOGGER.debug("SiliconFlow latency check failed: %s", e)
            self._latency = None
            self._status = "unreachable"

        self._last_check = datetime.now()


class EdgeTTSHealthSensor(SensorEntity):
    """Sensor for Edge TTS API health and latency."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "ms"
    _attr_icon = "mdi:text-to-speech"
    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_edge_tts_latency"
        self._attr_name = "Edge TTS Latency"
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

        try:
            start_time = datetime.now()
            async with session.get(
                "https://speech.platform.bing.com",
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_HEALTH_CHECK),
            ) as response:
                self._latency = round(
                    (datetime.now() - start_time).total_seconds() * 1000,
                    2,
                )
                self._status = "healthy" if response.status < 500 else "degraded"

        except Exception as e:
            _LOGGER.debug("Edge TTS latency check failed: %s", e)
            self._latency = None
            self._status = "unreachable"

        self._last_check = datetime.now()


class BemfaHealthSensor(SensorEntity):
    """Sensor for Bemfa API health and latency."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "ms"
    _attr_icon = "mdi:message-text"
    _attr_should_poll = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_bemfa_latency"
        self._attr_name = "Bemfa Latency"
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

        try:
            start_time = datetime.now()
            async with session.get(
                "https://apis.bemfa.com",
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_HEALTH_CHECK),
            ) as response:
                self._latency = round(
                    (datetime.now() - start_time).total_seconds() * 1000,
                    2,
                )
                self._status = "healthy" if response.status < 500 else "degraded"

        except Exception as e:
            _LOGGER.debug("Bemfa latency check failed: %s", e)
            self._latency = None
            self._status = "unreachable"

        self._last_check = datetime.now()
