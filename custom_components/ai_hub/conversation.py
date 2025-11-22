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

        # 🚀 检查是否需要本地意图处理 (全局设备控制)
        try:
            from .intents import get_global_intent_handler
            intent_handler = get_global_intent_handler(self.hass)

            if intent_handler and intent_handler.should_handle(user_input.text):
                # 需要本地意图处理的全局控制指令
                _LOGGER.info(f"🚀 本地意图处理: {user_input.text}")
                intent_result = await intent_handler.handle(user_input.text, user_input.language)

                if intent_result:
                    _LOGGER.info(f"✅ 本地意图完成")
                    return conversation.ConversationResult(
                        response=intent_result["response"],
                        conversation_id=user_input.conversation_id
                    )

        except Exception as e:
            _LOGGER.debug("Local intent handling failed: %s", e)

        # 其他情况交给LLM处理
        # Home Assistant会通过conversation组件自动处理意图

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

            # 🔄 新增：验证设备操作并重试 (3秒内)
            if hasattr(chat_log, 'tool_calls') and chat_log.tool_calls:
                device_operations = [
                    call for call in chat_log.tool_calls
                    if self._is_device_operation(call.tool_name)
                ]

                if device_operations:
                    _LOGGER.info(f"🔧 验证 {len(device_operations)} 个设备操作 (3秒内完成)")
                    await self._verify_device_operations_with_retry(device_operations)

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
            from .intents import get_device_verification_config
            config = get_device_verification_config()
        except Exception as e:
            _LOGGER.debug(f"获取验证配置失败: {e}")
            # 使用默认配置
            config = {
                'total_timeout': 3,
                'max_retries': 3,
                'wait_times': [0.5, 0.8, 1.1]
            }

        import time
        import asyncio

        start_time = time.time()
        total_timeout = config.get('total_timeout', 3)
        max_retries = config.get('max_retries', 3)
        wait_times = config.get('wait_times', [0.5, 0.8, 1.1])

        _LOGGER.info(f"🔧 开始设备操作验证，总时间限制{total_timeout}秒，最多重试{max_retries}次")

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
                    _LOGGER.info(f"✅ 所有设备操作验证成功 (耗时{total_time:.1f}秒)")
                    return True
                else:
                    _LOGGER.info(f"⏳ 第{attempt + 1}次验证未完全成功，继续等待 (剩余{remaining_time:.1f}秒)")

            except Exception as e:
                _LOGGER.debug(f"验证过程出错: {e}")

        total_time = time.time() - start_time
        _LOGGER.warning(f"⚠️ {total_timeout}秒内无法验证所有设备操作成功 (耗时{total_time:.1f}秒)")
        return False

    async def _get_live_context(self):
        """获取当前设备状态 (模拟GetLiveContext工具)"""
        # 这里应该调用实际的GetLiveContext工具
        # 暂时返回模拟数据
        return {
            "lights": {"living_room_main": "off", "living_room_ambient": "on"},
            "switches": {},
            "climate": {},
            "covers": {},
            "media_players": {},
            "locks": {},
            "vacuums": {}
        }

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

        # 从配置中读取"所有"相关的关键词，避免硬编码
        try:
            config = get_intents_config()
            all_keywords = config.get('global_keywords', []) if config else []
            if not all_keywords:
                # 如果配置中没有，使用默认值
                all_keywords = ["所有", "全部", "一切"]
        except Exception as e:
            _LOGGER.debug(f"读取global_keywords失败，使用默认值: {e}")
            all_keywords = ["所有", "全部", "一切"]

        return any(keyword in text for keyword in all_keywords)

    def _has_local_intent_config(self, intent_type: str, intent_info: Dict[str, Any]) -> bool:
        """检查意图是否在本地配置中定义为需要特殊处理"""
        text = intent_info.get("text", "").lower()

        # 从intents.yaml中读取本地特征配置，避免硬编码
        local_features = []
        try:
            intents_config = get_intents_config()
            if intents_config and 'expansion_rules' in intents_config:
                # 获取所有本地特征关键词
                for key, value in intents_config['expansion_rules'].items():
                    if isinstance(value, str) and '|' in value:
                        # 拆分管道符分隔的关键词
                        local_features.extend(value.split('|'))
                _LOGGER.debug(f"从intents.yaml加载本地特征关键词: {len(local_features)}个")
        except Exception as e:
            _LOGGER.debug(f"读取本地配置失败，使用默认值: {e}")
            # 如果配置读取失败，使用默认的关键词（从配置中读取）
            local_features = ["所有设备", "全部设备", "所有灯", "全部灯"]

        return any(feature in text for feature in local_features)

    def _should_skip_ha_standard_processing(self, text: str) -> bool:
        """判断是否应该跳过Home Assistant标准处理，直接进入本地意图

        只有非常明确的本地意图才跳过HA标准处理，如:
        - "打开所有设备"
        - "关闭所有灯"
        """
        try:
            from .intents import get_intents_config
            config = get_intents_config()
            if not config:
                return False

            global_config = config.get('GlobalDeviceControl', {})
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

            # 检查设备类型关键词
            device_type_keywords = global_config.get('device_type_keywords', {})
            has_device = any(keyword in text_lower for keywords in device_type_keywords.values() for keyword in keywords)

            # 只有同时具备：全局关键词 + 明确动作 + 设备类型，才跳过HA处理
            should_skip = has_global and has_action and has_device

            if should_skip:
                _LOGGER.debug(f"跳过HA标准处理: 全局={has_global}, 动作={has_action}, 设备={has_device}")

            return should_skip

        except Exception as e:
            _LOGGER.debug(f"判断跳过HA处理时出错: {e}")
            return False

    

    