"""The AI Hub integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, TypeAlias

import aiohttp

try:
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry
    from homeassistant.const import CONF_API_KEY, Platform
    from homeassistant.core import HomeAssistant
    from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
except ModuleNotFoundError:  # pragma: no cover - used only in lightweight test environments
    ConfigEntry = Any  # type: ignore[assignment]
    ConfigSubentry = Any  # type: ignore[assignment]
    HomeAssistant = Any  # type: ignore[assignment]
    CONF_API_KEY = "api_key"

    class ConfigEntryAuthFailed(Exception):
        """Fallback exception when Home Assistant is not installed."""

    class ConfigEntryNotReady(Exception):
        """Fallback exception when Home Assistant is not installed."""

    Platform = None  # type: ignore[assignment]

from .consts import DOMAIN

_LOGGER = logging.getLogger(__name__)

if Platform is None:
    PLATFORMS: list[Any] = []
else:
    PLATFORMS = [
        Platform.CONVERSATION,
        Platform.AI_TASK,
        Platform.TTS,
        Platform.STT,
        Platform.BUTTON,
        Platform.SENSOR,
    ]

AIHubConfigEntry: TypeAlias = ConfigEntry  # Store API key


@dataclass
class AIHubData:
    """Runtime data for AI Hub integration.

    This class holds all runtime state for the integration,
    avoiding global variables and ensuring proper cleanup on reload.
    """

    api_key: str | None = None
    tts_cache: Any = None
    provider_registry: Any = None
    diagnostics_collector: Any = None
    stats: dict[str, Any] = field(default_factory=dict)

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.tts_cache is not None:
            self.tts_cache.clear()
        self.provider_registry = None


def get_ai_hub_data(hass: HomeAssistant) -> AIHubData | None:
    """Get AI Hub runtime data."""
    return hass.data.get(DOMAIN)


def get_configured_api_key(entry: ConfigEntry) -> str:
    """Return the configured main API key from options or entry data."""
    api_key = entry.options.get(CONF_API_KEY) or entry.data.get(CONF_API_KEY) or ""
    return api_key.strip() if isinstance(api_key, str) else str(api_key).strip()


def get_or_create_ai_hub_data(hass: HomeAssistant) -> AIHubData:
    """Get or create AI Hub runtime data."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = AIHubData()
    return hass.data[DOMAIN]


def get_provider_registry(hass: HomeAssistant):
    """Get or create the provider registry for this Home Assistant instance.

    This ensures proper lifecycle management - the registry is cleaned up
    when the integration is unloaded.

    Args:
        hass: Home Assistant instance

    Returns:
        UnifiedProviderRegistry instance
    """
    from .providers import get_registry

    ai_hub_data = get_or_create_ai_hub_data(hass)
    if ai_hub_data.provider_registry is None:
        ai_hub_data.provider_registry = get_registry()
    return ai_hub_data.provider_registry


