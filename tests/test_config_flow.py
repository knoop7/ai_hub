"""Tests for the AI Hub config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("voluptuous")

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from custom_components.ai_hub.config_flow import (
    AIHubConfigFlow,
    AIHubSubentryFlowHandler,
    AIHubTranslationFlowHandler,
    STEP_USER_DATA_SCHEMA,
    validate_input,
)
from custom_components.ai_hub.const import (
    CONF_CHAT_MODEL,
    CONF_LLM_HASS_API,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_TTS_NAME,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_TEMPERATURE,
)


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=[])
    return hass


@pytest.fixture
def flow(mock_hass):
    """Create a config flow instance."""
    flow = AIHubConfigFlow(mock_hass)
    flow.hass = mock_hass
    return flow


class TestValidateInput:
    """Tests for validate_input function."""

    @pytest.mark.asyncio
    async def test_valid_api_key(self, mock_hass):
        """Test validation with valid API key."""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post.return_value.__aenter__.return_value = mock_response

            data = {CONF_API_KEY: "valid_key"}
            await validate_input(mock_hass, data)
            # Should not raise exception

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, mock_hass):
        """Test validation with invalid API key."""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_post.return_value.__aenter__.return_value = mock_response

            data = {CONF_API_KEY: "invalid_key"}
            with pytest.raises(ValueError, match="invalid_auth"):
                await validate_input(mock_hass, data)

    @pytest.mark.asyncio
    async def test_connection_error(self, mock_hass):
        """Test validation with connection error."""
        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.side_effect = Exception("Connection error")

            data = {CONF_API_KEY: "test_key"}
            with pytest.raises(Exception, match="Connection error"):
                await validate_input(mock_hass, data)


class TestAIHubConfigFlow:
    """Tests for AIHubConfigFlow."""

    def test_form_show(self, flow):
        """Test the initial form is shown."""
        result = flow.async_step_user(None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["data_schema"] == STEP_USER_DATA_SCHEMA

    @pytest.mark.asyncio
    async def test_form_success(self, flow, mock_hass):
        """Test successful form submission."""
        with patch.object(flow, "__class__") as mock_class:
            mock_class.VERSION = 1

            with patch("custom_components.ai_hub.config_flow.validate_input") as mock_validate:
                user_input = {
                    CONF_API_KEY: "test_api_key",
                }

                with patch.object(flow, "async_create_entry") as mock_create:
                    result = flow.async_step_user(user_input)

                    assert result["type"] == "create_entry"
                    assert mock_create.called

    @pytest.mark.asyncio
    async def test_form_invalid_auth(self, flow):
        """Test form submission with invalid auth."""
        with patch("custom_components.ai_hub.config_flow.validate_input") as mock_validate:
            mock_validate.side_effect = ValueError("Invalid API key")

            user_input = {CONF_API_KEY: "invalid_key"}

            result = flow.async_step_user(user_input)

            assert result["type"] == "form"
            assert result["errors"] == {"base": "invalid_auth"}

    @pytest.mark.asyncio
    async def test_form_cannot_connect(self, flow):
        """Test form submission with connection error."""
        with patch("custom_components.ai_hub.config_flow.validate_input") as mock_validate:
            import aiohttp
            mock_validate.side_effect = aiohttp.ClientError("Cannot connect")

            user_input = {CONF_API_KEY: "test_key"}

            result = flow.async_step_user(user_input)

            assert result["type"] == "form"
            assert result["errors"] == {"base": "cannot_connect"}

    def test_get_supported_subentry_types(self, flow):
        """Test getting supported subentry types."""
        subentry_types = AIHubConfigFlow.async_get_supported_subentry_types(None)

        assert "conversation" in subentry_types
        assert "ai_task_data" in subentry_types
        assert "tts" in subentry_types
        assert "stt" in subentry_types
        assert "translation" in subentry_types

        assert subentry_types["conversation"] == AIHubSubentryFlowHandler
        assert subentry_types["translation"] == AIHubTranslationFlowHandler


class TestAIHubSubentryFlowHandler:
    """Tests for AIHubSubentryFlowHandler."""

    @pytest.fixture
    def subentry_flow(self, mock_hass):
        """Create a subentry flow instance."""
        config_entry = MagicMock(spec=config_entries.ConfigEntry)
        config_entry.subentries = {}

        flow = AIHubSubentryFlowHandler(mock_hass, config_entry, None)
        flow.hass = mock_hass
        flow.source = "user"
        flow._subentry_type = "conversation"
        return flow

    def test_init_form_show(self, subentry_flow):
        """Test the initial form is shown."""
        result = subentry_flow.async_step_init(None)

        assert result["type"] == "form"
        assert result["step_id"] == "init"
        assert "data_schema" in result

    def test_recommended_mode_toggle(self, subentry_flow):
        """Test recommended mode toggling."""
        user_input = {
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Custom prompt",
            CONF_CHAT_MODEL: "custom_model",
            CONF_TEMPERATURE: 0.5,
        }

        # Set initial recommended mode
        subentry_flow.last_rendered_recommended = True
        subentry_flow.options = RECOMMENDED_CONVERSATION_OPTIONS.copy()

        result = subentry_flow.async_step_init(user_input)

        # Should re-render form with advanced options
        assert result["type"] == "form"

    def test_conversation_subentry_with_recommended_mode(self, subentry_flow):
        """Test conversation subentry in recommended mode."""
        subentry_flow._subentry_type = "conversation"
        subentry_flow.options = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        subentry_flow.last_rendered_recommended = True

        result = subentry_flow.async_step_init({CONF_RECOMMENDED: True})

        assert result["type"] == "form"

    def test_tts_subentry(self, subentry_flow):
        """Test TTS subentry."""
        subentry_flow._subentry_type = "tts"
        subentry_flow.options = {"recommended": True}

        result = subentry_flow.async_step_init({CONF_RECOMMENDED: True})

        assert result["type"] == "form"

class TestAIHubTranslationFlowHandler:
    """Tests for AIHubTranslationFlowHandler."""

    @pytest.fixture
    def translation_flow(self, mock_hass):
        """Create a Translation subentry flow instance."""
        config_entry = MagicMock(spec=config_entries.ConfigEntry)
        config_entry.subentries = {}

        flow = AIHubTranslationFlowHandler(mock_hass, config_entry, None)
        flow.hass = mock_hass
        flow.source = "user"
        return flow

    def test_init_create_entry(self, translation_flow):
        """Test that translation subentry is created immediately."""
        with patch.object(translation_flow, "async_create_entry") as mock_create:
            result = translation_flow.async_step_user(None)

            assert result["type"] == "create_entry"
            assert mock_create.called

    def test_reconfigure_not_supported(self, translation_flow):
        """Test that reconfigure is not supported."""
        translation_flow.source = "reconfigure"

        result = translation_flow.async_step_user(None)

        assert result["type"] == "abort"
        assert result["reason"] == "translation_no_reconfigure"
