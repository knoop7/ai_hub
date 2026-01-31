"""Tests for the AI Hub conversation agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from custom_components.ai_hub.conversation import AIHubConversationAgent
from custom_components.ai_hub.const import (
    CONF_CHAT_MODEL,
    CONF_LLM_HASS_API,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_TEMPERATURE,
    DEFAULT_CONVERSATION_NAME,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_TEMPERATURE,
)


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    subentry = ConfigSubentry(
        subentry_type="conversation",
        title=DEFAULT_CONVERSATION_NAME,
        data={
            CONF_RECOMMENDED: True,
            CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
            CONF_TEMPERATURE: RECOMMENDED_TEMPERATURE,
            CONF_PROMPT: llm.DEFAULT_INSTRUCTIONS_PROMPT,
            CONF_LLM_HASS_API: llm.LLM_API_ASSIST,
        },
        unique_id=None,
    )

    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.runtime_data = "test_api_key"
    entry.subentries = {"conversation_subentry": subentry}

    return entry


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.config.language = "zh-CN"

    # Mock the config registry
    hass.config_entries.async_get_entry = AsyncMock(return_value=None)

    return hass


class TestAIHubConversationAgent:
    """Tests for AIHubConversationAgent."""

    def test_init(self, mock_hass, mock_config_entry):
        """Test conversation agent initialization."""
        subentry = list(mock_config_entry.subentries.values())[0]

        agent = AIHubConversationAgent(mock_config_entry, subentry)

        assert agent._attr_supported_languages == "*"
        assert agent._attr_supports_streaming is True
        assert agent.entity_id == "conversation.ai_hub_ai_hub_conversation"

    def test_supported_languages(self, mock_hass, mock_config_entry):
        """Test supported languages property."""
        subentry = list(mock_config_entry.subentries.values())[0]
        agent = AIHubConversationAgent(mock_config_entry, subentry)

        assert agent.supported_languages == "*"

    def test_recommended_mode_enabled(self, mock_hass, mock_config_entry):
        """Test that recommended mode enables LLM Hass API."""
        subentry = list(mock_config_entry.subentries.values())[0]
        agent = AIHubConversationAgent(mock_config_entry, subentry)

        assert conversation.ConversationEntityFeature.CONTROL in agent._attr_supported_features

    def test_recommended_mode_disabled(self, mock_hass, mock_config_entry):
        """Test that disabling recommended mode disables LLM Hass API."""
        subentry_data = list(mock_config_entry.subentries.values())[0].data.copy()
        subentry_data[CONF_RECOMMENDED] = False
        subentry_data[CONF_LLM_HASS_API] = []

        subentry = ConfigSubentry(
            subentry_type="conversation",
            title=DEFAULT_CONVERSATION_NAME,
            data=subentry_data,
            unique_id=None,
        )

        agent = AIHubConversationAgent(mock_config_entry, subentry)

        assert conversation.ConversationEntityFeature.CONTROL not in agent._attr_supported_features

    @pytest.mark.asyncio
    async def test_async_added_to_hass(self, mock_hass, mock_config_entry):
        """Test entity added to hass."""
        subentry = list(mock_config_entry.subentries.values())[0]
        agent = AIHubConversationAgent(mock_config_entry, subentry)
        agent.hass = mock_hass
        agent.entry = mock_config_entry

        with patch.object(conversation, "async_set_agent"):
            await agent.async_added_to_hass()

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass(self, mock_hass, mock_config_entry):
        """Test entity removed from hass."""
        subentry = list(mock_config_entry.subentries.values())[0]
        agent = AIHubConversationAgent(mock_config_entry, subentry)
        agent.hass = mock_hass
        agent.entry = mock_config_entry

        with patch.object(conversation, "async_unset_agent"):
            await agent.async_will_remove_from_hass()

    def test_extract_automation_description(self, mock_hass, mock_config_entry):
        """Test automation description extraction."""
        subentry = list(mock_config_entry.subentries.values())[0]
        agent = AIHubConversationAgent(mock_config_entry, subentry)

        # Test with automation keyword
        result = agent._extract_automation_description("帮我创建一个自动化，每天早上8点打开灯")
        assert result == "，每天早上8点打开灯"

        # Test without automation keyword
        result = agent._extract_automation_description("打开客厅的灯")
        assert result is None

        # Test with short description
        result = agent._extract_automation_description("创建自动化")
        assert result is None

    def test_should_skip_ha_processing(self, mock_hass, mock_config_entry):
        """Test HA processing skip logic."""
        subentry = list(mock_config_entry.subentries.values())[0]
        agent = AIHubConversationAgent(mock_config_entry, subentry)

        # Test global command with action
        assert agent._should_skip_ha_processing("打开所有灯") is True

        # Test global command with parameter
        assert agent._should_skip_ha_processing("所有灯调到50%亮度") is True

        # Test normal command
        assert agent._should_skip_ha_processing("打开客厅的灯") is False

    def test_is_all_device_operation(self, mock_hass, mock_config_entry):
        """Test all device operation detection."""
        subentry = list(mock_config_entry.subentries.values())[0]
        agent = AIHubConversationAgent(mock_config_entry, subentry)

        assert agent._is_all_device_operation({"text": "打开所有设备"}) is True
        assert agent._is_all_device_operation({"text": "关闭全部灯"}) is True
        assert agent._is_all_device_operation({"text": "打开客厅灯"}) is False