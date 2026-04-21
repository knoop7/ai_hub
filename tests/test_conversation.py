"""Tests for the AI Hub conversation agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("homeassistant")

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
from custom_components.ai_hub.intents.config_cache import ConfigCache


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

    @pytest.mark.asyncio
    async def test_query_like_input_rejects_action_done_without_explicit_outcome(self, mock_hass, mock_config_entry):
        """Query-like input should not accept speech-only action_done results from HA."""
        subentry = list(mock_config_entry.subentries.values())[0]
        agent = AIHubConversationAgent(mock_config_entry, subentry)
        agent.hass = mock_hass

        user_input = MagicMock()
        user_input.text = "有多少个开关是开着的"
        user_input.language = "zh-CN"
        user_input.conversation_id = "conv-query-1"

        chat_log = MagicMock()
        chat_log.content = []

        ha_response = MagicMock()
        ha_response.response_type = conversation.intent.IntentResponseType.ACTION_DONE
        ha_response.speech = {"plain": {"speech": "已打开3个设备"}}
        ha_response.error = None
        ha_response.data = {"targets": [], "success": [], "failed": []}

        with patch("homeassistant.components.conversation.async_handle_intents", AsyncMock(return_value=ha_response)):
            with patch("custom_components.ai_hub.conversation.get_global_intent_handler", return_value=None, create=True):
                result = await agent._async_handle_local_and_builtin_intents(user_input, chat_log)

        assert result is None

    @pytest.mark.asyncio
    async def test_action_done_accepts_explicit_success_from_response_data(self, mock_hass, mock_config_entry):
        """Structured action_done results should still be accepted when HA reports success targets."""
        subentry = list(mock_config_entry.subentries.values())[0]
        agent = AIHubConversationAgent(mock_config_entry, subentry)
        agent.hass = mock_hass

        user_input = MagicMock()
        user_input.text = "打开客厅灯"
        user_input.language = "zh-CN"
        user_input.conversation_id = "conv-action-1"

        chat_log = MagicMock()
        chat_log.content = []
        chat_log.conversation_id = "conv-action-1"
        chat_log.async_add_assistant_content_without_tools = MagicMock()

        ha_response = MagicMock()
        ha_response.response_type = conversation.intent.IntentResponseType.ACTION_DONE
        ha_response.speech = {"plain": {"speech": "已打开客厅灯"}}
        ha_response.error = None
        ha_response.data = {
            "targets": [{"type": "area", "name": "客厅", "id": "living_room"}],
            "success": [{"type": "entity", "name": "客厅灯", "id": "light.living_room"}],
            "failed": [],
        }

        with patch("homeassistant.components.conversation.async_handle_intents", AsyncMock(return_value=ha_response)):
            with patch("custom_components.ai_hub.conversation.get_global_intent_handler", return_value=None, create=True):
                result = await agent._async_handle_local_and_builtin_intents(user_input, chat_log)

        assert result is not None
        assert result.response is ha_response

    @pytest.mark.asyncio
    async def test_query_answer_follow_up_prompt_falls_through_to_llm(self, mock_hass, mock_config_entry):
        """HA clarification prompts should not intercept follow-up turns."""
        subentry = list(mock_config_entry.subentries.values())[0]
        agent = AIHubConversationAgent(mock_config_entry, subentry)
        agent.hass = mock_hass

        user_input = MagicMock()
        user_input.text = "打开"
        user_input.language = "zh-CN"
        user_input.conversation_id = "conv-follow-up-1"

        chat_log = MagicMock()
        chat_log.content = []
        chat_log.conversation_id = "conv-follow-up-1"

        ha_response = MagicMock()
        ha_response.response_type = conversation.intent.IntentResponseType.QUERY_ANSWER
        ha_response.speech = {"plain": {"speech": "您想打开什么？"}}
        ha_response.error = None
        ha_response.data = {"targets": [], "success": [], "failed": []}

        def _fake_replace(_chat_log, **changes):
            replaced = MagicMock()
            replaced.content = changes.get("content", [])
            replaced.continue_conversation = True
            return replaced

        with patch("custom_components.ai_hub.conversation.replace", side_effect=_fake_replace):
            with patch("homeassistant.components.conversation.async_handle_intents", AsyncMock(return_value=ha_response)):
                with patch("custom_components.ai_hub.conversation.get_global_intent_handler", return_value=None, create=True):
                    result = await agent._async_handle_local_and_builtin_intents(user_input, chat_log)

        assert result is None

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

    def test_should_skip_ha_standard_processing(self, mock_hass, mock_config_entry):
        """Test that only explicit global commands bypass HA Core first."""
        subentry = list(mock_config_entry.subentries.values())[0]
        agent = AIHubConversationAgent(mock_config_entry, subentry)

        agent._config_cache = MagicMock()
        agent._config_cache.get_config.return_value = {
            "local_intents": {
                "GlobalDeviceControl": {
                    "global_keywords": ["所有", "全部", "全屋"],
                    "on_keywords": ["打开", "开启"],
                    "off_keywords": ["关闭", "关掉"],
                    "param_keywords": ["调到", "设置"],
                    "brightness_keywords": ["亮度"],
                    "volume_keywords": ["音量"],
                    "color_keywords": ["颜色"],
                    "temperature_keywords": ["温度"],
                }
            }
        }

        # Test global command with action
        assert agent._should_skip_ha_standard_processing("打开所有灯") is True

        # Test global command with parameter
        assert agent._should_skip_ha_standard_processing("所有灯调到50%亮度") is True

        # Non-global commands should let HA Core try first
        assert agent._should_skip_ha_standard_processing("打开客厅的灯") is False
        assert agent._should_skip_ha_standard_processing("把卧室灯调成暖白") is False

    def test_is_all_device_operation(self, mock_hass, mock_config_entry):
        """Test all device operation detection."""
        subentry = list(mock_config_entry.subentries.values())[0]
        agent = AIHubConversationAgent(mock_config_entry, subentry)

        assert agent._is_all_device_operation({"text": "打开所有设备"}) is True
        assert agent._is_all_device_operation({"text": "关闭全部灯"}) is True
        assert agent._is_all_device_operation({"text": "打开客厅灯"}) is False


class TestIntentConfigCache:
    """Tests for intent config cache compatibility."""

    def test_reads_merged_local_intents_structure(self):
        """Config cache should read AI Hub merged config directly."""
        cache = ConfigCache()
        cache.get_config = lambda force_reload=False: {
            "local_intents": {
                "GlobalDeviceControl": {
                    "global_keywords": ["所有", "全屋"],
                }
            },
            "responses": {"ok": "ok"},
            "expansion_rules": {"turn": "打开|关闭"},
        }

        assert cache.get_global_keywords() == ["所有", "全屋"]
        assert "打开" in cache.get_local_features()

    def test_keeps_backward_compatibility_with_legacy_nested_structure(self):
        """Config cache should still support legacy nested config."""
        cache = ConfigCache()
        cache.get_config = lambda force_reload=False: {
            "intents": {
                "ai_hub": {
                    "local_intents": {
                        "GlobalDeviceControl": {
                            "global_keywords": ["全部"],
                        }
                    },
                    "defaults": {
                        "error_messages": {
                            "llm_config_error": "配置错误",
                        }
                    },
                }
            }
        }

        assert cache.get_global_keywords() == ["全部"]
        assert cache.get_error_message("llm_config_error") == "配置错误"
