"""意图模块 - 超高速优化版本 - 解决10秒延迟问题"""

from __future__ import annotations

import logging
import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

try:
    from .const import DOMAIN
except ImportError:
    DOMAIN = "ai_hub"

_LOGGER = logging.getLogger(__name__)

# 全局配置缓存 - 超高性能设置
_INTENTS_CONFIG: Optional[Dict[str, Any]] = None
_CONFIG_LOADED = False  # 简单的加载标记，不再需要TTL


async def async_setup_intents(hass: HomeAssistant) -> None:
    """向Home Assistant注册中文意图扩展 - 超高性能版本"""
    global _INTENTS_CONFIG

    try:
        # 使用缓存机制加载配置
        config = await _load_intents_config_once()
        if not config:
            _LOGGER.warning("无法加载中文意图配置")
            return

        _INTENTS_CONFIG = config

        # 极简化处理 - 最小化日志和计算
        intents = config.get('intents', {})
        registered_count = sum(len(item.get('sentences', []))
                           for intent_data in intents.values()
                           for item in intent_data.get('data', []))

        # 只在首次加载时记录一次日志
        if _CONFIG_LOADED == False:
            _LOGGER.info(f"中文意图配置已加载 ({registered_count} 个句子)")

    except Exception as e:
        _LOGGER.error(f"本地意图初始化失败: {e}")






def get_intents_config() -> Optional[Dict[str, Any]]:
    """获取意图配置（供其他模块使用）"""
    return _INTENTS_CONFIG if _CONFIG_LOADED else None


def get_device_operations_config() -> Dict[str, Any]:
    """获取设备操作配置"""
    if not _CONFIG_LOADED or not _INTENTS_CONFIG:
        return get_default_device_operations_config()

    return _INTENTS_CONFIG.get('device_operations', get_default_device_operations_config())


def get_default_device_operations_config() -> Dict[str, Any]:
    """获取默认设备操作配置"""
    return {
        'verification': {
            'total_timeout': 3,
            'max_retries': 3,
            'wait_times': [0.5, 0.8, 1.1]
        },
        'control_operations': {
            'light': ['light.turn_on', 'light.turn_off', 'light.toggle', 'light.set_brightness', 'light.set_color'],
            'switch': ['switch.turn_on', 'switch.turn_off', 'switch.toggle'],
            'climate': ['climate.turn_on', 'climate.turn_off', 'climate.set_temperature', 'climate.set_hvac_mode'],
            'fan': ['fan.turn_on', 'fan.turn_off', 'fan.set_speed'],
            'cover': ['cover.open_cover', 'cover.close_cover', 'cover.set_cover_position', 'cover.stop_cover'],
            'media_player': ['media_player.media_play', 'media_player.media_pause', 'media_player.media_stop', 'media_player.volume_set'],
            'lock': ['lock.unlock', 'lock.lock'],
            'vacuum': ['vacuum.start', 'vacuum.pause', 'vacuum.stop', 'vacuum.return_to_base'],
            'script': ['script.turn_on', 'script.turn_off', 'script.toggle'],
            'scene': ['scene.turn_on'],
            'valve': ['valve.open_valve', 'valve.close_valve', 'valve.set_valve_position']
        }
    }


def is_device_operation(tool_name: str) -> bool:
    """判断是否是设备控制操作"""
    config = get_device_operations_config()
    control_ops = config.get('control_operations', {})

    # 检查是否在任何设备类型中
    for device_type, operations in control_ops.items():
        if tool_name in operations:
            return True

    return False


def get_device_verification_config() -> Dict[str, Any]:
    """获取设备验证配置"""
    config = get_device_operations_config()
    return config.get('verification', {
        'total_timeout': 3,
        'max_retries': 3,
        'wait_times': [0.5, 0.8, 1.1]
    })


async def _load_intents_config_once() -> Optional[Dict[str, Any]]:
    """一次性加载intents.yaml配置 - 简化版本"""
    global _INTENTS_CONFIG, _CONFIG_LOADED

    # 如果已经加载过，直接返回
    if _CONFIG_LOADED and _INTENTS_CONFIG is not None:
        return _INTENTS_CONFIG

    try:
        import yaml
        yaml_path = Path(__file__).parent / "intents.yaml"

        if not yaml_path.exists():
            _LOGGER.warning(f"intents.yaml不存在: {yaml_path}")
            return None

        # 使用异步文件读取避免阻塞事件循环
        import asyncio
        loop = asyncio.get_running_loop()

        def _load_yaml():
            with open(yaml_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)

        config = await loop.run_in_executor(None, _load_yaml)

        if not config:
            _LOGGER.error("intents.yaml为空")
            return None

        # 保存到全局变量
        _INTENTS_CONFIG = config
        _CONFIG_LOADED = True

        # 验证关键配置
        local_intents = config.get('local_intents', {})
        if local_intents and local_intents.get('GlobalDeviceControl'):
            _LOGGER.info("意图配置已加载 - 包含GlobalDeviceControl")
        else:
            _LOGGER.warning("意图配置已加载 - 但缺少GlobalDeviceControl配置")

        return config

    except Exception as e:
        _LOGGER.error(f"加载intents.yaml失败: {e}")
        return None


class ChineseIntentHandler(intent.IntentHandler):
    """中文意图处理器 - 仅作为后备选项"""

    def __init__(self, hass: HomeAssistant, intent_name: str, sentence: str):
        self.hass = hass
        self.intent_type = intent_name
        self.sentence = sentence

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """处理意图 - 委托给Home Assistant的原生意图处理"""
        try:
            response = intent.IntentResponse(language="zh-CN")
            response.async_set_speech("好的，正在处理您的请求")
            return response

        except Exception as e:
            _LOGGER.error(f"意图处理失败 {self.intent_type}: {e}")
            response = intent.IntentResponse()
            response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"意图处理失败: {str(e)}"
            )
            return response


# 性能统计函数 - 仅在需要时调用
def get_local_intents_config() -> Optional[Dict[str, Any]]:
    """获取本地意图配置"""
    if not _INTENTS_CONFIG:
        return None
    return _INTENTS_CONFIG.get('local_intents', {})


