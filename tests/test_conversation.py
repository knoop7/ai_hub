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
from custom_components.ai_hub.entity import AIHubBaseLLMEntity
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
from custom_components.ai_hub.providers.openai_compatible import OpenAICompatibleProvider
from custom_components.ai_hub.providers.ollama_compatible import OllamaCompatibleProvider
from custom_components.ai_hub.http import resolve_provider_name
from custom_components.ai_hub.intents.response_utils import create_intent_result


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


class TestLocalIntentResponse:
    """Tests for local intent structured responses."""

    def test_create_intent_result_can_include_success_results(self):
        """Local intent responses should preserve structured success targets."""
        result = create_intent_result(
            "zh-CN",
            "已打开书房灯",
            success_results=[
                {"type": "entity", "name": "书房灯", "id": "light.study"}
            ],
        )

        response = result["response"]
        assert response.data["success"] == [
            {"type": "entity", "name": "书房灯", "id": "light.study"}
        ]


class TestEntityStreamingSelection:
    """Tests for provider streaming selection."""

    @pytest.mark.asyncio
    async def test_openai_compatible_with_tools_uses_streaming(self):
        """OpenAI-compatible requests should keep streaming enabled with tools."""
        entity = object.__new__(AIHubBaseLLMEntity)

        entity.subentry = MagicMock()
        entity.subentry.data = {
            "chat_url": "https://example.com/v1",
            "llm_provider": "openai_compatible",
        }
        entity.default_model = "test-model"
        entity._api_key = "test-key"
        entity.entity_id = "conversation.test_agent"
        entity.hass = MagicMock()

        entity._get_model_config = MagicMock(
            return_value={
                "model": "test-model",
                "temperature": 0.3,
                "max_tokens": 250,
                "enable_thinking": False,
            }
        )
        entity._async_convert_chat_log_to_messages = AsyncMock(
            return_value=[{"role": "user", "content": "打开客厅灯"}]
        )
        entity._format_tool = MagicMock(return_value={"type": "function"})
        entity._async_run_provider_stream = AsyncMock()
        entity._async_run_provider_completion = AsyncMock()

        provider = MagicMock()
        provider.supports_tools.return_value = True
        provider.config = MagicMock(timeout=60)

        chat_log = MagicMock()
        chat_log.llm_api = MagicMock()
        chat_log.llm_api.custom_serializer = None
        chat_log.llm_api.tools = [MagicMock()]

        with patch("custom_components.ai_hub.entity.create_provider", return_value=provider):
            with patch("custom_components.ai_hub.entity.resolve_provider_name", return_value="openai_compatible"):
                await entity._async_handle_chat_log(chat_log)

        entity._async_run_provider_stream.assert_awaited_once()
        entity._async_run_provider_completion.assert_not_awaited()


class TestProviderStreamRobustness:
    """Tests for provider streaming edge cases."""

    @pytest.mark.asyncio
    async def test_openai_stream_ignores_empty_choices_chunks(self):
        """Streaming should skip SSE chunks without choices instead of crashing."""
        provider = OpenAICompatibleProvider(
            {
                "api_key": "test-key",
                "model": "test-model",
                "base_url": "https://example.com/v1",
            }
        )

        async def _fake_stream(*args, **kwargs):
            yield 'data: {"choices": []}\n'
            yield 'data: {"choices": [{"delta": {"content": "你好"}}]}\n'
            yield 'data: [DONE]\n'

        with patch(
            "custom_components.ai_hub.providers.openai_compatible.async_stream_response_text",
            _fake_stream,
        ):
            chunks = [
                chunk
                async for chunk in provider.complete_stream(
                    [MagicMock(role="user", content="hi", tool_calls=None, tool_call_id=None, tool_name=None)]
                )
            ]

        assert chunks == ["你好"]

    @pytest.mark.asyncio
    async def test_ollama_stream_supports_json_line_format(self):
        """Ollama-compatible streaming should support Ollama JSON lines."""
        provider = OllamaCompatibleProvider(
            {
                "api_key": "test-key",
                "model": "gemma4:26b-a4b-it-q4_K_M",
                "base_url": "http://localhost:11434/api/chat",
            }
        )

        async def _fake_stream(*args, **kwargs):
            yield '{"message":{"role":"assistant","content":"你"},"done":false}\n'
            yield '{"message":{"role":"assistant","content":"好"},"done":false}\n'
            yield '{"message":{"role":"assistant","content":""},"done":true}\n'

        with patch(
            "custom_components.ai_hub.providers.ollama_compatible.async_stream_response_text",
            _fake_stream,
        ):
            chunks = [
                chunk
                async for chunk in provider.complete_stream(
                    [MagicMock(role="user", content="hi", tool_calls=None, tool_call_id=None, tool_name=None)]
                )
            ]

        assert chunks == ["你", "好"]


class TestProviderResolution:
    """Tests for provider auto-detection."""

    def test_resolve_provider_name_detects_ollama_api_chat(self):
        """Ollama /api/chat URLs should resolve to the dedicated provider."""
        assert resolve_provider_name("http://localhost:11434/api/chat") == "ollama_compatible"

    @pytest.mark.asyncio
    async def test_anthropic_compatible_with_tools_uses_streaming(self):
        """Anthropic-compatible requests should keep streaming enabled with tools."""
        entity = object.__new__(AIHubBaseLLMEntity)

        entity.subentry = MagicMock()
        entity.subentry.data = {
            "chat_url": "https://example.com/v1/messages",
            "llm_provider": "anthropic_compatible",
        }
        entity.default_model = "test-model"
        entity._api_key = "test-key"
        entity.entity_id = "conversation.test_agent"
        entity.hass = MagicMock()

        entity._get_model_config = MagicMock(
            return_value={
                "model": "test-model",
                "temperature": 0.3,
                "max_tokens": 250,
                "enable_thinking": False,
            }
        )
        entity._async_convert_chat_log_to_messages = AsyncMock(
            return_value=[{"role": "user", "content": "打开客厅灯"}]
        )
        entity._format_tool = MagicMock(return_value={"type": "function"})
        entity._async_run_provider_stream = AsyncMock()
        entity._async_run_provider_completion = AsyncMock()

        provider = MagicMock()
        provider.supports_tools.return_value = True
        provider.config = MagicMock(timeout=60)

        chat_log = MagicMock()
        chat_log.llm_api = MagicMock()
        chat_log.llm_api.custom_serializer = None
        chat_log.llm_api.tools = [MagicMock()]

        with patch("custom_components.ai_hub.entity.create_provider", return_value=provider):
            with patch("custom_components.ai_hub.entity.resolve_provider_name", return_value="anthropic_compatible"):
                await entity._async_handle_chat_log(chat_log)

        entity._async_run_provider_stream.assert_awaited_once()
        entity._async_run_provider_completion.assert_not_awaited()
