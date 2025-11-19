"""Conversation support for AI Hub."""

from __future__ import annotations

import logging
import time
from typing import Literal, Dict, Any, Optional
from dataclasses import dataclass

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import intent

from .const import CONF_LLM_HASS_API, CONF_PROMPT, DOMAIN
from .entity import AIHubBaseLLMEntity
from .intents import get_intents_config

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

        Simplified processing flow:
        1. Automation request handling
        2. Home Assistant intent processing (including registered Chinese intents)
        3. LLM fallback processing
        """
        options = self.subentry.data

        # 检查是否是自动化创建请求
        try:
            automation_result = await self._handle_automation_request(user_input)
            if automation_result:
                return automation_result
        except Exception as e:
            _LOGGER.debug("Automation handling failed: %s", e)

        # 跳过意图匹配，直接交给LLM处理
        # Home Assistant会通过conversation组件自动处理意图
        # 我们的intents.yaml作为语言扩展包被HA自动识别

        # 步骤4: LLM处理 (如果所有意图处理都失败)

        try:
            # 检查LLM配置
            llm_apis = options.get(CONF_LLM_HASS_API, [])
            _LOGGER.info(f"🤖 LLM配置: {llm_apis}")
            _LOGGER.info(f"🤖 可用选项: {list(options.keys())}")

            if not llm_apis:
                _LOGGER.warning("⚠️ LLM没有配置Hass API权限，无法控制设备!")
            else:
                _LOGGER.info(f"✅ LLM已配置 {len(llm_apis)} 个Hass API")

            # Provide LLM data (tools, home info, etc.)
            _LOGGER.info("🔧 提供LLM数据（工具、家庭信息等）")
            user_prompt = options.get(CONF_PROMPT, "")
            _LOGGER.info(f"📝 用户配置的prompt: {user_prompt}")
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                llm_apis,
                user_prompt,
                user_input.extra_system_prompt,
            )
            _LOGGER.info("✅ LLM数据提供完成")
        except conversation.ConverseError as err:
            _LOGGER.error(f"❌ LLM对话错误: {err}")
            return err.as_conversation_result()

        # Process the chat log with AI Hub
        # Loop to handle tool calls: model may call tools, then we need to call again with results
        loop_count = 0
        while True:
            loop_count += 1
            _LOGGER.info(f"🔄 LLM处理循环 {loop_count}: 检查是否有工具调用")

            # 检查chat_log状态
            if hasattr(chat_log, 'tool_calls') and chat_log.tool_calls:
                _LOGGER.info(f"🔧 LLM发起了 {len(chat_log.tool_calls)} 个工具调用")
                for tool_call in chat_log.tool_calls:
                    _LOGGER.info(f"🛠️ 工具调用请求: {tool_call.tool_name} - {tool_call.arguments}")
            else:
                _LOGGER.info("ℹ️ LLM没有发起工具调用")

            await self._async_handle_chat_log(chat_log)

            # 检查是否有工具调用结果
            if hasattr(chat_log, 'unresponded_tool_results') and chat_log.unresponded_tool_results:
                # 检查是否是boolean值
                if isinstance(chat_log.unresponded_tool_results, bool):
                    _LOGGER.info("🔧 发现未处理的工具调用结果")
                else:
                    # 如果是列表，显示数量
                    _LOGGER.info(f"🔧 发现 {len(chat_log.unresponded_tool_results)} 个未处理的工具结果")
                    for tool_result in chat_log.unresponded_tool_results:
                        _LOGGER.info(f"🛠️ 工具调用结果: {tool_result.tool_name} - {tool_result.result}")
            else:
                _LOGGER.info("✅ 没有更多工具调用，处理完成")

            # If there are no unresponded tool results, continue the loop
            if not chat_log.unresponded_tool_results:
                break

        # Return result from chat log
        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    
    async def _handle_automation_request(
        self,
        user_input: conversation.ConversationInput
    ) -> Optional[conversation.ConversationResult]:
        """Handle automation creation requests."""
        user_text = user_input.text.lower()

        # 加载配置获取自动化关键词
        try:
            from .intents import get_intents_config
            config = get_intents_config()
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
                intents_config = get_intents_config()
                responses = intents_config.get('responses', {}) if intents_config else {}
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
                intents_config = get_intents_config()
                responses = intents_config.get('responses', {}) if intents_config else {}
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
            from .intents import get_intents_config

            config = get_intents_config()
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

    def _is_local_special_function(self, intent_type: str, intent_info: Dict[str, Any]) -> bool:
        """判断是否是真正的本地特殊功能"""
        text = intent_info.get("text", "").lower()

        # 检查是否是"所有设备"相关的操作（HA原生不支持）
        if self._is_all_device_operation(intent_info):
            return True

        # 检查是否是其他需要本地处理的特殊功能
        # 这里可以根据配置或模式来动态判断
        return self._has_local_intent_config(intent_type, intent_info)

    def _is_all_device_operation(self, intent_info: Dict[str, Any]) -> bool:
        """判断是否是"所有设备"操作"""
        text = intent_info.get("text", "").lower()

        # 检查是否包含"所有"相关的关键词
        all_keywords = ["所有", "全部", "一切"]
        return any(keyword in text for keyword in all_keywords)

    def _has_local_intent_config(self, intent_type: str, intent_info: Dict[str, Any]) -> bool:
        """检查意图是否在本地配置中定义为需要特殊处理"""
        text = intent_info.get("text", "").lower()

        # 检查是否包含了需要本地处理的特征
        # 比如所有设备控制、特殊功能等
        local_features = [
            # 所有设备相关的关键词组合
            "所有设备",
            "全部设备",
            "所有灯",
            "全部灯",

            # 可以在配置中添加更多特征
        ]

        return any(feature in text for feature in local_features)

    