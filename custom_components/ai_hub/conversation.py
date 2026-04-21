"""Conversation agent support for AI Hub integration.

This module implements the ConversationEntity for AI-powered
dialogue interactions, supporting:
- Streaming responses
- Tool calling (Home Assistant control)
- Image understanding (vision models)
- Context-aware conversations
- Three-tier intent processing (local → HA built-in → LLM)"""

from __future__ import annotations

from dataclasses import replace
import logging
from types import SimpleNamespace
from typing import Any, Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import intent, llm
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .consts import CONF_LLM_HASS_API, CONF_PROMPT, DOMAIN, LLM_API_ASSIST, SUBENTRY_CONVERSATION
from .entity import AIHubBaseLLMEntity
from .intents import get_config_cache

_LOGGER = logging.getLogger(__name__)

MATCH_ALL: Literal["*"] = "*"
FALLBACK_AGENT_NAME = "AI Hub Local Assist"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    _LOGGER.debug("Setting up conversation entities, subentries: %s", config_entry.subentries)

    conversation_subentries = [
        subentry
        for subentry in config_entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_CONVERSATION
    ]

    if not conversation_subentries:
        async_add_entities([AIHubLocalConversationAgent(config_entry)])
        _LOGGER.debug(
            "Created fallback local conversation agent for entry: %s",
            config_entry.entry_id,
        )
        return

    _remove_fallback_entity_registry_entry(hass, config_entry)

    for subentry in conversation_subentries:
        _LOGGER.debug("Processing subentry: %s, type: %s", subentry.subentry_id, subentry.subentry_type)

        async_add_entities(
            [AIHubConversationAgent(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )
        _LOGGER.debug("Created conversation agent for subentry: %s", subentry.subentry_id)


def _remove_fallback_entity_registry_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Remove stale fallback entity and device once a formal agent exists."""
    entity_registry = er.async_get(hass)
    fallback_entity_id = entity_registry.async_get_entity_id(
        conversation.DOMAIN,
        DOMAIN,
        f"{config_entry.entry_id}_local_assist",
    )
    if not fallback_entity_id:
        return

    entity_registry.async_remove(fallback_entity_id)
    _LOGGER.debug("Removed stale fallback local conversation entity: %s", fallback_entity_id)

    device_registry = dr.async_get(hass)
    fallback_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{config_entry.entry_id}_local_assist")},
    )
    if fallback_device is not None:
        device_registry.async_remove_device(fallback_device.id)
        _LOGGER.debug(
            "Removed stale fallback local conversation device: %s",
            fallback_device.id,
        )


class AIHubConversationAgent(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    AIHubBaseLLMEntity,
):
    """AI Hub conversation agent."""

    _attr_supports_streaming = True

    def __init__(
        self,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        *,
        warn_on_missing_api_key: bool = True,
        force_control_feature: bool = False,
    ) -> None:
        """Initialize the agent."""
        from .consts import RECOMMENDED_CHAT_MODEL

        super().__init__(
            entry,
            subentry,
            RECOMMENDED_CHAT_MODEL,
            warn_on_missing_api_key=warn_on_missing_api_key,
        )

        # 初始化配置缓存
        self._config_cache = get_config_cache()

        # Formal agents expose control when LLM tools are enabled, while the
        # fallback local agent forces control support explicitly.
        if force_control_feature or self.subentry.data.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process a sentence and return a response.

        处理流程:
        1. 本地意图处理（全局设备控制等 HA 原生不支持的功能）
        2. 如果本地没匹配，交给 Home Assistant 处理（内置意图 + LLM）
        """
        options = self.subentry.data

        local_or_builtin_result = await self._async_handle_local_and_builtin_intents(
            user_input,
            chat_log,
        )
        if local_or_builtin_result is not None:
            return local_or_builtin_result

        return await self._async_handle_llm_message(user_input, chat_log, options)

    async def _async_handle_local_and_builtin_intents(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult | None:
        """Run local intents first, then Home Assistant built-in intents."""

        # ========== 步骤1: 本地意图处理 ==========
        # 只处理 HA 原生不支持的功能（如全局设备控制）

        # 仅对明确的全局控制优先走本地处理，避免覆盖 HA Core
        intent_handler = None
        try:
            from .intents import get_global_intent_handler
            intent_handler = get_global_intent_handler(self.hass)

            if (
                intent_handler
                and self._should_skip_ha_standard_processing(user_input.text)
                and intent_handler.should_handle(user_input.text)
            ):
                _LOGGER.debug("Local intent processing: %s", user_input.text)
                intent_result = await intent_handler.handle(user_input.text, user_input.language)

                if intent_result:
                    speech = intent_result["response"].speech.get("plain", {}).get("speech")
                    if speech:
                        chat_log.async_add_assistant_content_without_tools(
                            conversation.AssistantContent(
                                agent_id=self.entity_id,
                                content=speech,
                            )
                        )
                    _LOGGER.debug("Local intent completed")
                    return conversation.ConversationResult(
                        response=intent_result["response"],
                        conversation_id=user_input.conversation_id
                    )
        except Exception as e:
            _LOGGER.debug("Local intent handling failed: %s", e)

        # ========== 步骤2: 尝试 HA 内置意图处理 ==========
        # timer、shopping list、设备控制等 HA 原生支持的意图
        try:
            from homeassistant.components import conversation as ha_conversation

            ha_chat_log = replace(chat_log, content=chat_log.content.copy())

            _LOGGER.debug("调用 HA 内置 intents 处理: %s", user_input.text)
            ha_response = await ha_conversation.async_handle_intents(
                self.hass,
                user_input,
                ha_chat_log,
            )

            _LOGGER.debug("HA intents 返回结果: %s", ha_response)

            if ha_response is not None:
                response_type = ha_response.response_type
                _LOGGER.debug("HA intents response_type: %s", response_type)

                plain_speech = None
                if ha_response.speech and ha_response.speech.get("plain"):
                    plain_speech = ha_response.speech["plain"].get("speech")

                has_error = hasattr(ha_response, "error") and ha_response.error
                is_error_type = response_type == intent.IntentResponseType.ERROR
                is_no_match = (
                    response_type == intent.IntentResponseType.NO_INTENT_MATCHED
                    if hasattr(intent.IntentResponseType, "NO_INTENT_MATCHED")
                    else False
                )
                response_has_content = bool(plain_speech)
                success_results = getattr(ha_response, "success_results", []) or []
                failed_results = getattr(ha_response, "failed_results", []) or []
                has_explicit_success = bool(success_results)
                has_explicit_failure = bool(failed_results)
                is_empty_action_done = (
                    response_type == intent.IntentResponseType.ACTION_DONE
                    and not has_explicit_success
                    and not has_explicit_failure
                )

                if (
                    not has_error
                    and not is_error_type
                    and not is_no_match
                    and response_has_content
                    and not is_empty_action_done
                ):
                    chat_log.content = ha_chat_log.content
                    if not isinstance(chat_log.content[-1], conversation.AssistantContent):
                        chat_log.async_add_assistant_content_without_tools(
                            conversation.AssistantContent(
                                agent_id=self.entity_id,
                                content=plain_speech,
                            )
                        )
                    _LOGGER.info("HA 内置意图处理成功: %s, type: %s", user_input.text, response_type)
                    return conversation.ConversationResult(
                        response=ha_response,
                        conversation_id=chat_log.conversation_id,
                    )

                if intent_handler and intent_handler.should_handle(user_input.text):
                    _LOGGER.debug("Falling back to local intent processing: %s", user_input.text)
                    intent_result = await intent_handler.handle(user_input.text, user_input.language)
                    if intent_result:
                        speech = intent_result["response"].speech.get("plain", {}).get("speech")
                        if speech:
                            chat_log.async_add_assistant_content_without_tools(
                                conversation.AssistantContent(
                                    agent_id=self.entity_id,
                                    content=speech,
                                )
                            )
                        return conversation.ConversationResult(
                            response=intent_result["response"],
                            conversation_id=user_input.conversation_id,
                        )

                _LOGGER.debug(
                    "HA 内置意图未匹配、返回错误或结果异常(has_error=%s, is_error_type=%s, is_no_match=%s, is_empty_action_done=%s)，交给 LLM 处理",
                    has_error,
                    is_error_type,
                    is_no_match,
                    is_empty_action_done,
                )
            elif intent_handler and intent_handler.should_handle(user_input.text):
                _LOGGER.debug("HA intents returned None, falling back to local intent: %s", user_input.text)
                intent_result = await intent_handler.handle(user_input.text, user_input.language)
                if intent_result:
                    speech = intent_result["response"].speech.get("plain", {}).get("speech")
                    if speech:
                        chat_log.async_add_assistant_content_without_tools(
                            conversation.AssistantContent(
                                agent_id=self.entity_id,
                                content=speech,
                            )
                        )
                    return conversation.ConversationResult(
                        response=intent_result["response"],
                        conversation_id=user_input.conversation_id,
                    )

        except Exception as e:
            _LOGGER.warning("HA 内置意图处理异常: %s", e, exc_info=True)

        return None

    async def _async_handle_llm_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
        options: dict[str, Any],
    ) -> conversation.ConversationResult:
        """Handle the remaining request via LLM."""

        try:
            # High-performance LLM API config retrieval
            llm_apis_value = options.get(CONF_LLM_HASS_API, [])
            if isinstance(llm_apis_value, str):
                llm_apis = [llm_apis_value] if llm_apis_value.strip() else []
            elif isinstance(llm_apis_value, (list, tuple, set)):
                llm_apis = [item for item in llm_apis_value if isinstance(item, str) and item.strip()]
            else:
                llm_apis = []

            valid_api_ids = {api.id for api in llm.async_get_apis(self.hass)}
            llm_apis = [api_id for api_id in llm_apis if api_id in valid_api_ids]

            if not llm_apis:
                _LOGGER.warning("LLM API config not found, checking LLM_API_ASSIST")
                # Try using the default LLM API ASSIST
                try:
                    default_llm_api = LLM_API_ASSIST
                    llm_apis = [default_llm_api]
                    _LOGGER.debug("Using default LLM API")
                except Exception as err:
                    _LOGGER.error("LLM_API_ASSIST retrieval failed: %s", err)
                    empty_response = intent.IntentResponse(language=user_input.language)
                    error_msg = self._config_cache.get_error_message("llm_config_error")
                    empty_response.async_set_speech(error_msg)
                    return conversation.ConversationResult(
                        response=empty_response,
                        conversation_id=user_input.conversation_id
                    )

            # Provide LLM data (tools, home info, etc.)
            user_prompt = options.get(CONF_PROMPT, "")
            _LOGGER.debug(
                "Preparing LLM data for '%s' with APIs=%s",
                user_input.text,
                llm_apis,
            )
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                llm_apis,
                user_prompt,
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            _LOGGER.error("LLM conversation error: %s", err)
            return err.as_conversation_result()

        # Process the chat log with AI Hub
        # Loop to handle tool calls: model may call tools, then we need to call again with results
        loop_count = 0
        while True:
            loop_count += 1
            _LOGGER.debug("LLM processing loop %d", loop_count)

            # Check chat_log status
            if hasattr(chat_log, 'tool_calls') and chat_log.tool_calls:
                _LOGGER.debug("LLM initiated %d tool calls", len(chat_log.tool_calls))
            else:
                _LOGGER.debug("LLM did not initiate tool calls")

            await self._async_handle_chat_log(chat_log)

            # Check if there are tool call results
            if hasattr(chat_log, 'unresponded_tool_results') and chat_log.unresponded_tool_results:
                _LOGGER.debug("Found unprocessed tool call results")
            else:
                _LOGGER.debug("No more tool calls, processing completed")

            # If there are no unresponded tool results, continue the loop
            if not chat_log.unresponded_tool_results:
                break

        # Apply markdown filtering to the final assistant message before returning
        from .markdown_filter import filter_markdown_content
        if chat_log.content and len(chat_log.content) > 0:
            last_content = chat_log.content[-1]
            if last_content.role == "assistant" and last_content.content:
                original_content = str(last_content.content)
                filtered_content = filter_markdown_content(original_content)
                if filtered_content != original_content:
                    _LOGGER.debug(
                        "Filtered markdown from chat_log before returning: '%s' -> '%s'",
                        original_content[:50] if len(original_content) > 50 else original_content,
                        filtered_content[:50] if len(filtered_content) > 50 else filtered_content
                    )
                    chat_log.content[-1] = replace(last_content, content=filtered_content)

        # Return result from chat log
        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    def _should_skip_ha_standard_processing(self, text: str) -> bool:
        """Check whether to skip Home Assistant standard processing and go directly to local intent

        Only very explicit local intents skip HA standard processing, such as:
        - "Turn on all devices"
        - "Turn off all lights"
        """
        try:
            config = self._config_cache.get_config()
            if not config:
                return False

            # Get config from local_intents.GlobalDeviceControl
            local_intents = config.get('local_intents', {})
            global_config = local_intents.get('GlobalDeviceControl', {})
            if not global_config:
                return False

            text_lower = text.lower().strip()

            # Check global keywords
            global_keywords = global_config.get('global_keywords', [])
            has_global = any(keyword in text_lower for keyword in global_keywords)

            # Check explicit on/off keywords
            on_keywords = global_config.get('on_keywords', [])
            off_keywords = global_config.get('off_keywords', [])
            has_action = any(keyword in text_lower for keyword in on_keywords + off_keywords)

            # Check if contains parameter control keywords (brightness, volume, etc.)
            param_keywords = global_config.get('param_keywords', [])
            brightness_keywords = global_config.get('brightness_keywords', [])
            volume_keywords = global_config.get('volume_keywords', [])
            color_keywords = global_config.get('color_keywords', [])
            temperature_keywords = global_config.get('temperature_keywords', [])

            has_param_control = any(keyword in text_lower for keyword in
                                    param_keywords + brightness_keywords + volume_keywords +
                                    color_keywords + temperature_keywords)

            # Skip HA processing: only explicit global commands go to local processing
            # Requires both global keywords and explicit action or parameter control
            should_skip = has_global and (has_action or has_param_control)

            if should_skip:
                _LOGGER.debug(
                    "Skipping HA processing: '%s' (global=%s, action=%s, param=%s)",
                    text, has_global, has_action, has_param_control
                )

            return should_skip

        except Exception as err:
            _LOGGER.debug("Error checking whether to skip HA processing: %s", err)
            return False


class AIHubLocalConversationAgent(AIHubConversationAgent):
    """Fallback local-only conversation agent shown when no formal agent exists."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the fallback agent."""
        from .consts import RECOMMENDED_CHAT_MODEL

        fallback_subentry = SimpleNamespace(
            subentry_id=f"{entry.entry_id}_local_assist",
            title=FALLBACK_AGENT_NAME,
            data={},
            subentry_type=SUBENTRY_CONVERSATION,
        )
        super().__init__(
            entry,
            fallback_subentry,
            warn_on_missing_api_key=False,
            force_control_feature=True,
        )

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process a sentence using only local and built-in intents."""
        local_or_builtin_result = await self._async_handle_local_and_builtin_intents(
            user_input,
            chat_log,
        )
        if local_or_builtin_result is not None:
            return local_or_builtin_result

        empty_response = intent.IntentResponse(language=user_input.language)
        if (user_input.language or "").lower().startswith("en"):
            empty_response.async_set_speech("Current mode only supports local intents")
        else:
            empty_response.async_set_speech("当前模式仅支持本地意图")
        return conversation.ConversationResult(
            response=empty_response,
            conversation_id=user_input.conversation_id,
        )