async def async_setup_entry(hass: HomeAssistant, entry: AIHubConfigEntry) -> bool:
    """Set up AI Hub from a config entry."""

    # Get API key (may be None if not provided)
    api_key = get_configured_api_key(entry)

    # Validate API key by testing API connection only if provided
    if api_key and api_key.strip():
        try:
            from .config_flow_validation import validate_input

            await validate_input(hass, {CONF_API_KEY: api_key})
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to connect to API: %s", err)
            raise ConfigEntryNotReady(f"Failed to connect: {err}") from err
        except ValueError as err:
            reason = str(err)
            if reason == "invalid_auth":
                raise ConfigEntryAuthFailed("Invalid API key") from err
            if reason == "cannot_connect":
                raise ConfigEntryNotReady("API test failed") from err
            if reason.startswith("cannot_connect:"):
                detail = reason.split(":", 1)[1].strip()
                raise ConfigEntryNotReady(f"API test failed: {detail}") from err
            _LOGGER.error("API validation failed: %s", err)
            raise ConfigEntryNotReady(f"API validation failed: {err}") from err
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            _LOGGER.error("API validation failed: %s", err)
            raise ConfigEntryNotReady(f"API validation failed: {err}") from err

    # Initialize runtime data in hass.data
    ai_hub_data = get_or_create_ai_hub_data(hass)
    ai_hub_data.api_key = api_key

    # Store in entry.runtime_data
    entry.runtime_data = api_key

    # Sync auto-generated intent lists before loading local intent config
    from .intents.loader import async_sync_intent_lists
    await async_sync_intent_lists(hass)

    # Set up intent handlers
    from .intents import async_setup_intents
    await async_setup_intents(hass)

    # Set up services
    from .services import async_setup_services
    await async_setup_services(hass, entry)

    # Forward setup to platforms last. If any initialization above fails and Home
    # Assistant retries the config entry, delaying platform setup prevents the
    # entity component from seeing the same entry as already configured.
    _LOGGER.debug("Setting up AI Hub platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Platforms setup completed")

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AIHubConfigEntry) -> bool:
    """Unload a config entry."""
    remaining_entries = [
        config_entry
        for config_entry in hass.config_entries.async_entries(DOMAIN)
        if config_entry.entry_id != entry.entry_id
    ]

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    from .services import async_unload_services
    await async_unload_services(hass, entry.entry_id)

    if not remaining_entries:
        ai_hub_data = get_ai_hub_data(hass)
        if ai_hub_data is not None:
            ai_hub_data.cleanup()
            hass.data.pop(DOMAIN, None)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating configuration from version %s.%s", entry.version, entry.minor_version)

    if entry.version == 1:
        # Migrate from version 1 to version 2
        # Version 2 uses subentries for conversation and ai_task
        new_data = {**entry.data}
        new_options = {**entry.options}

        # Create default subentries
        from homeassistant.helpers import llm

        from .consts import (
            CONF_CHAT_MODEL,
            CONF_LLM_HASS_API,
            CONF_MAX_TOKENS,
            CONF_PROMPT,
            CONF_RECOMMENDED,
            CONF_TEMPERATURE,
            CONF_TOP_P,
            DEFAULT_AI_TASK_NAME,
            DEFAULT_CONVERSATION_NAME,
            LEGACY_AI_TASK_TITLES,
            LEGACY_CONVERSATION_TITLES,
            LLM_API_ASSIST,
            RECOMMENDED_AI_TASK_MAX_TOKENS,
            RECOMMENDED_AI_TASK_MODEL,
            RECOMMENDED_AI_TASK_TEMPERATURE,
            RECOMMENDED_AI_TASK_TOP_P,
            RECOMMENDED_CHAT_MODEL,
            RECOMMENDED_MAX_TOKENS,
            RECOMMENDED_TEMPERATURE,
            RECOMMENDED_TOP_P,
            SUBENTRY_AI_TASK,
            SUBENTRY_CONVERSATION,
        )

        # Create conversation subentry from old options
        conversation_data = {
            CONF_RECOMMENDED: new_options.get(CONF_RECOMMENDED, True),
            CONF_CHAT_MODEL: new_options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL),
            CONF_TEMPERATURE: new_options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE),
            CONF_TOP_P: new_options.get(CONF_TOP_P, RECOMMENDED_TOP_P),
            CONF_MAX_TOKENS: new_options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
            CONF_PROMPT: new_options.get(CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT),
            CONF_LLM_HASS_API: new_options.get(CONF_LLM_HASS_API, [LLM_API_ASSIST]),
        }

        # Create AI task subentry with defaults
        ai_task_data = {
            CONF_RECOMMENDED: True,
            CONF_CHAT_MODEL: RECOMMENDED_AI_TASK_MODEL,
            CONF_TEMPERATURE: RECOMMENDED_AI_TASK_TEMPERATURE,
            CONF_TOP_P: RECOMMENDED_AI_TASK_TOP_P,
            CONF_MAX_TOKENS: RECOMMENDED_AI_TASK_MAX_TOKENS,
        }

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options={},
            version=2,
            minor_version=2,
        )

        # Add subentries
        conversation_subentry = ConfigSubentry(
            data=conversation_data,
            subentry_type=SUBENTRY_CONVERSATION,
            title=DEFAULT_CONVERSATION_NAME,
            unique_id=None,
        )
        hass.config_entries.async_add_subentry(entry, conversation_subentry)

        ai_task_subentry = ConfigSubentry(
            data=ai_task_data,
            subentry_type=SUBENTRY_AI_TASK,
            title=DEFAULT_AI_TASK_NAME,
            unique_id=None,
        )
        hass.config_entries.async_add_subentry(entry, ai_task_subentry)

        _LOGGER.debug("Migration to version %s.%s successful", entry.version, entry.minor_version)

    if entry.version == 2 and entry.minor_version == 1:
        # Migrate from version 2.1 to 2.2
        # Update subentry titles
        from .consts import DEFAULT_AI_TASK_NAME, DEFAULT_CONVERSATION_NAME

        for subentry in entry.subentries.values():
            # Update old titles to new format
            if subentry.subentry_type == SUBENTRY_CONVERSATION:
                if subentry.title in LEGACY_CONVERSATION_TITLES:
                    hass.config_entries.async_update_subentry(
                        entry, subentry.subentry_id, title=DEFAULT_CONVERSATION_NAME
                    )
            elif subentry.subentry_type == SUBENTRY_AI_TASK:
                if subentry.title in LEGACY_AI_TASK_TITLES:
                    hass.config_entries.async_update_subentry(
                        entry, subentry.subentry_id, title=DEFAULT_AI_TASK_NAME
                    )

        hass.config_entries.async_update_entry(
            entry,
            minor_version=2,
        )

        _LOGGER.debug("Migration to version %s.%s successful", entry.version, entry.minor_version)

    return True