class LocalIntentHandler:
    """本地意图处理器"""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.local_config = get_local_intents_config()

    def _get_default_area_name(self) -> str:
        """获取默认区域名称"""
        global_config = self.local_config.get('GlobalDeviceControl', {})
        return global_config.get('default_area_name', '全屋')

    def _format_error_suffix(self, error_count: int) -> str:
        """格式化错误后缀消息"""
        if error_count > 0:
            return f"，{error_count}个设备失败"
        return ""

    def should_handle(self, text: str) -> bool:
        """智能判断是否应该使用本地意图处理"""
        if not self.local_config:
            return False

        global_config = self.local_config.get('GlobalDeviceControl', {})
        if not global_config:
            return False

        text_clean = text.strip()
        text_lower = text.lower().strip()

        # 规则1: 检查明确的全局关键词 - HA不支持的功能
        global_keywords = global_config.get('global_keywords', [])
        has_global_keyword = any(keyword in text_lower for keyword in global_keywords)

        # 规则2: 检查明确的动作词 + 简短文本 (避免处理上下文指令)
        action_words = global_config.get('on_keywords', []) + global_config.get('off_keywords', [])
        has_action_word = any(action in text_lower for action in action_words)
        is_short_text = len(text_clean) <= 4  # 短文本可能是上下文指令

        # 关键判断: 必须有全局关键词，或者是明确的全局控制指令
        should_handle = has_global_keyword

        # 对于有动作词的短文本，如果缺少全局关键词，则不处理（让HA处理上下文）
        if has_action_word and is_short_text and not has_global_keyword:
            should_handle = False

        _LOGGER.debug(f"本地意图判断: '{text}' → {should_handle} (全局关键词={has_global_keyword}, 短文本={is_short_text})")

        return should_handle

    async def handle(self, text: str, language: str = "zh-CN"):
        """处理本地意图"""
        if not self.should_handle(text):
            return None

        global_config = self.local_config.get('GlobalDeviceControl', {})
        text_lower = text.lower().strip()

        # 1. 检查是否为参数控制命令
        param_result = await self._handle_parameter_control(text, text_lower, global_config)
        if param_result:
            return param_result

        # 2. 解析操作类型 - 只处理明确的控制命令
        on_keywords = global_config.get('on_keywords', [])
        off_keywords = global_config.get('off_keywords', [])

        is_on = any(keyword in text_lower for keyword in on_keywords)
        is_off = any(keyword in text_lower for keyword in off_keywords)

        _LOGGER.debug(f"操作类型解析: 打开={is_on}, 关闭={is_off}")

        # 如果没有明确的开关关键词，交给LLM处理（包括查询类请求）
        if not (is_on or is_off):
            _LOGGER.debug(f"未识别到明确的控制意图，交给LLM处理: {text}")
            return None

        # 解析设备类型关键词和区域关键词
        area_names = []
        device_types = []
        areas_config = None
        device_type_config = None

        try:
            # 尝试从缓存的主配置中获取区域和设备类型列表
            if _INTENTS_CONFIG and 'lists' in _INTENTS_CONFIG:
                areas_config = _INTENTS_CONFIG['lists'].get('area_names', {}).get('values', [])
        except:
            pass

        # 从配置中获取设备类型关键词
        device_type_keywords = global_config.get('device_type_keywords', {})
        _LOGGER.debug(f"加载设备类型关键词配置: {device_type_keywords}")

        # 识别文本中的区域
        if areas_config:
            for area in areas_config:
                if area in text_lower:
                    area_names.append(area)

        # 识别文本中的设备类型 - 直接引用lists配置
        # 如果device_type_keywords是字符串，尝试从lists中获取
        if isinstance(device_type_keywords, str) and device_type_keywords.startswith("{{lists}}"):
            # 从主配置获取lists配置
            lists_config = _INTENTS_CONFIG.get('lists', {}) if _INTENTS_CONFIG else {}
            _LOGGER.debug(f"使用lists配置进行设备类型识别，文本: '{text_lower}'")

            # 检查各种设备类型的关键词
            domain_mapping = {
                'light': 'light_names',
                'switch': 'switch_names',
                'climate': 'climate_names',
                'fan': 'fan_names',
                'cover': 'cover_names',
                'media_player': 'media_player_names',
                'lock': 'lock_names',
                'vacuum': 'vacuum_names',
                'valve': 'valve_names'
            }

            for domain, list_name in domain_mapping.items():
                keywords_list = lists_config.get(list_name, {}).get('values', [])
                if keywords_list:
                    _LOGGER.debug(f"检查 {domain} 域，关键词列表: {keywords_list}")
                    for keyword in keywords_list:
                        if keyword in text_lower:
                            device_types.append(domain)
                            _LOGGER.info(f"✅ 识别到设备类型: {domain} (关键词: '{keyword}')")
                            break
                else:
                    _LOGGER.debug(f"⚠️ {domain} 域没有找到关键词配置: {list_name}")
        else:
            # 处理传统的字典格式
            _LOGGER.debug(f"使用传统设备类型关键词配置: {device_type_keywords}")
            for keyword, domain in device_type_keywords.items():
                if keyword in text_lower:
                    device_types.append(domain)
                    _LOGGER.debug(f"识别到设备类型: {domain} (关键词: {keyword})")

        # 去重设备类型
        device_types = list(set(device_types))

        # 确定控制范围和域
        is_global_control = not area_names  # 没有识别到特定区域就是全局控制

        # 确定要控制的域 - 严格匹配模式，只操作识别到的设备类型
        if device_types:
            control_domains = device_types
            _LOGGER.info(f"✅ 设备类型识别成功，控制域: {control_domains}")
        else:
            # 严格模式：没有识别到设备类型就不操作任何设备
            control_domains = []
            _LOGGER.warning(f"❌ 未识别到具体设备类型，为确保安全不执行任何操作。文本: '{text}'")

        # 安全检查：如果没有识别到设备类型，返回None让LLM处理
        if not control_domains:
            _LOGGER.info(f"未识别到设备类型，交由LLM处理。文本: '{text}'")
            return None  # 让LLM处理不明确的意图

        # 执行设备控制
        try:
            all_devices = []

            if is_global_control:
                # 全局控制：获取所有域的设备
                for domain in control_domains:
                    try:
                        devices = self.hass.states.async_entity_ids(domain)
                        all_devices.extend(devices)
                    except Exception as e:
                        _LOGGER.debug(f"获取 {domain} 设备失败: {e}")
            else:
                # 区域控制：获取指定区域的设备
                from homeassistant.helpers import entity_registry as er
                try:
                    registry = er.async_get(self.hass)
                    for domain in control_domains:
                        try:
                            domain_devices = self.hass.states.async_entity_ids(domain)
                            for device_id in domain_devices:
                                # 检查设备是否在指定区域中
                                try:
                                    entity_entry = registry.async_get(device_id)
                                    if entity_entry and entity_entry.area_id:
                                        area_entry = registry.async_get_area(entity_entry.area_id)
                                        if area_entry and self._match_area_name(area_entry.name, area_entry.name, area_names):
                                            all_devices.append(device_id)
                                except:
                                    # 如果无法获取区域信息，跳过
                                    continue
                        except Exception as e:
                            _LOGGER.debug(f"获取 {domain} 区域设备失败: {e}")
                except Exception as e:
                    _LOGGER.debug(f"获取实体注册表失败: {e}")
                    # 回退到全局控制
                    for domain in control_domains:
                        try:
                            devices = self.hass.states.async_entity_ids(domain)
                            all_devices.extend(devices)
                        except Exception as e:
                            _LOGGER.debug(f"获取 {domain} 设备失败: {e}")

            if not all_devices:
                return None  # 让LLM处理，而不是直接响应用户

            # 批量控制设备
            domain_services = global_config.get('domain_services', global_config.get('default_domain_services', {}))
            service_key = "turn_on" if is_on else "turn_off"

            # 按域分组执行操作，以提高效率
            all_success = 0
            all_errors = 0
            all_failed_devices = []

            # 按域分组设备
            devices_by_domain = {}
            for device_id in all_devices:
                domain = device_id.split('.')[0]
                if domain not in devices_by_domain:
                    devices_by_domain[domain] = []
                devices_by_domain[domain].append(device_id)

            # 对每个域执行批量操作
            for domain, devices in devices_by_domain.items():
                service_name = domain_services.get(domain, {}).get(service_key, service_key)
                success_count, error_count, failed_devices = await self._execute_device_operations(
                    devices, domain, service_name
                )
                all_success += success_count
                all_errors += error_count
                all_failed_devices.extend(failed_devices)

            success_count = all_success
            error_count = all_errors
            failed_devices = all_failed_devices

            # 生成响应消息
            responses = global_config.get('responses', {})

            # 根据控制范围选择消息
            if is_on:
                if is_global_control:
                    template = responses.get('success_on', '已打开{count}个设备{fail_msg}')
                else:
                    template = responses.get('success_on', '已打开{area}的{count}个设备{fail_msg}')
            else:
                if is_global_control:
                    template = responses.get('success_off', '已关闭{count}个设备{fail_msg}')
                else:
                    template = responses.get('success_off', '已关闭{area}的{count}个设备{fail_msg}')

            # 使用统一的失败消息格式化
            fail_msg = self._format_failure_message(error_count, failed_devices)
            area_text = f"{area_names[0]}" if area_names else ""
            message = template.format(count=success_count, area=area_text, fail_msg=fail_msg)

            return self._create_response(language, message)

        except Exception as e:
            error_template = global_config.get('responses', {}).get('error', '设备控制失败：{error}')
            error_message = error_template.format(error=str(e))
            return self._create_response(language, error_message, is_error=True)

    async def _handle_parameter_control(self, text: str, text_lower: str, global_config: dict):
        """处理全局参数控制命令"""
        import re

        param_keywords = global_config.get('param_keywords', [])

        # 检查是否包含参数控制关键词
        has_param_keyword = any(keyword in text_lower for keyword in param_keywords)

        # 检查是否包含直接参数模式（参数类型+数值，如"亮度50%"）
        brightness_keywords = global_config.get('brightness_keywords', [])
        color_keywords = global_config.get('color_keywords', [])
        volume_keywords = global_config.get('volume_keywords', [])
        position_keywords = global_config.get('position_keywords', [])
        speed_keywords = global_config.get('fan_speed_keywords', [])
        temp_keywords = global_config.get('temperature_keywords', [])

        # 检查是否有参数类型关键词+数值模式
        has_direct_param = False
        if any(keyword in text_lower for keyword in brightness_keywords) and re.search(r'(\d{1,3})\s*%?', text):
            has_direct_param = True
        elif any(keyword in text_lower for keyword in volume_keywords) and re.search(r'(\d{1,3})\s*%?', text):
            has_direct_param = True
        elif any(keyword in text_lower for keyword in position_keywords) and re.search(r'(\d{1,3})\s*%?', text):
            has_direct_param = True
        elif any(keyword in text_lower for keyword in speed_keywords) and re.search(r'(\d{1,3})\s*%?', text):
            has_direct_param = True
        elif any(keyword in text_lower for keyword in color_keywords) and any(color in text for color in ['红色', '蓝色', '绿色', '黄色', '白色', '黑色', '紫色', '橙色']):
            has_direct_param = True
        elif any(keyword in text_lower for keyword in temp_keywords) and re.search(r'(\d{1,2})\s*度', text_lower):
            has_direct_param = True

        # 检查亮度抱怨（太亮了/太暗了）
        brightness_complaint_config = global_config.get('brightness_complaint', {})
        if brightness_complaint_config:
            hot_keywords = brightness_complaint_config.get('hot_keywords', [])
            cold_keywords = brightness_complaint_config.get('cold_keywords', [])
            if any(keyword in text_lower for keyword in hot_keywords + cold_keywords):
                has_direct_param = True

        # 如果既没有参数关键词也没有直接参数模式，则不处理
        if not has_param_keyword and not has_direct_param:
            return None

        _LOGGER.debug(f"参数控制检测: has_keyword={has_param_keyword}, has_direct_param={has_direct_param}")

        # 解析区域
        area_names = []
        areas_config = None
        try:
            if _INTENTS_CONFIG and 'lists' in _INTENTS_CONFIG:
                areas_config = _INTENTS_CONFIG['lists'].get('area_names', {}).get('values', [])
        except:
            pass

        if areas_config:
            for area in areas_config:
                if area in text_lower:
                    area_names.append(area)

        area_text = area_names[0] if area_names else global_config.get('default_area_name', '全屋')
        is_global_control = not area_names

        # 参数范围配置
        param_ranges = global_config.get('parameter_ranges', {})

        # 温度控制
        temp_keywords = global_config.get('temperature_keywords', [])
        if any(keyword in text_lower for keyword in temp_keywords):
            # 智能解析温度意图
            temp_result = await self._parse_temperature_intent(text_lower, area_names, global_config)
            if temp_result:
                return temp_result

        # 亮度控制
        brightness_keywords = global_config.get('brightness_keywords', [])
        if any(keyword in text_lower for keyword in brightness_keywords):
            brightness_config = param_ranges.get('brightness', {})
            brightness_match = re.search(brightness_config.get('pattern', r'(\d{1,3})\s*%?'), text)
            if brightness_match:
                brightness = int(brightness_match.group(1))
                brightness_min = brightness_config.get('min', 0)
                brightness_max = brightness_config.get('max', 100)
                if brightness_min <= brightness <= brightness_max:
                    return await self._control_light_brightness(area_names, is_global_control, brightness)

        # 亮度抱怨处理（如"太亮了"、"太暗了"）
        brightness_complaint_config = global_config.get('brightness_complaint', {})
        if brightness_complaint_config:
            hot_keywords = brightness_complaint_config.get('hot_keywords', [])
            cold_keywords = brightness_complaint_config.get('cold_keywords', [])

            if any(keyword in text_lower for keyword in hot_keywords + cold_keywords):
                # 智能解析亮度抱怨意图
                brightness_result = await self._parse_brightness_intent(text_lower, area_names, global_config)
                if brightness_result:
                    return brightness_result

        # 颜色控制
        color_keywords = global_config.get('color_keywords', [])
        if any(keyword in text_lower for keyword in color_keywords):
            color_values = global_config.get('color_values', {})
            for chinese_color, english_color in color_values.items():
                if chinese_color in text:
                    return await self._control_light_color(area_names, is_global_control, english_color, chinese_color)

        # 音量控制
        volume_keywords = global_config.get('volume_keywords', [])
        if any(keyword in text_lower for keyword in volume_keywords):
            volume_config = param_ranges.get('volume', {})
            volume_match = re.search(volume_config.get('pattern', r'(\d{1,3})\s*%?'), text)
            if volume_match:
                volume = int(volume_match.group(1))
                volume_min = volume_config.get('min', 0)
                volume_max = volume_config.get('max', 100)
                if volume_min <= volume <= volume_max:
                    return await self._control_media_volume(area_names, is_global_control, volume)

        # 窗帘位置控制
        cover_keywords = global_config.get('cover_position_keywords', [])
        if any(keyword in text_lower for keyword in cover_keywords):
            position_config = param_ranges.get('position', {})
            position_match = re.search(position_config.get('pattern', r'(\d{1,3})\s*%?'), text)
            if position_match:
                position = int(position_match.group(1))
                position_min = position_config.get('min', 0)
                position_max = position_config.get('max', 100)
                if position_min <= position <= position_max:
                    # 智能解析窗帘位置意图
                    position_intent = self._parse_cover_position_intent(text_lower, position)
                    return await self._control_cover_position(area_names, is_global_control, position_intent)

        # 风扇速度控制
        fan_speed_keywords = global_config.get('fan_speed_keywords', [])
        if any(keyword in text_lower for keyword in fan_speed_keywords):
            speed_config = param_ranges.get('speed', {})
            speed_match = re.search(speed_config.get('pattern', r'(\d{1,3})\s*%?'), text)
            if speed_match:
                speed = int(speed_match.group(1))
                speed_min = speed_config.get('min', 0)
                speed_max = speed_config.get('max', 100)
                if speed_min <= speed <= speed_max:
                    return await self._control_fan_speed(area_names, is_global_control, speed)

        return None

    async def _parse_brightness_intent(self, text_lower: str, area_names, global_config):
        """智能解析亮度意图"""
        import re

        brightness_complaint_config = global_config.get('brightness_complaint', {})
        if not brightness_complaint_config:
            return None

        # 检查是否是亮度抱怨
        hot_keywords = brightness_complaint_config.get('hot_keywords', [])  # 太亮了
        cold_keywords = brightness_complaint_config.get('cold_keywords', [])  # 太暗了

        is_global_control = not area_names

        if any(keyword in text_lower for keyword in hot_keywords):
            # 太亮了，调暗
            default_brightness = brightness_complaint_config.get('default_brightness', {})
            target_brightness = default_brightness.get('hot_recommendation', 30)
            return await self._control_light_brightness(area_names, is_global_control, target_brightness)

        elif any(keyword in text_lower for keyword in cold_keywords):
            # 太暗了，调亮
            default_brightness = brightness_complaint_config.get('default_brightness', {})
            target_brightness = default_brightness.get('cold_recommendation', 70)
            return await self._control_light_brightness(area_names, is_global_control, target_brightness)

        return None

    async def _parse_temperature_intent(self, text_lower: str, area_names, global_config):
        """智能解析温度意图"""
        import re

        # 1. 检查是否是温度调节请求（有具体数值）
        temp_config = global_config.get('parameter_ranges', {}).get('temperature', {})
        temp_match = re.search(temp_config.get('pattern', r'(\d{1,2})\s*度'), text_lower)
        if temp_match:
            temperature = int(temp_match.group(1))
            temperature_config = global_config.get('temperature', {})
            temp_min = temp_config.get('min', temperature_config.get('min_temperature', 16))
            temp_max = temp_config.get('max', temperature_config.get('max_temperature', 30))
            if temp_min <= temperature <= temp_max:
                is_global_control = not area_names
                return await self._control_climate_temperature(area_names, is_global_control, temperature)

        # 2. 检查是否是温度抱怨或状态描述
        temperature_config = global_config.get('temperature', {})
        hot_keywords = temperature_config.get('hot_keywords', [])
        cold_keywords = temperature_config.get('cold_keywords', [])
        if any(keyword in text_lower for keyword in hot_keywords + cold_keywords):
            return await self._handle_temperature_complaint(text_lower, area_names, global_config)

        # 3. 检查是否是空调/风扇控制请求
        hvac_modes = global_config.get('hvac_modes', {})
        climate_keywords = []
        for mode_data in hvac_modes.values():
            climate_keywords.extend(mode_data.get('keywords', []))
        if any(keyword in text_lower for keyword in climate_keywords):
            return await self._handle_climate_mode_request(text_lower, area_names, global_config)

        return None

    async def _handle_temperature_complaint(self, text_lower: str, area_names, global_config):
        """处理温度抱怨，自动推荐合适的操作"""
        is_global_control = not area_names

        # 获取可用的空调设备
        climate_devices = await self._get_devices_by_domain(['climate'], area_names, is_global_control)
        if not climate_devices:
            error_messages = global_config.get('error_messages', {})
            return self._create_response(
                "zh-CN",
                error_messages.get('no_climate_devices', "这个区域没有找到空调设备，无法调节温度")
            )

        # 检测用户意图（太热还是太冷）
        temperature_config = global_config.get('temperature', {})
        hot_keywords = temperature_config.get('hot_keywords', [])
        cold_keywords = temperature_config.get('cold_keywords', [])
        default_temps = temperature_config.get('default_temperatures', {})

        is_hot = any(keyword in text_lower for keyword in hot_keywords)
        is_cold = any(keyword in text_lower for keyword in cold_keywords)

        # 智能推荐操作
        if is_hot:
            # 太热了，推荐开启制冷
            hvac_modes = global_config.get('hvac_modes', {})
            cooling_mode = hvac_modes.get('cooling', {}).get('name', '制冷')
            return await self._smart_climate_control(area_names, is_global_control, climate_devices, cooling_mode)
        elif is_cold:
            # 太冷了，推荐开启制热
            hvac_modes = global_config.get('hvac_modes', {})
            heating_mode = hvac_modes.get('heating', {}).get('name', '制热')
            return await self._smart_climate_control(area_names, is_global_control, climate_devices, heating_mode)
        else:
            # 模糊的温度描述，询问用户具体需求
            return await self._ask_climate_preference(area_names, is_global_control, climate_devices)

    async def _handle_climate_mode_request(self, text_lower: str, area_names, global_config):
        """处理空调模式请求"""
        is_global_control = not area_names

        # 获取可用的空调设备
        climate_devices = await self._get_devices_by_domain(['climate'], area_names, is_global_control)
        if not climate_devices:
            error_messages = global_config.get('error_messages', {})
            return self._create_response(
                "zh-CN",
                error_messages.get('no_climate_devices', "这个区域没有找到空调设备")
            )

        # 解析空调模式
        hvac_modes = global_config.get('hvac_modes', {})
        mode = None
        for mode_key, mode_data in hvac_modes.items():
            keywords = mode_data.get('keywords', [])
            if any(keyword in text_lower for keyword in keywords):
                mode = mode_data.get('name', mode_key)
                break

        if not mode:
            return await self._ask_climate_mode_preference(area_names, is_global_control, climate_devices)

        return await self._smart_climate_control(area_names, is_global_control, climate_devices, mode)

    async def _smart_climate_control(self, area_names, is_global_control, climate_devices, mode):
        """智能空调控制"""
        try:
            # 获取设备友好名称
            device_names = [self._get_device_friendly_name(device_id) for device_id in climate_devices]

            if len(climate_devices) == 1:
                # 只有一个设备，直接操作
                device_id = climate_devices[0]
                device_name = device_names[0]

                service_data = {
                    'entity_id': device_id,
                }

                # 根据模式设置相应的参数
                hvac_modes = global_config.get('hvac_modes', {})
                service_parameter = None
                for mode_key, mode_data in hvac_modes.items():
                    if mode_data.get('name') == mode:
                        service_parameter = mode_data.get('service_parameter', mode_key)
                        break

                if service_parameter:
                    service_data['hvac_mode'] = service_parameter

                await self.hass.services.async_call('climate', 'set_hvac_mode', service_data)

                area_text = area_names[0] if area_names else self._get_default_area_name()
                device_selection_templates = global_config.get('device_selection_templates', {})
                # 使用默认模板配置，避免硬编码
                default_templates = global_config.get('default_message_templates', {})
                message_template = device_selection_templates.get('single_device',
                    default_templates.get('device_single_device', "已将{area}{device_name}调至{mode}模式"))
                message = message_template.format(area=area_text, device_name=device_name, mode=mode)
                return self._create_response("zh-CN", message)

            else:
                # 多个设备，询问用户选择
                device_list = "、".join(device_names)
                area_text = area_names[0] if area_names else self._get_default_area_name()
                device_selection_templates = global_config.get('device_selection_templates', {})

                if len(climate_devices) <= 3:
                    message_template = device_selection_templates.get('multiple_devices_few', "{area}找到{count}个空调设备：{device_list}。请问您想控制哪一个？")
                    message = message_template.format(area=area_text, count=len(climate_devices), device_list=device_list)
                else:
                    message_template = device_selection_templates.get('multiple_devices_many', "{area}找到{count}个空调设备，包括：{device_list}等。请告诉我具体设备名称。")
                    # 截取前3个设备名称
                    limited_list = device_list.split('、')[:3]
                    message = message_template.format(area=area_text, count=len(climate_devices), device_list="、".join(limited_list))

                return self._create_response("zh-CN", message)

        except Exception as e:
            return self._create_error_response("error", str(e))

    async def _ask_climate_preference(self, area_names, is_global_control, climate_devices):
        """询问用户温度调节偏好"""
        global_config = self.local_config.get('GlobalDeviceControl', {})
        device_names = [self._get_device_friendly_name(device_id) for device_id in climate_devices]
        area_text = area_names[0] if area_names else self._get_default_area_name()
        device_selection_templates = global_config.get('device_selection_templates', {})

        if len(climate_devices) <= 2:
            device_list = "、".join(device_names)
            message_template = device_selection_templates.get('temperature_preference_single', "我注意到您提到温度问题。{area}有空调设备：{device_list}。请问您是觉得太热了还是太冷了？")
            message = message_template.format(area=area_text, device_list=device_list)
        else:
            message_template = device_selection_templates.get('temperature_preference_general', "我注意到您提到温度问题。请问您是觉得太热了还是太冷了？")
            message = message_template

        return self._create_response("zh-CN", message)

    async def _ask_climate_mode_preference(self, area_names, is_global_control, climate_devices):
        """询问用户空调模式偏好"""
        global_config = self.local_config.get('GlobalDeviceControl', {})
        device_names = [self._get_device_friendly_name(device_id) for device_id in climate_devices]
        area_text = area_names[0] if area_names else self._get_default_area_name()
        device_selection_templates = global_config.get('device_selection_templates', {})

        if len(climate_devices) <= 2:
            device_list = "、".join(device_names)
            message_template = device_selection_templates.get('mode_preference_single', "{area}有空调设备：{device_list}。请问您需要制冷、制热、除湿还是送风模式？")
            message = message_template.format(area=area_text, device_list=device_list)
        else:
            message_template = device_selection_templates.get('mode_preference_general', "请问您需要空调的哪种模式：制冷、制热、除湿还是送风？")
            message = message_template

        return self._create_response("zh-CN", message)

    def _parse_cover_position_intent(self, text_lower: str, position: int) -> int:
        """智能解析窗帘位置意图

        Home Assistant窗帘位置逻辑：
        - position=0: 完全关闭
        - position=100: 完全打开

        用户表达习惯：
        - "开到50%" → position=50 (打开到50%)
        - "关到50%" → position=50 (关闭到50%开度，即50%打开)
        - "调到50%" → position=50 (调整到50%)
        """
        global_config = self.local_config.get('GlobalDeviceControl', {})
        cover_keywords = global_config.get('cover_position_keywords_detailed', {})

        open_keywords = cover_keywords.get('open_keywords', ["开到", "升到", "打开"])
        close_keywords = cover_keywords.get('close_keywords', ["关到", "降到", "关闭"])

        # 如果明确说了"开到"，直接使用原值
        if any(keyword in text_lower for keyword in open_keywords):
            return position

        # 如果明确说了"关到"，也使用原值（因为用户意思是"关到50%开度"）
        if any(keyword in text_lower for keyword in close_keywords):
            return position

        # 其他情况（调到、设置等），直接使用原值
        return position

    async def _control_climate_temperature(self, area_names, is_global_control, temperature):
        """控制空调温度"""
        try:
            global_config = self.local_config.get('GlobalDeviceControl', {})
            domain_services = global_config.get('domain_services', {})
            service_name = domain_services.get('climate', {}).get('set_temperature', 'set_temperature')

            devices = await self._get_devices_by_domain(['climate'], area_names, is_global_control)
            if not devices:
                _LOGGER.info(f"未找到climate设备，交由LLM处理。区域: {area_names}, 全局: {is_global_control}")
                return None

            success_count = 0
            error_count = 0

            for device_id in devices:
                try:
                    await self.hass.services.async_call('climate', service_name, {
                        'entity_id': device_id,
                        'temperature': temperature
                    })
                    success_count += 1
                except Exception as e:
                    _LOGGER.debug(f"设置空调温度失败 {device_id}: {e}")
                    error_count += 1

            area_text = area_names[0] if area_names else self._get_default_area_name()
            param_ranges = global_config.get('parameter_ranges', {})
            temp_config = param_ranges.get('temperature', {})
            unit = temp_config.get('unit', '度')
            responses = global_config.get('responses', {})
            message_template = responses.get('success_temperature', "已将{area}温度设置为{temperature}度")
            message = message_template.format(area=area_text, temperature=temperature)
            if error_count > 0:
                message += self._format_error_suffix(error_count)

            return self._create_response("zh-CN", message)

        except Exception as e:
            return self._create_error_response("error", str(e))

    async def _control_light_brightness(self, area_names, is_global_control, brightness):
        """控制灯光亮度"""
        try:
            global_config = self.local_config.get('GlobalDeviceControl', {})
            domain_services = global_config.get('domain_services', {})
            service_name = domain_services.get('light', {}).get('set_brightness', 'turn_on')

            devices = await self._get_devices_by_domain(['light'], area_names, is_global_control)
            if not devices:
                _LOGGER.info(f"未找到light设备进行亮度控制，交由LLM处理。区域: {area_names}, 全局: {is_global_control}")
                return None

            success_count = 0
            error_count = 0

            param_ranges = global_config.get('parameter_ranges', {})
            brightness_config = param_ranges.get('brightness', {})
            conversion_target = brightness_config.get('conversion_target', 'direct')

            if conversion_target == '0-255':
                conversion_factor = brightness_config.get('conversion_factor', 2.54)
                brightness_value = int(brightness * conversion_factor)
            else:
                brightness_value = brightness

            for device_id in devices:
                try:
                    service_data = {'entity_id': device_id}
                    if conversion_target == '0-255':
                        service_data['brightness'] = brightness_value
                    else:
                        service_data['brightness_pct'] = brightness

                    await self.hass.services.async_call('light', service_name, service_data)
                    success_count += 1
                except Exception as e:
                    _LOGGER.debug(f"设置灯光亮度失败 {device_id}: {e}")
                    error_count += 1

            area_text = area_names[0] if area_names else self._get_default_area_name()
            param_config = param_ranges.get('brightness', {})
            unit = param_config.get('unit', '%')
            responses = global_config.get('responses', {})
            # 使用默认模板配置，避免硬编码
            default_templates = global_config.get('default_message_templates', {})
            message_template = responses.get('success_brightness',
                default_templates.get('success_brightness', "已将{area}{device}亮度调至{brightness}%"))
            default_device_names = global_config.get('default_device_names', {})
            device_name = default_device_names.get('light', '灯光')
            message = message_template.format(area=area_text, device=device_name, brightness=brightness, unit=unit)
            if error_count > 0:
                message += self._format_error_suffix(error_count)

            return self._create_response("zh-CN", message)

        except Exception as e:
            return self._create_error_response("error", str(e))

    async def _control_light_color(self, area_names, is_global_control, color_english, color_chinese):
        """控制灯光颜色"""
        try:
            global_config = self.local_config.get('GlobalDeviceControl', {})
            domain_services = global_config.get('domain_services', {})
            service_name = domain_services.get('light', {}).get('set_color', 'turn_on')

            devices = await self._get_devices_by_domain(['light'], area_names, is_global_control)
            if not devices:
                _LOGGER.info(f"未找到light设备进行颜色控制，交由LLM处理。区域: {area_names}, 全局: {is_global_control}")
                return None

            success_count = 0
            error_count = 0

            # 从配置获取RGB值
            color_rgb_values = global_config.get('color_rgb_values', {})
            rgb_color = color_rgb_values.get(color_english, [255, 255, 255])

            for device_id in devices:
                try:
                    await self.hass.services.async_call('light', service_name, {
                        'entity_id': device_id,
                        'rgb_color': rgb_color
                    })
                    success_count += 1
                except Exception as e:
                    _LOGGER.debug(f"设置灯光颜色失败 {device_id}: {e}")
                    error_count += 1

            area_text = area_names[0] if area_names else self._get_default_area_name()
            default_device_names = global_config.get('default_device_names', {})
            device_name = default_device_names.get('light', '灯光')
            responses = global_config.get('responses', {})
            message_template = responses.get('success_color', "已将{area}{device}颜色设置为{color}")
            message = message_template.format(area=area_text, device=device_name, color=color_chinese)
            message += self._format_error_suffix(error_count)

            return self._create_response("zh-CN", message)

        except Exception as e:
            return self._create_error_response("error", str(e))

    async def _control_media_volume(self, area_names, is_global_control, volume):
        """控制媒体设备音量"""
        try:
            global_config = self.local_config.get('GlobalDeviceControl', {})
            domain_services = global_config.get('domain_services', {})
            service_name = domain_services.get('media_player', {}).get('set_volume', 'volume_set')

            devices = await self._get_devices_by_domain(['media_player'], area_names, is_global_control)
            if not devices:
                _LOGGER.info(f"未找到media_player设备进行音量控制，交由LLM处理。区域: {area_names}, 全局: {is_global_control}")
                return None

            success_count = 0
            error_count = 0

            param_ranges = global_config.get('parameter_ranges', {})
            volume_config = param_ranges.get('volume', {})
            conversion_target = volume_config.get('conversion_target', 'direct')

            if conversion_target == '0-1':
                conversion_factor = volume_config.get('conversion_factor', 0.01)
                volume_value = volume * conversion_factor
            else:
                volume_value = volume

            for device_id in devices:
                try:
                    await self.hass.services.async_call('media_player', service_name, {
                        'entity_id': device_id,
                        'volume_level': volume_value
                    })
                    success_count += 1
                except Exception as e:
                    _LOGGER.debug(f"设置音量失败 {device_id}: {e}")
                    error_count += 1

            area_text = area_names[0] if area_names else self._get_default_area_name()
            param_config = param_ranges.get('volume', {})
            unit = param_config.get('unit', '%')
            responses = global_config.get('responses', {})
            # 使用默认模板配置，避免硬编码
            default_templates = global_config.get('default_message_templates', {})
            message_template = responses.get('success_volume',
                default_templates.get('success_volume', "已将{area}{device}音量调至{volume}%"))
            default_device_names = global_config.get('default_device_names', {})
            device_name = default_device_names.get('media_player', '媒体设备')
            message = message_template.format(area=area_text, device=device_name, volume=volume, unit=unit)
            if error_count > 0:
                message += self._format_error_suffix(error_count)

            return self._create_response("zh-CN", message)

        except Exception as e:
            return self._create_error_response("error", str(e))

    async def _control_cover_position(self, area_names, is_global_control, position):
        """控制窗帘位置"""
        try:
            global_config = self.local_config.get('GlobalDeviceControl', {})
            domain_services = global_config.get('domain_services', {})
            service_name = domain_services.get('cover', {}).get('set_position', 'set_cover_position')

            devices = await self._get_devices_by_domain(['cover'], area_names, is_global_control)
            if not devices:
                _LOGGER.info(f"未找到cover设备进行位置控制，交由LLM处理。区域: {area_names}, 全局: {is_global_control}")
                return None

            success_count, error_count, failed_devices = await self._execute_device_operations(
                devices, 'cover', service_name, {'position': position}
            )

            area_text = area_names[0] if area_names else self._get_default_area_name()
            param_ranges = global_config.get('parameter_ranges', {})
            param_config = param_ranges.get('position', {})
            unit = param_config.get('unit', '%')

            fail_msg = self._format_failure_message(error_count, failed_devices)
            responses = global_config.get('responses', {})
            # 使用默认模板配置，避免硬编码
            default_templates = global_config.get('default_message_templates', {})
            message_template = responses.get('success_cover_position',
                default_templates.get('success_cover_position', "已将{area}{device}位置调至{position}%"))
            default_device_names = global_config.get('default_device_names', {})
            device_name = default_device_names.get('cover', '窗帘')
            message = message_template.format(area=area_text, device=device_name, position=position, unit=unit) + fail_msg

            return self._create_response("zh-CN", message)

        except Exception as e:
            return self._create_error_response("error", str(e))

    async def _control_fan_speed(self, area_names, is_global_control, speed):
        """控制风扇速度"""
        try:
            global_config = self.local_config.get('GlobalDeviceControl', {})
            domain_services = global_config.get('domain_services', {})
            service_name = domain_services.get('fan', {}).get('set_speed', 'set_speed')

            devices = await self._get_devices_by_domain(['fan'], area_names, is_global_control)
            if not devices:
                _LOGGER.info(f"未找到fan设备进行风速控制，交由LLM处理。区域: {area_names}, 全局: {is_global_control}")
                return None

            success_count = 0
            error_count = 0

            param_ranges = global_config.get('parameter_ranges', {})
            speed_config = param_ranges.get('speed', {})
            conversion_target = speed_config.get('conversion_target', 'direct')

            if conversion_target == 'speed_levels':
                speed_value = self._convert_speed_to_level(speed, global_config)
            else:
                speed_value = speed

            for device_id in devices:
                try:
                    await self.hass.services.async_call('fan', service_name, {
                        'entity_id': device_id,
                        'speed': speed_value
                    })
                    success_count += 1
                except Exception as e:
                    _LOGGER.debug(f"设置风扇速度失败 {device_id}: {e}")
                    error_count += 1

            area_text = area_names[0] if area_names else self._get_default_area_name()
            param_config = param_ranges.get('speed', {})
            unit = param_config.get('unit', '%')
            responses = global_config.get('responses', {})
            # 使用默认模板配置，避免硬编码
            default_templates = global_config.get('default_message_templates', {})
            message_template = responses.get('success_fan_speed',
                default_templates.get('success_fan_speed', "已将{area}{device}风速调至{speed}%"))
            default_device_names = global_config.get('default_device_names', {})
            device_name = default_device_names.get('fan', '风扇')
            message = message_template.format(area=area_text, device=device_name, speed=speed, unit=unit)
            if error_count > 0:
                message += self._format_error_suffix(error_count)

            return self._create_response("zh-CN", message)

        except Exception as e:
            return self._create_error_response("error", str(e))

    async def _get_devices_by_domain(self, domains, area_names, is_global_control):
        """根据域和区域获取设备列表"""
        all_devices = []

        if is_global_control:
            # 全局控制：获取所有域的设备
            for domain in domains:
                try:
                    devices = self.hass.states.async_entity_ids(domain)
                    # 过滤掉明显的错误设备（如light域的设备被误标为cover）
                    filtered_devices = [d for d in devices if self._is_valid_device_for_domain(d, domain)]
                    all_devices.extend(filtered_devices)
                    _LOGGER.debug(f"获取 {domain} 设备: {len(filtered_devices)} 个")
                except Exception as e:
                    _LOGGER.debug(f"获取 {domain} 设备失败: {e}")
        else:
            # 区域控制：获取指定区域的设备
            try:
                from homeassistant.helpers import entity_registry as er
                registry = er.async_get(self.hass)
                for domain in domains:
                    try:
                        domain_devices = self.hass.states.async_entity_ids(domain)
                        for device_id in domain_devices:
                            try:
                                # 验证设备域名的正确性
                                if not self._is_valid_device_for_domain(device_id, domain):
                                    _LOGGER.debug(f"跳过不匹配的设备: {device_id} (期望域: {domain})")
                                    continue

                                entity_entry = registry.async_get(device_id)
                                if entity_entry and entity_entry.area_id:
                                    area_entry = registry.async_get_area(entity_entry.area_id)
                                    if area_entry and self._match_area_name(area_entry.name, area_entry.name, area_names):
                                        all_devices.append(device_id)
                                        _LOGGER.debug(f"找到匹配设备: {device_id} 在区域 {area_entry.name} (匹配关键词: {area_names})")
                            except Exception as e:
                                _LOGGER.debug(f"处理设备 {device_id} 失败: {e}")
                                continue
                    except Exception as e:
                        _LOGGER.debug(f"获取 {domain} 区域设备失败: {e}")
            except Exception as e:
                _LOGGER.debug(f"获取实体注册表失败: {e}")
                # 回退到全局控制
                for domain in domains:
                    try:
                        devices = self.hass.states.async_entity_ids(domain)
                        filtered_devices = [d for d in devices if self._is_valid_device_for_domain(d, domain)]
                        all_devices.extend(filtered_devices)
                    except Exception as e:
                        _LOGGER.debug(f"获取 {domain} 设备失败: {e}")

        # 获取去重配置
        global_config = self.local_config.get('GlobalDeviceControl', {})
        dedup_config = global_config.get('device_deduplication', {})
        deduplication_enabled = dedup_config.get('enabled', True)
        log_duplicates = dedup_config.get('log_duplicates', True)

        if not deduplication_enabled:
            # 如果禁用去重，直接返回原始列表
            _LOGGER.info(f"获取设备列表 ({len(domains)} 域): {len(all_devices)} 个设备 (去重已禁用)")
            return all_devices

        # 去重处理：移除重复的设备ID
        unique_devices = []
        seen_devices = set()
        duplicates_found = []

        for device_id in all_devices:
            if device_id not in seen_devices:
                seen_devices.add(device_id)
                unique_devices.append(device_id)
            else:
                duplicates_found.append(device_id)

        # 记录重复设备信息
        if log_duplicates and duplicates_found:
            _LOGGER.warning(f"发现并移除 {len(duplicates_found)} 个重复设备: {duplicates_found}")

        _LOGGER.info(f"最终获取设备列表 ({len(domains)} 域): 原始 {len(all_devices)} 个，去重后 {len(unique_devices)} 个设备")
        if log_duplicates and unique_devices != all_devices:
            _LOGGER.debug(f"去重后设备列表详情: {unique_devices}")

        return unique_devices

    def _is_valid_device_for_domain(self, device_id: str, expected_domain: str) -> bool:
        """验证设备是否属于期望的域"""
        # 基础检查：设备ID必须以域名开头
        if not device_id.startswith(f"{expected_domain}."):
            _LOGGER.debug(f"设备ID前缀不匹配: {device_id} (期望域: {expected_domain})")
            return False

        # 特殊检查：防止将灯光设备误认为窗帘
        device_name = device_id.split('.', 1)[1].lower()
        global_config = self.local_config.get('GlobalDeviceControl', {})
        domain_validation = global_config.get('domain_validation', {})

        # 如果期望是cover域，但设备名包含light关键词，很可能是错误分类
        if expected_domain == 'cover':
            light_indicators = domain_validation.get('light_indicators', ['light', '灯', 'lamp', 'bulb'])
            if any(indicator in device_name for indicator in light_indicators):
                _LOGGER.debug(f"疑似错误分类: 灯光设备 {device_id} 被归类为cover")
                return False

        # 如果期望是light域，但设备名包含cover关键词，也很可能是错误分类
        if expected_domain == 'light':
            cover_indicators = domain_validation.get('cover_indicators', ['cover', 'curtain', 'blind', 'shade', '窗帘', '百叶'])
            if any(indicator in device_name for indicator in cover_indicators):
                _LOGGER.debug(f"疑似错误分类: 窗帘设备 {device_id} 被归类为light")
                return False

        return True

    async def _execute_device_operations(self, devices, domain, service_name, service_data=None):
        """执行批量设备操作并返回详细结果"""
        if service_data is None:
            service_data = {}

        success_count = 0
        error_count = 0
        failed_devices = []

        for device_id in devices:
            try:
                # 检查设备是否支持该服务
                if not self._device_supports_service(device_id, domain, service_name):
                    _LOGGER.debug(f"设备 {device_id} 不支持服务 {domain}.{service_name}，跳过")
                    device_name = self._get_device_friendly_name(device_id)
                    failed_devices.append(f"{device_name} (不支持该操作)")
                    error_count += 1
                    continue

                service_data['entity_id'] = device_id
                await self.hass.services.async_call(domain, service_name, service_data)
                success_count += 1
            except Exception as e:
                global_config = self.local_config.get('GlobalDeviceControl', {})
                log_levels = global_config.get('log_levels', {})
                level = log_levels.get('device_operation_failed', 'warning')
                if level == 'debug':
                    _LOGGER.debug(f"控制设备 {device_id} 失败: {e}")
                elif level == 'warning':
                    _LOGGER.warning(f"控制设备 {device_id} 失败: {e}")
                error_count += 1
                # 记录失败设备的友好名称
                device_name = self._get_device_friendly_name(device_id)
                failed_devices.append(device_name)

        return success_count, error_count, failed_devices

    def _match_area_name(self, area_name: str, area_id: str, target_areas: list) -> bool:
        """简化版区域匹配，只使用有效的策略"""
        try:
            # 策略1：精确匹配
            if area_name in target_areas:
                return True

            # 策略2：大小写不敏感匹配
            area_name_lower = area_name.lower()
            target_areas_lower = [area.lower() for area in target_areas]
            if area_name_lower in target_areas_lower:
                return True

            # 策略3：包含关系匹配
            for target_area in target_areas:
                if target_area in area_name or area_name in target_area:
                    return True

            return False

        except Exception:
            return False

    def _device_supports_service(self, device_id: str, domain: str, service_name: str) -> bool:
        """检查设备是否支持指定的服务"""
        try:
            # 获取设备状态对象
            from homeassistant.core import State
            state = self.hass.states.get(device_id)
            if not state:
                return False

            # 获取设备的实体注册信息
            from homeassistant.helpers import entity_registry as er
            registry = er.async_get(self.hass)
            entity_entry = registry.async_get(device_id)

            # 如果有实体注册信息，检查supported_features
            if entity_entry and hasattr(entity_entry, 'supported_features'):
                supported_features = entity_entry.supported_features or 0

                # 根据域和服务类型检查支持性
                if domain == 'climate':
                    # climate域的特定服务支持检查
                    if service_name in ['turn_on', 'turn_off']:
                        # 检查是否支持开关功能 (climate ClimateEntityFeature.TURN_ON_OFF = 1)
                        return bool(supported_features & 1)  # ClimateEntityFeature.TURN_ON_OFF
                    elif service_name in ['set_temperature', 'set_hvac_mode', 'set_fan_mode']:
                        return True  # 大部分climate设备都支持基本功能

                elif domain == 'media_player':
                    # media_player域的服务支持检查
                    if service_name in ['volume_set', 'volume_mute', 'media_play', 'media_pause', 'media_stop']:
                        return True  # 大部分media_player都支持基本功能

                elif domain == 'light':
                    # light域服务支持检查
                    if service_name in ['turn_on', 'turn_off', 'toggle']:
                        return True  # 所有lights都支持开关
                    elif service_name in ['set_brightness', 'set_color']:
                        # 检查是否支持亮度和颜色功能
                        return bool(supported_features & 0b11)  # LightEntityFeature.BRIGHTNESS | COLOR

            # 如果无法从supported_features判断，使用Home Assistant的服务支持检查
            # 这是一个备用方案，通过检查服务是否存在该域的支持函数
            try:
                service_handler = self.hass.services.get(domain, service_name)
                if service_handler:
                    # 服务存在，进一步检查是否有支持检查函数
                    if hasattr(service_handler, 'schema') and service_handler.schema:
                        # 检查schema是否需要entity_id参数（大部分设备服务都需要）
                        schema_fields = getattr(service_handler.schema, 'schema', {})
                        if isinstance(schema_fields, dict) and 'entity_id' in schema_fields:
                            return True
                    return True  # 服务存在就假设支持
            except Exception:
                pass

            # 最后的备用方案：基于域和服务的常见支持情况
            common_supported_services = {
                'light': ['turn_on', 'turn_off', 'toggle'],
                'switch': ['turn_on', 'turn_off', 'toggle'],
                'fan': ['turn_on', 'turn_off', 'toggle', 'set_speed'],
                'cover': ['open_cover', 'close_cover', 'stop_cover', 'set_cover_position'],
                'lock': ['lock', 'unlock'],
                'vacuum': ['start', 'pause', 'stop', 'return_to_base'],
                'climate': ['set_temperature', 'set_hvac_mode', 'set_fan_mode'],  # 不包括turn_on/turn_off
                'media_player': ['media_play', 'media_pause', 'media_stop', 'volume_set'],
                'valve': ['open_valve', 'close_valve', 'set_valve_position'],
            }

            return service_name in common_supported_services.get(domain, [])

        except Exception as e:
            _LOGGER.debug(f"检查设备服务支持时出错 {device_id}: {e}")
            # 出错时保守处理，返回True让服务调用时自然报错
            return True

    def _format_failure_message(self, error_count, failed_devices):
        """格式化失败消息"""
        if error_count == 0:
            return ""

        global_config = self.local_config.get('GlobalDeviceControl', {})
        failure_config = global_config.get('failure_message', {})
        max_devices = failure_config.get('max_devices_list', 3)

        # 去重失败设备列表，防止显示重复的设备名称
        unique_failed_devices = []
        seen_devices = set()

        for device_name in failed_devices:
            if device_name not in seen_devices:
                seen_devices.add(device_name)
                unique_failed_devices.append(device_name)

        # 调整错误计数以反映唯一的失败设备数
        unique_error_count = len(unique_failed_devices)

        if unique_error_count <= max_devices:
            # 如果失败设备较少，列出所有失败设备
            failed_list = "、".join(unique_failed_devices)
            template = failure_config.get('few_devices', "，但以下{error_count}个设备失败：{failed_list}")
            return template.format(error_count=unique_error_count, failed_list=failed_list)
        else:
            # 如果失败设备较多，列出前N个并说明总数
            failed_list = "、".join(unique_failed_devices[:max_devices])
            template = failure_config.get('many_devices', "，但{error_count}个设备失败，包括：{failed_list}等")
            return template.format(error_count=unique_error_count, failed_list=failed_list)

    def _get_device_friendly_name(self, device_id: str) -> str:
        """获取设备的友好名称"""
        try:
            global_config = self.local_config.get('GlobalDeviceControl', {})
            device_name_mappings = global_config.get('device_name_mappings', {})

            # 首先检查特殊设备映射
            special_mappings = device_name_mappings.get('special_mappings', {})
            if device_id in special_mappings:
                return special_mappings[device_id]

            # 然后检查模式匹配
            patterns = device_name_mappings.get('patterns', {})
            domain = device_id.split('.')[0] if '.' in device_id else ''
            entity_id = device_id.split('.', 1)[1] if '.' in device_id else ''

            for pattern, template in patterns.items():
                # 将模式转换为正则表达式
                # 例如 "light_{area}_{type}" -> "light_(.+?)_(.+)"
                regex_pattern = pattern.replace('{area}', '(.+?)').replace('{type}', '(.+?)')
                import re
                match = re.match(regex_pattern, entity_id)
                if match:
                    groups = match.groups()
                    result = template
                    # 替换模板中的占位符
                    if '{area}' in template and len(groups) > 0:
                        result = result.replace('{area}', groups[0])
                    if '{type}' in template and len(groups) > 1:
                        result = result.replace('{type}', groups[1])
                    return result

            # 尝试从设备状态中获取friendly_name
            state = self.hass.states.get(device_id)
            if state and state.attributes.get('friendly_name'):
                return state.attributes['friendly_name']

            # 如果没有friendly_name，尝试从实体注册表获取
            try:
                from homeassistant.helpers import entity_registry as er
                registry = er.async_get(self.hass)
                entity_entry = registry.async_get(device_id)
                if entity_entry and entity_entry.name:
                    return entity_entry.name
            except Exception as e:
                log_levels = global_config.get('log_levels', {})
                level = log_levels.get('device_name_failed', 'debug')
                if level == 'debug':
                    _LOGGER.debug(f"从实体注册表获取设备名称失败 {device_id}: {e}")

            # 最后，使用设备ID作为后备，但去掉域名前缀
            if '.' in device_id:
                return device_id.split('.', 1)[1].replace('_', ' ')
            else:
                return device_id.replace('_', ' ')

        except Exception as e:
            global_config = self.local_config.get('GlobalDeviceControl', {})
            log_levels = global_config.get('log_levels', {})
            level = log_levels.get('device_name_failed', 'debug')
            if level == 'debug':
                _LOGGER.debug(f"获取设备友好名称失败 {device_id}: {e}")
            # 返回处理过的设备ID作为后备
            return device_id.replace('_', ' ')

    def _convert_speed_to_level(self, speed_percent, global_config):
        """将速度百分比转换为HA速度等级"""
        speed_levels = global_config.get('speed_levels', {
            'off': 0,
            'low': 33,
            'medium': 66,
            'high': 100
        })

        if speed_percent == 0:
            return "off"
        elif speed_percent <= speed_levels.get('low', 33):
            return "low"
        elif speed_percent <= speed_levels.get('medium', 66):
            return "medium"
        else:
            return "high"

    def _create_error_response(self, error_key, error_detail=""):
        """创建错误响应"""
        global_config = self.local_config.get('GlobalDeviceControl', {})
        responses = global_config.get('responses', {})

        if error_key == "error":
            error_template = responses.get('error', '设备控制失败：{error}')
            message = error_template.format(error=error_detail)
        else:
            message = f"未知错误: {error_key}"

        return self._create_response("zh-CN", message, is_error=True)

    def _create_response(self, language: str, message: str, is_error: bool = False):
        """创建响应结果"""
        from homeassistant.helpers import intent

        response = intent.IntentResponse(language=language)
        if is_error:
            response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, message)
        else:
            response.async_set_speech(message)

        return {
            "response": response,
            "success": not is_error,
            "message": message
        }


  

# 全局意图处理器实例
_global_intent_handler = None


def get_global_intent_handler(hass: HomeAssistant) -> Optional[LocalIntentHandler]:
    """获取全局意图处理器实例"""
    global _global_intent_handler
    if _global_intent_handler is None:
        _global_intent_handler = LocalIntentHandler(hass)
    return _global_intent_handler
