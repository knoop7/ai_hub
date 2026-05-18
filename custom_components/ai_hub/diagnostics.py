"""Diagnostics support for AI Hub integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

try:
    from homeassistant.components.diagnostics import async_redact_data
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
except ModuleNotFoundError:  # pragma: no cover - used only in lightweight test environments
    ConfigEntry = Any  # type: ignore[assignment]
    HomeAssistant = Any  # type: ignore[assignment]

    def async_redact_data(data: dict[str, Any], to_redact: set[str]) -> dict[str, Any]:
        """Fallback redaction helper when Home Assistant is unavailable."""
        redacted = {}
        for key, value in data.items():
            if key in to_redact:
                redacted[key] = "REDACTED"
            else:
                redacted[key] = value
        return redacted

from .consts import (
    CONF_API_KEY,
    CONF_CUSTOM_API_KEY,
    DOMAIN,
    RETRY_BASE_DELAY,
    RETRY_MAX_ATTEMPTS,
    TIMEOUT_CHAT_API,
    TIMEOUT_IMAGE_API,
    TIMEOUT_STT_API,
    TIMEOUT_TTS_API,
)

_LOGGER = logging.getLogger(__name__)

# Keys that contain sensitive data and should be redacted
TO_REDACT = {
    CONF_API_KEY,
    CONF_CUSTOM_API_KEY,
    "api_key",
    "token",
    "password",
    "secret",
    "authorization",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    This is called when the user requests diagnostics from the
    Home Assistant UI under Settings -> Integrations -> AI Hub -> Diagnostics.

    Args:
        hass: Home Assistant instance
        entry: Config entry for this integration

    Returns:
        Dictionary containing diagnostic information
    """
    # Wrap all diagnostics under the "ai_hub" category
    diagnostics: dict[str, Any] = {
        "ai_hub": {
            "integration": {
                "domain": DOMAIN,
            "title": entry.title,
            "entry_id": entry.entry_id,
            "version": entry.version,
            "minor_version": entry.minor_version,
        },
            "configuration": await _get_configuration_diagnostics(hass, entry),
            "subentries": await _get_subentries_diagnostics(hass, entry),
            "entities": await _get_entities_diagnostics(hass, entry),
            "timeout_config": _get_timeout_config(),
            "retry_config": _get_retry_config(),
            "statistics": _get_statistics_diagnostics(hass, entry),
            "system_info": _get_system_info(hass),
        }
    }

    return diagnostics


async def _get_configuration_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Get configuration diagnostics with sensitive data redacted."""
    config = {
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
    }

    # Check if API key is configured
    api_key = entry.options.get(CONF_API_KEY) or entry.data.get(CONF_API_KEY, "")
    config["api_key_configured"] = bool(api_key and api_key.strip())
    config["api_key_length"] = len(api_key) if api_key else 0

    return config
async def _get_subentries_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Get diagnostics for all subentries."""
    subentries_info: dict[str, Any] = {}

    if not entry.subentries:
        return {"count": 0, "entries": []}

    for subentry_id, subentry in entry.subentries.items():
        subentry_data = async_redact_data(dict(subentry.data), TO_REDACT)
        subentries_info[subentry_id] = {
            "type": subentry.subentry_type,
            "title": subentry.title,
            "data": subentry_data,
        }

    return {
        "count": len(entry.subentries),
        "entries": subentries_info,
    }


async def _get_entities_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Get diagnostics for all entities created by this integration."""
    from homeassistant.helpers import entity_registry as er

    entity_registry = er.async_get(hass)
    entities_info: dict[str, list[dict[str, Any]]] = {
        "conversation": [],
        "ai_task": [],
        "tts": [],
        "stt": [],
        "button": [],
        "sensor": [],
        "other": [],
    }

    # Get all entities for this config entry
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        entity_data = {
            "entity_id": entity_entry.entity_id,
            "unique_id": entity_entry.unique_id,
            "name": entity_entry.name or entity_entry.original_name,
            "platform": entity_entry.platform,
            "disabled": entity_entry.disabled,
            "disabled_by": str(entity_entry.disabled_by) if entity_entry.disabled_by else None,
        }

        # Categorize by domain
        domain = entity_entry.domain
        if domain in entities_info:
            entities_info[domain].append(entity_data)
        else:
            entities_info["other"].append(entity_data)

    # Calculate totals
    total_entities = sum(len(entities) for entities in entities_info.values())

    return {
        "total_count": total_entities,
        "by_type": {
            domain: {"count": len(entities), "entities": entities}
            for domain, entities in entities_info.items()
            if entities  # Only include non-empty categories
        },
    }
def _get_timeout_config() -> dict[str, Any]:
    """Get current timeout configuration."""
    return {
        "chat_api_seconds": TIMEOUT_CHAT_API,
        "image_api_seconds": TIMEOUT_IMAGE_API,
        "stt_api_seconds": TIMEOUT_STT_API,
        "tts_api_seconds": TIMEOUT_TTS_API,
    }


def _get_retry_config() -> dict[str, Any]:
    """Get current retry configuration."""
    return {
        "max_attempts": RETRY_MAX_ATTEMPTS,
        "base_delay_seconds": RETRY_BASE_DELAY,
    }


def _get_statistics_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return minimal runtime statistics that are actually available."""
    # Get integration data if available
    integration_data = hass.data.get(DOMAIN, {})

    stats: dict[str, Any] = {
        "integration_data_available": bool(integration_data),
        "entry_has_runtime_data": entry.entry_id in integration_data,
    }

    # Check for any cached statistics
    if entry.entry_id in integration_data:
        entry_data = integration_data[entry.entry_id]
        if isinstance(entry_data, dict):
            if "stats" in entry_data:
                stats["cached_stats"] = entry_data["stats"]

    return stats


def _get_system_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get relevant system information."""
    import sys

    return {
        "python_version": sys.version,
        "home_assistant_version": hass.config.version,
        "timezone": str(hass.config.time_zone),
        "language": hass.config.language,
        "units": hass.config.units.name if hass.config.units else "unknown",
        "timestamp": datetime.now().isoformat(),
    }
