"""Conversation support for AI Hub."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Literal, Optional

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent, llm
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_LLM_HASS_API, CONF_PROMPT, DOMAIN
from .entity import AIHubBaseLLMEntity
from .intents import get_config_cache

_LOGGER = logging.getLogger(__name__)

MATCH_ALL: Literal["*"] = "*"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    _LOGGER.debug("Setting up conversation entities, subentries: %s", config_entry.subentries)

    if not config_entry.subentries:
        _LOGGER.warning("No subentries found in config entry")
        return

    for subentry in config_entry.subentries.values():
        _LOGGER.debug("Processing subentry: %s, type: %s", subentry.subentry_id, subentry.subentry_type)
        if subentry.subentry_type != "conversation":
            continue

        async_add_entities(
            [AIHubConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )
        _LOGGER.debug("Created conversation entity for subentry: %s", subentry.subentry_id)


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

        # 初始化配置缓存
        self._config_cache = get_config_cache()

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

        处理流程:
        1. 本地意图处理（全局设备控制等 HA 原生不支持的功能）
        2. 如果本地没匹配，交给 Home Assistant 处理（内置意图 + LLM）
        """
        options = self.subentry.data

        # ========== 步骤1: 本地意图处理 ==========
        # 只处理 HA 原生不支持的功能（如全局设备控制）

        # 1a. 检查是否是自动化创建请求
        try:
            automation_result = await self._handle_automation_request(user_input)
            if automation_result:
                return automation_result
        except Exception as e:
            _LOGGER.debug("Automation handling failed: %s", e)

        # 1b. 检查是否需要本地意图处理 (全局设备控制)
        try:
            from .intents import get_global_intent_handler
            intent_handler = get_global_intent_handler(self.hass)

            if intent_handler and intent_handler.should_handle(user_input.text):
                _LOGGER.debug("本地意图处理: %s", user_input.text)
                intent_result = await intent_handler.handle(user_input.text, user_input.language)

                if intent_result:
                    _LOGGER.debug("本地意图完成")
                    return conversation.ConversationResult(
                        response=intent_result["response"],
                        conversation_id=user_input.conversation_id
                    )
        except Exception as e:
            _LOGGER.debug("Local intent handling failed: %s", e)

        # ========== 步骤2: 尝试 HA 内置意图处理 ==========
        # timer、shopping list、设备控制等 HA 原生支持的意图
        # 注意：这个步骤可能会增加延迟，只在必要时启用
        try:
            from homeassistant.components.conversation import default_agent

            # 获取 HA 默认的 conversation agent
            agent = await default_agent.async_get_agent(self.hass)
            if agent:
                # 让默认 agent 处理
                result = await agent.async_process(user_input)
                if result and result.response:
                    response_type = result.response.response_type
                    # 如果成功处理（不是错误且不是 "no intent matched"）
                    if response_type == intent.IntentResponseType.ACTION_DONE:
                        _LOGGER.debug("HA 内置意图处理成功: %s", user_input.text)
                        return result
                    elif response_type == intent.IntentResponseType.QUERY_ANSWER:
                        _LOGGER.debug("HA 内置意图查询成功: %s", user_input.text)
                        return result

        except Exception as e:
            _LOGGER.debug("HA 内置意图处理跳过: %s", e)

        # ========== 步骤3: LLM 处理 ==========

        try:
            # 🚀 高性能LLM API配置获取
            llm_apis = options.get(CONF_LLM_HASS_API, [])

            if not llm_apis:
                _LOGGER.warning("⚠️ 未找到LLM API配置，检查LLM_API_ASSIST")
                # 尝试使用默认的LLM API ASSIST
                try:
                    default_llm_api = llm.LLM_API_ASSIST
                    llm_apis = [default_llm_api]
                    _LOGGER.debug("使用默认LLM API")
                except Exception as e:
                    _LOGGER.error(f"❌ LLM_API_ASSIST获取失败: {e}")
                    empty_response = intent.IntentResponse(language=user_input.language)
                    error_msg = self._config_cache.get_error_message("llm_config_error")
                    empty_response.async_set_speech(error_msg)
                    return conversation.ConversationResult(
                        response=empty_response,
                        conversation_id=user_input.conversation_id
                    )

            # Provide LLM data (tools, home info, etc.)
            user_prompt = options.get(CONF_PROMPT, "")
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                llm_apis,
                user_prompt,
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            _LOGGER.error(f"❌ LLM对话错误: {err}")
            return err.as_conversation_result()

        # Process the chat log with AI Hub
        # Loop to handle tool calls: model may call tools, then we need to call again with results
        loop_count = 0
        while True:
            loop_count += 1
            _LOGGER.debug("LLM处理循环 %d", loop_count)

            # 检查chat_log状态
            if hasattr(chat_log, 'tool_calls') and chat_log.tool_calls:
                _LOGGER.debug("LLM发起了 %d 个工具调用", len(chat_log.tool_calls))
            else:
                _LOGGER.debug("LLM没有发起工具调用")

            await self._async_handle_chat_log(chat_log)

            # 🔄 设备操作验证（可选，默认禁用以提高响应速度）
            # 如果需要验证设备操作，可以在配置中启用
            # if hasattr(chat_log, 'tool_calls') and chat_log.tool_calls:
            #     device_operations = [
            #         call for call in chat_log.tool_calls
            #         if self._is_device_operation(call.tool_name)
            #     ]
            #     if device_operations:
            #         _LOGGER.debug("验证 %d 个设备操作", len(device_operations))
            #         await self._verify_device_operations_with_retry(device_operations)

            # 检查是否有工具调用结果
            if hasattr(chat_log, 'unresponded_tool_results') and chat_log.unresponded_tool_results:
                _LOGGER.debug("发现未处理的工具调用结果")
            else:
                _LOGGER.debug("没有更多工具调用，处理完成")

            # If there are no unresponded tool results, continue the loop
            if not chat_log.unresponded_tool_results:
                break

        # Return result from chat log
        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    def _is_device_operation(self, tool_name: str) -> bool:
        """判断是否是设备控制操作"""
        try:
            from .intents import is_device_operation
            return is_device_operation(tool_name)
        except Exception as e:
            _LOGGER.debug(f"设备操作判断失败: {e}")
            return False

    async def _verify_device_operations_with_retry(self, device_operations):
        """验证设备操作并重试，使用配置的时间限制"""
        try:
            config = self._config_cache.get_verification_config()
        except Exception as e:
            _LOGGER.debug(f"获取验证配置失败: {e}")
            # 使用硬编码的备用配置
            config = {
                'total_timeout': 3,
                'max_retries': 3,
                'wait_times': [0.5, 0.8, 1.1]
            }

        import asyncio

        start_time = time.time()
        total_timeout = config.get('total_timeout', 3)
        max_retries = config.get('max_retries', 3)
        wait_times = config.get('wait_times', [0.5, 0.8, 1.1])

        _LOGGER.debug("开始设备操作验证，总时间限制%ds，最多重试%d次", total_timeout, max_retries)

        for attempt in range(max_retries):
            # 检查是否还有时间
            elapsed = time.time() - start_time
            remaining_time = total_timeout - elapsed

            if remaining_time <= 0:
                _LOGGER.warning("⏰ 验证超时，停止重试")
                break

            # 获取等待时间
            wait_time = wait_times[attempt] if attempt < len(wait_times) else wait_times[-1]
            # 确保不超过剩余时间
            wait_time = min(wait_time, remaining_time * 0.3)

            await asyncio.sleep(wait_time)

            # 使用GetLiveContext验证
            try:
                # 模拟调用GetLiveContext工具
                current_context = await self._get_live_context()

                # 检查操作是否成功
                all_successful = True
                for operation in device_operations:
                    if not self._is_operation_successful(operation, current_context):
                        all_successful = False
                        break

                if all_successful:
                    total_time = time.time() - start_time
                    _LOGGER.debug("所有设备操作验证成功 (耗时%.1fs)", total_time)
                    return True
                else:
                    _LOGGER.debug("第%d次验证未完全成功，继续等待", attempt + 1)

            except Exception as e:
                _LOGGER.debug(f"验证过程出错: {e}")

        total_time = time.time() - start_time
        _LOGGER.warning(f"⚠️ {total_timeout}秒内无法验证所有设备操作成功 (耗时{total_time:.1f}秒)")
        return False

    async def _get_live_context(self):
        """获取当前设备状态 (模拟GetLiveContext工具)"""
        # 这里应该调用实际的GetLiveContext工具
        # 从配置中读取模拟数据
        return self._config_cache.get_device_state_simulation()

    def _is_operation_successful(self, operation, context):
        """检查单个操作是否成功"""
        tool_name = operation.tool_name
        arguments = operation.arguments

        # 根据操作类型检查对应设备状态
        if tool_name == 'light.turn_on':
            # 检查灯是否打开
            entity_id = arguments.get('entity_id', [])
            if isinstance(entity_id, str):
                entity_id = [entity_id]

            for eid in entity_id:
                # 从context中检查状态
                if 'living_room_main' in eid and context.get('lights', {}).get('living_room_main') != 'on':
                    return False
                if 'living_room_ambient' in eid and context.get('lights', {}).get('living_room_ambient') != 'on':
                    return False
            return True

        elif tool_name == 'light.turn_off':
            # 检查灯是否关闭
            entity_id = arguments.get('entity_id', [])
            if isinstance(entity_id, str):
                entity_id = [entity_id]

            for eid in entity_id:
                if 'living_room_main' in eid and context.get('lights', {}).get('living_room_main') != 'off':
                    return False
                if 'living_room_ambient' in eid and context.get('lights', {}).get('living_room_ambient') != 'off':
                    return False
            return True

        # 其他设备类型的检查可以在这里添加
        # 暂时返回True，表示其他操作假设成功
        return True

    async def _handle_automation_request(
        self,
        user_input: conversation.ConversationInput
    ) -> Optional[conversation.ConversationResult]:
        """Handle automation creation requests."""
        user_text = user_input.text.lower()

        # 使用配置缓存获取自动化关键词
        try:
            automation_keywords = self._config_cache.get_automation_config('automation_keywords', [])

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
                responses = self._config_cache.get_responses_config()
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
                    unknown_platform = self._config_cache.get_error_message("automation_trigger_unknown")
                    triggers = [t.get("platform", unknown_platform) for t in config_data["trigger"]]
                    message += f"\\n触发条件: {', '.join(triggers)}"

                intent_response.async_set_speech(message)
            else:
                # 使用配置化的错误消息
                responses = self._config_cache.get_responses_config()
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
        # 使用配置缓存获取自动化前缀
        try:
            prefixes = self._config_cache.get_automation_config('automation_prefixes', [])

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
        # 检查是否是"所有设备"相关的操作（HA原生不支持）
        if self._is_all_device_operation(intent_info):
            return True

        # 检查是否是其他需要本地处理的特殊功能
        # 这里可以根据配置或模式来动态判断
        return self._has_local_intent_config(intent_type, intent_info)

    def _is_all_device_operation(self, intent_info: Dict[str, Any]) -> bool:
        """判断是否是"所有设备"操作"""
        text = intent_info.get("text", "").lower()

        # 使用配置缓存获取全局关键词，避免硬编码
        try:
            global_keywords = self._config_cache.get_global_keywords()
        except Exception as e:
            _LOGGER.debug(f"读取global_keywords失败，使用默认值: {e}")
            global_keywords = ["所有", "全部", "一切"]

        return any(keyword in text for keyword in global_keywords)

    def _has_local_intent_config(self, intent_type: str, intent_info: Dict[str, Any]) -> bool:
        """检查意图是否在本地配置中定义为需要特殊处理"""
        text = intent_info.get("text", "").lower()

        # 使用配置缓存获取本地特征关键词，避免硬编码
        try:
            local_features = self._config_cache.get_local_features()
            _LOGGER.debug(f"从配置缓存加载本地特征关键词: {len(local_features)}个")
        except Exception as e:
            _LOGGER.debug(f"读取本地配置失败，使用默认值: {e}")
            local_features = ["所有设备", "全部设备", "所有灯", "全部灯"]

        return any(feature in text for feature in local_features)

    def _should_skip_ha_standard_processing(self, text: str) -> bool:
        """判断是否应该跳过Home Assistant标准处理，直接进入本地意图

        只有非常明确的本地意图才跳过HA标准处理，如:
        - "打开所有设备"
        - "关闭所有灯"
        """
        try:
            config = self._config_cache.get_config()
            if not config:
                return False

            # 从 local_intents.GlobalDeviceControl 获取配置
            local_intents = config.get('local_intents', {})
            global_config = local_intents.get('GlobalDeviceControl', {})
            if not global_config:
                return False

            text_lower = text.lower().strip()

            # 检查全局关键词
            global_keywords = global_config.get('global_keywords', [])
            has_global = any(keyword in text_lower for keyword in global_keywords)

            # 检查明确的开关关键词
            on_keywords = global_config.get('on_keywords', [])
            off_keywords = global_config.get('off_keywords', [])
            has_action = any(keyword in text_lower for keyword in on_keywords + off_keywords)

            # 检查是否包含参数控制关键词（亮度、音量等）
            param_keywords = global_config.get('param_keywords', [])
            brightness_keywords = global_config.get('brightness_keywords', [])
            volume_keywords = global_config.get('volume_keywords', [])
            color_keywords = global_config.get('color_keywords', [])
            temperature_keywords = global_config.get('temperature_keywords', [])

            has_param_control = any(keyword in text_lower for keyword in
                                    param_keywords + brightness_keywords + volume_keywords +
                                    color_keywords + temperature_keywords)

            # 跳过HA处理的情况：只有明确的全局指令才进行本地处理
            # 要求必须同时包含全局关键词和明确的动作或参数控制
            should_skip = has_global and (has_action or has_param_control)

            if should_skip:
                _LOGGER.debug(
                    f"跳过HA标准处理: '{text}' (全局关键词: {has_global}, 动作关键词: {has_action}, 参数控制: {has_param_control})")

            return should_skip

        except Exception as e:
            _LOGGER.debug(f"判断跳过HA处理时出错: {e}")
            return False
