"""Conversation support for AI Hub."""

from __future__ import annotations

import logging
from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import intent

from .const import CONF_LLM_HASS_API, CONF_PROMPT, DOMAIN
from .entity import AIHubBaseLLMEntity
from .intents import extract_intent_info, get_intent_handler

_LOGGER = logging.getLogger(__name__)

MATCH_ALL = "*"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    _LOGGER.info("Setting up conversation entities, subentries: %s", config_entry.subentries)

    if not config_entry.subentries:
        _LOGGER.warning("No subentries found in config entry")
        return

    for subentry in config_entry.subentries.values():
        _LOGGER.info("Processing subentry: %s, type: %s", subentry.subentry_id, subentry.subentry_type)
        if subentry.subentry_type != "conversation":
            continue

        async_add_entities(
            [AIHubConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )
        _LOGGER.info("Created conversation entity for subentry: %s", subentry.subentry_id)


class AIHubConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    AIHubBaseLLMEntity,
):
    """AI Hub conversation agent."""

    _attr_supports_streaming = True

    def __init__(
        self, entry: ConfigEntry, subentry: ConfigSubentry
    ) -> None:
        """Initialize the agent."""
        from .const import RECOMMENDED_CHAT_MODEL

        super().__init__(entry, subentry, RECOMMENDED_CHAT_MODEL)

        # Enable control feature if LLM Hass API is configured
        if self.subentry.data.get(CONF_LLM_HASS_API):
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

        Processing order:
        1. Automation request handling
        2. Enhanced intent matching (this integration's custom intents)
        3. Fallback to Home Assistant native intent processing
        4. LLM-powered conversation processing
        """
        options = self.subentry.data

        # 检查是否是自动化创建请求
        try:
            automation_result = await self._handle_automation_request(user_input)
            if automation_result:
                return automation_result
        except Exception as e:
            _LOGGER.debug("Automation handling failed: %s", e)

        # 步骤2: 使用增强意图处理系统
        # 优先尝试我们的自定义意图，这些意图提供更丰富的中文支持
        try:
            intent_info = await extract_intent_info(user_input.text, self.hass)
            if intent_info:
                _LOGGER.debug("Enhanced intent detected: %s", intent_info)

                handler = get_intent_handler(self.hass)
                result = await handler.handle_intent(intent_info)

                if result.get("success"):
                    # 增强意图处理成功，直接返回结果
                    intent_response = intent.IntentResponse(language=user_input.language)
                    intent_response.async_set_speech(result.get("message", "操作完成"))

                    return conversation.ConversationResult(
                        response=intent_response,
                        conversation_id=user_input.conversation_id
                    )
                else:
                    _LOGGER.debug("Enhanced intent handling failed: %s", result.get("error"))
                    # 增强意图处理失败，继续尝试Home Assistant原生
            else:
                _LOGGER.debug("No enhanced intent matched, trying Home Assistant native intents")

        except Exception as e:
            _LOGGER.debug("Enhanced intent processing failed: %s", e)

        # 步骤3: 回退到Home Assistant原生意图处理
        # 如果我们的增强意图没有匹配到，尝试使用Home Assistant内置的意图系统
        try:
            _LOGGER.debug("Attempting Home Assistant native intent processing")

            # 使用Home Assistant的原生意图识别和处理系统
            from homeassistant.helpers import intent as ha_intent
            from homeassistant.components.intent import IntentResponse

            # 尝试识别和处理意图
            try:
                # 使用Home Assistant的意图识别器
                intent_type = await ha_intent.async_match_intent(self.hass, user_input.text, user_input.language)

                if intent_type:
                    _LOGGER.debug("Home Assistant matched intent: %s", intent_type.intent_type)

                    # 创建意图对象
                    ha_intent_obj = ha_intent.Intent(
                        intent_type.intent_type,
                        slots=intent_type.slots or {}
                    )

                    # 处理意图
                    result = await ha_intent.async_handle(
                        self.hass,
                        "conversation",  # 使用conversation作为平台
                        ha_intent_obj,
                        user_input.text,
                        user_input.language or "zh-CN"
                    )

                    # 如果有结果，创建响应
                    if result and hasattr(result, 'response') and result.response:
                        speech = result.response.speech.get("plain", {}).get("speech", "")
                        if speech:
                            intent_response = IntentResponse(language=user_input.language or "zh-CN")
                            intent_response.async_set_speech(speech)

                            _LOGGER.debug("Home Assistant native intent processing successful")
                            return conversation.ConversationResult(
                                response=intent_response,
                                conversation_id=user_input.conversation_id
                            )

                _LOGGER.debug("Home Assistant native intent processing returned no result")

            except ha_intent.UnknownIntent:
                _LOGGER.debug("No matching Home Assistant native intent found")
            except Exception as intent_error:
                _LOGGER.debug("Home Assistant native intent processing error: %s", intent_error)

        except Exception as e:
            _LOGGER.debug("Failed to setup Home Assistant native intent processing: %s", e)

        # 步骤4: LLM处理 (如果所有意图处理都失败)

        try:
            # Provide LLM data (tools, home info, etc.)
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get(CONF_LLM_HASS_API),
                options.get(CONF_PROMPT),
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        # Process the chat log with AI Hub
        # Loop to handle tool calls: model may call tools, then we need to call again with results
        while True:
            await self._async_handle_chat_log(chat_log)

            # If there are unresponded tool results, continue the loop
            if not chat_log.unresponded_tool_results:
                break

        # Return result from chat log
        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    async def _handle_intent(
        self,
        intent_info: dict,
        user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Handle recognized intent."""
        try:
            from .intents import get_intent_handler
            intent_handler = get_intent_handler(self.hass)

            # 处理意图
            result = await intent_handler.handle_intent(intent_info)

            if result.get("success", False):
                # 创建成功的响应
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_speech(result.get("message", "操作完成"))

                return conversation.ConversationResult(
                    response=intent_response,
                    conversation_id=user_input.conversation_id
                )
            else:
                # 创建错误响应
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    result.get("message", "操作失败")
                )

                return conversation.ConversationResult(
                    response=intent_response,
                    conversation_id=user_input.conversation_id
                )

        except Exception as e:
            _LOGGER.error("Error handling intent: %s", e)
            # 返回错误响应
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"意图处理失败: {str(e)}"
            )

            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id
            )

    async def _handle_automation_request(
        self,
        user_input: conversation.ConversationInput
    ) -> Optional[conversation.ConversationResult]:
        """Handle automation creation requests."""
        user_text = user_input.text.lower()

        # 加载配置获取自动化关键词
        try:
            from .intents import _load_config
            config = await _load_config()
            if not config:
                _LOGGER.debug("No config available for automation keywords")
                return None

            automation_keywords = config.get('automation_keywords', [])
            if not automation_keywords:
                _LOGGER.debug("No automation_keywords found in config")
                return None

        except Exception as e:
            _LOGGER.debug("Failed to load automation keywords: %s", e)
            return None

        if not any(keyword in user_text for keyword in automation_keywords):
            return None

        try:
            from .ai_automation import get_automation_manager
            manager = get_automation_manager(self.hass)

            # 提取自动化描述
            description = self._extract_automation_description(user_input.text)
            if not description:
                return None

            # 创建自动化
            result = await manager.create_automation_from_description(description)

            # 创建响应
            intent_response = intent.IntentResponse(language=user_input.language)

            if result.get("success", False):
                config_data = result.get("config", {})
                automation_name = config_data.get("alias", "新自动化")

                # 使用配置化的成功消息
                responses = config.get('responses', {})
                success_template = responses.get('automation', {}).get('creation_success')
                if success_template:
                    try:
                        message = success_template.format(automation_name=automation_name)
                    except KeyError:
                        message = success_template
                else:
                    message = f"我已经为您创建了自动化: {automation_name}"

                # 可以添加更多配置详情
                if config_data.get("trigger"):
                    triggers = [t.get("platform", "unknown") for t in config_data["trigger"]]
                    message += f"\\n触发条件: {', '.join(triggers)}"

                intent_response.async_set_speech(message)
            else:
                # 使用配置化的错误消息
                responses = config.get('responses', {})
                error_template = responses.get('automation', {}).get('creation_error')
                if error_template:
                    try:
                        error_msg = error_template.format(error=result.get('error', '未知错误'))
                    except KeyError:
                        error_msg = error_template
                else:
                    error_msg = f"创建自动化失败: {result.get('error', '未知错误')}"

                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    error_msg
                )

            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id
            )

        except Exception as e:
            _LOGGER.error("Error handling automation request: %s", e)
            return None

    def _extract_automation_description(self, user_text: str) -> Optional[str]:
        """Extract automation description from user input."""
        # 加载配置获取自动化前缀
        try:
            from .intents import _load_config
            import asyncio

            # Try to get config sync or async
            try:
                loop = asyncio.get_running_loop()
                config = loop.run_until_complete(_load_config())
            except RuntimeError:
                config = asyncio.run(_load_config())

            if not config:
                prefixes = []
            else:
                prefixes = config.get('automation_prefixes', [])

        except Exception as e:
            _LOGGER.debug("Failed to load automation prefixes: %s", e)
            prefixes = []

        description = user_text
        for prefix in prefixes:
            if prefix in description:
                description = description.replace(prefix, "").strip()

        # 如果描述太短或为空，返回None
        if len(description) < 5:
            return None

        return description
