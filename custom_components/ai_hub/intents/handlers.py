"""意图处理器 - 本地意图和中文意图处理."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.helpers import intent

from .loader import get_global_config

_LOGGER = logging.getLogger(__name__)


def get_local_intents_config() -> dict[str, Any] | None:
    """获取本地意图配置."""
    config = get_global_config()
    if not config:
        return None
    return config.get('local_intents', {})


class ChineseIntentHandler(intent.IntentHandler):
    """中文意图处理器 - 仅作为后备选项."""

    def __init__(self, hass: HomeAssistant, intent_name: str, sentence: str):
        self.hass = hass
        self.intent_type = intent_name
        self.sentence = sentence

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """处理意图 - 委托给Home Assistant的原生意图处理."""
        try:
            response = intent.IntentResponse(language="zh-CN")
            response.async_set_speech("好的，正在处理您的请求")
            return response

        except Exception as e:
            _LOGGER.error(f"Intent handling failed {self.intent_type}: {e}")
            response = intent.IntentResponse()
            response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"意图处理失败: {str(e)}"
            )
            return response


class LocalIntentHandler:
    """本地意图处理器 - 处理全局设备控制等本地意图."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._config = None  # 延迟加载
        self._local_config = None

    @property
    def local_config(self):
        """延迟加载本地意图配置."""
        if self._local_config is None:
            self._local_config = get_local_intents_config()
        return self._local_config

    @property
    def config(self):
        """延迟加载全局配置."""
        if self._config is None:
            self._config = get_global_config()
        return self._config

    def _get_default_area_name(self) -> str:
        """获取默认区域名称."""
        global_config = self.local_config.get('GlobalDeviceControl', {}) if self.local_config else {}
        return global_config.get('default_area_name', '全屋')

    def _format_error_suffix(self, error_count: int) -> str:
        """格式化错误后缀消息."""
        if error_count > 0:
            return f"，{error_count}个设备失败"
        return ""

    def _get_response_template(self, key: str, fallback: str) -> str:
        """Read response templates from config."""
        global_config = self.local_config.get('GlobalDeviceControl', {}) if self.local_config else {}
        responses = global_config.get('responses', {})
        return responses.get(key, fallback)

    def _format_response_message(self, key: str, fallback: str, **kwargs: Any) -> str:
        """Format a configured response template with safe defaults."""
        template = self._get_response_template(key, fallback)
        values = {
            'area': kwargs.get('area', ''),
            'device': kwargs.get('device', ''),
            'count': kwargs.get('count', 0),
            'temperature': kwargs.get('temperature', ''),
            'brightness': kwargs.get('brightness', ''),
            'color': kwargs.get('color', ''),
            'volume': kwargs.get('volume', ''),
            'position': kwargs.get('position', ''),
            'speed': kwargs.get('speed', ''),
            'query': kwargs.get('query', ''),
            'fail_msg': kwargs.get('fail_msg', ''),
            'error': kwargs.get('error', ''),
        }
        return template.format(**values)

    def _get_temperature_limits(self) -> tuple[int, int]:
        """Get configured temperature range."""
        global_config = self.local_config.get('GlobalDeviceControl', {}) if self.local_config else {}
        temperature_config = global_config.get('temperature', {})
        return (
            temperature_config.get('min_temperature', 16),
            temperature_config.get('max_temperature', 30),
        )

    def _get_domain_service(self, domain: str, operation: str, fallback: str) -> str:
        """Read service names from config instead of hardcoding them in handlers."""
        global_config = self.local_config.get('GlobalDeviceControl', {}) if self.local_config else {}
        domain_services = global_config.get('domain_services', {})
        return domain_services.get(domain, {}).get(operation, fallback)

    def _get_default_device_name(self, domain: str, fallback: str) -> str:
        """Read default device labels from config."""
        global_config = self.local_config.get('GlobalDeviceControl', {}) if self.local_config else {}
        default_device_names = global_config.get('default_device_names', {})
        return default_device_names.get(domain, fallback)

    def should_handle(self, text: str) -> bool:
        """智能判断是否应该使用本地意图处理."""
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

        # 规则2: 检查显式动作/参数指令
        action_words = global_config.get('on_keywords', []) + global_config.get('off_keywords', [])
        has_action_word = any(action in text_lower for action in action_words)
        has_parameter_command = self._has_parameter_command(text, text_lower, global_config)
        has_target_hint = self._has_target_hint(text_lower, global_config)
        is_short_text = len(text_clean) <= 4

        # 关键判断:
        # 1. 全局控制直接本地处理
        # 2. 显式参数控制 + 明确目标，本地处理以补足中文能力
        # 3. 显式开关控制 + 明确目标，本地处理以补足中文泛化开关
        should_handle = has_global_keyword or (
            has_target_hint and (has_action_word or has_parameter_command)
        )

        # 对于有动作词的短文本，如果缺少全局关键词，则不处理
        if has_action_word and is_short_text and not has_global_keyword and not has_target_hint:
            should_handle = False

        _LOGGER.debug(f"Local intent check: '{text}' -> {should_handle}")

        return should_handle

    async def handle(self, text: str, language: str = "zh-CN"):
        """处理本地意图."""
        if not self.should_handle(text):
            return None

        global_config = self.local_config.get('GlobalDeviceControl', {})
        text_lower = text.lower().strip()

        # 1. 检查是否为参数控制命令
        param_result = await self._handle_parameter_control(text, text_lower, global_config)
        if param_result:
            return param_result

        media_result = await self._handle_media_play_command(text_lower, language, global_config)
        if media_result:
            return media_result

        # 2. 解析操作类型
        on_keywords = global_config.get('on_keywords', [])
        off_keywords = global_config.get('off_keywords', [])

        is_on = any(keyword in text_lower for keyword in on_keywords)
        is_off = any(keyword in text_lower for keyword in off_keywords)

        if not (is_on or is_off):
            return None

        # 3. 解析设备、设备类型和区域
        area_names, device_types = self._parse_device_and_area(text_lower, global_config)
        target_entities = self._match_named_entities(text_lower, device_types or None, area_names)

        if not device_types and not target_entities:
            return None

        # 4. 执行设备控制
        return await self._execute_control(
            area_names, device_types, is_on, global_config, language, target_entities
        )

    def _has_target_hint(self, text_lower: str, global_config: dict) -> bool:
        """Check whether the text contains a concrete area/device hint."""
        area_names, device_types = self._parse_device_and_area(text_lower, global_config)
        if area_names or device_types:
            return True

        return bool(self._match_named_entities(text_lower))

    def _parse_device_and_area(self, text_lower: str, global_config: dict) -> tuple:
        """解析设备类型和区域."""
        area_names = []
        device_types = []

        # 使用缓存的配置
        config = self.config

        # 获取区域配置
        try:
            if config and 'lists' in config:
                areas_config = config['lists'].get('area_names', {}).get('values', [])
                for area in areas_config:
                    if area in text_lower:
                        area_names.append(area)
        except Exception:
            pass

        # 获取设备类型
        device_type_keywords = global_config.get('device_type_keywords', {})

        if isinstance(device_type_keywords, str) and device_type_keywords.startswith("{{lists}}"):
            lists_config = config.get('lists', {}) if config else {}

            domain_mapping: dict[str, list[str]] = {}
            for domain in global_config.get('control_domains', []):
                list_names = [f'{domain}_names']
                if domain == 'media_player' and 'media_names' in lists_config:
                    list_names.append('media_names')
                if domain == 'device_tracker' and 'tracker_names' in lists_config:
                    list_names.append('tracker_names')
                domain_mapping[domain] = list_names

            for domain, list_names in domain_mapping.items():
                for list_name in list_names:
                    keywords_list = lists_config.get(list_name, {}).get('values', [])
                    if keywords_list:
                        for keyword in keywords_list:
                            if keyword in text_lower:
                                device_types.append(domain)
                                break
                    if domain in device_types:
                        break
        else:
            for keyword, domain in device_type_keywords.items():
                if keyword in text_lower:
                    device_types.append(domain)

        return area_names, list(set(device_types))

    def _match_named_entities(
        self,
        text_lower: str,
        allowed_domains: list[str] | None = None,
        area_names: list[str] | None = None,
    ) -> list[str]:
        """Match exposed entities by friendly name from the utterance."""
        area_names = area_names or []
        matches: list[tuple[str, str]] = []

        for entity_id in self.hass.states.async_entity_ids():
            domain = entity_id.split('.', 1)[0]
            if allowed_domains and domain not in allowed_domains:
                continue

            state = self.hass.states.get(entity_id)
            if state is None:
                continue

            candidate_names = [
                state.name,
                state.attributes.get('friendly_name'),
                entity_id.split('.', 1)[1].replace('_', ' '),
                entity_id.split('.', 1)[1].replace('_', ''),
            ]
            for name in candidate_names:
                if not isinstance(name, str):
                    continue
                normalized_name = name.strip().lower()
                if len(normalized_name) < 2:
                    continue
                if normalized_name in text_lower:
                    if area_names and not self._entity_matches_areas(entity_id, area_names):
                        continue
                    matches.append((entity_id, normalized_name))
                    break

        # Prefer longer names to avoid a short alias swallowing a more precise match.
        matches.sort(key=lambda item: len(item[1]), reverse=True)
        unique_entities: list[str] = []
        seen: set[str] = set()
        for entity_id, _ in matches:
            if entity_id in seen:
                continue
            seen.add(entity_id)
            unique_entities.append(entity_id)
        return unique_entities

    def _entity_matches_areas(self, entity_id: str, area_names: list[str]) -> bool:
        """Check whether entity belongs to any target area."""
        try:
            entity_registry = er.async_get(self.hass)
            area_registry = ar.async_get(self.hass)
            device_registry = dr.async_get(self.hass)

            entry = entity_registry.async_get(entity_id)
            area_id = None
            if entry is not None:
                area_id = entry.area_id
                if area_id is None and entry.device_id:
                    device_entry = device_registry.async_get(entry.device_id)
                    if device_entry is not None:
                        area_id = device_entry.area_id

            if area_id is None:
                return False

            area_entry = area_registry.async_get_area(area_id)
            if area_entry is None:
                return False

            return self._match_area_name(area_entry.name, area_names)
        except Exception:
            return False

    async def _execute_control(
        self, area_names: list, device_types: list,
        is_on: bool, global_config: dict, language: str,
        target_entities: list[str] | None = None,
    ):
        """执行设备控制."""
        is_global_control = not area_names

        try:
            all_devices = []

            if target_entities:
                all_devices = target_entities
            elif is_global_control:
                for domain in device_types:
                    try:
                        devices = self.hass.states.async_entity_ids(domain)
                        all_devices.extend(devices)
                    except Exception as e:
                        _LOGGER.debug(f"Failed to get {domain} devices: {e}")
            else:
                all_devices = await self._get_area_devices(area_names, device_types)

            if not all_devices:
                return None

            # 执行批量控制
            domain_services = global_config.get('domain_services', {})
            service_key = "turn_on" if is_on else "turn_off"

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

            # 执行操作
            for domain, devices in devices_by_domain.items():
                service_name = domain_services.get(domain, {}).get(service_key, service_key)
                success, errors, failed = await self._execute_device_operations(
                    devices, domain, service_name
                )
                all_success += success
                all_errors += errors
                all_failed_devices.extend(failed)

            # 生成响应
            fail_msg = self._format_failure_message(all_errors, all_failed_devices)
            area_text = area_names[0] if area_names else ""
            message_key = 'success_on' if is_on else 'success_off'
            message = self._format_response_message(
                message_key,
                '已打开{count}个设备{fail_msg}' if is_on else '已关闭{count}个设备{fail_msg}',
                count=all_success,
                area=area_text,
                fail_msg=fail_msg,
            )

            return self._create_response(language, message)

        except Exception as e:
            message = self._format_response_message('error', '设备控制失败：{error}', error=str(e))
            return self._create_response(language, message, is_error=True)

    async def _get_area_devices(self, area_names: list, device_types: list) -> list:
        """获取指定区域的设备."""
        all_devices = []

        try:
            entity_registry = er.async_get(self.hass)
            area_registry = ar.async_get(self.hass)
            device_registry = dr.async_get(self.hass)

            for domain in device_types:
                domain_devices = self.hass.states.async_entity_ids(domain)
                for device_id in domain_devices:
                    try:
                        entity_entry = entity_registry.async_get(device_id)
                        area_id = None
                        if entity_entry is not None:
                            area_id = entity_entry.area_id
                            if area_id is None and entity_entry.device_id:
                                device_entry = device_registry.async_get(entity_entry.device_id)
                                if device_entry is not None:
                                    area_id = device_entry.area_id

                        if area_id is None:
                            continue

                        area_entry = area_registry.async_get_area(area_id)
                        if area_entry and self._match_area_name(area_entry.name, area_names):
                            all_devices.append(device_id)
                    except Exception:
                        continue
        except Exception as e:
            _LOGGER.debug(f"Failed to get area devices: {e}")
            # 回退到全局
            for domain in device_types:
                all_devices.extend(self.hass.states.async_entity_ids(domain))

        return all_devices

    def _match_area_name(self, area_name: str, target_areas: list) -> bool:
        """区域名称匹配."""
        if area_name in target_areas:
            return True
        area_lower = area_name.lower()
        for target in target_areas:
            if target.lower() in area_lower or area_lower in target.lower():
                return True
        return False

    async def _execute_device_operations(
        self, devices: list, domain: str, service_name: str, service_data: dict | None = None
    ) -> tuple:
        """执行批量设备操作."""
        if service_data is None:
            service_data = {}

        success_count = 0
        error_count = 0
        failed_devices = []

        for device_id in devices:
            try:
                data = {'entity_id': device_id, **service_data}
                await self.hass.services.async_call(domain, service_name, data)
                success_count += 1
            except Exception as e:
                _LOGGER.debug(f"Failed to control device {device_id}: {e}")
                error_count += 1
                failed_devices.append(self._get_device_friendly_name(device_id))

        return success_count, error_count, failed_devices

    def _get_device_friendly_name(self, device_id: str) -> str:
        """获取设备友好名称."""
        try:
            state = self.hass.states.get(device_id)
            if state and state.attributes.get('friendly_name'):
                return state.attributes['friendly_name']
        except Exception:
            pass

        if '.' in device_id:
            return device_id.split('.', 1)[1].replace('_', ' ')
        return device_id

    def _format_failure_message(self, error_count: int, failed_devices: list) -> str:
        """格式化失败消息."""
        if error_count == 0:
            return ""

        global_config = self.local_config.get('GlobalDeviceControl', {}) if self.local_config else {}
        failure_config = global_config.get('failure_message', {})
        unique_failed = list(set(failed_devices))
        max_devices = failure_config.get('max_devices_list', 3)
        failed_list = '、'.join(unique_failed[:max_devices])
        if len(unique_failed) <= max_devices:
            template = failure_config.get('few_devices', '，但以下{error_count}个设备失败：{failed_list}')
            return template.format(error_count=len(unique_failed), failed_list=failed_list)

        template = failure_config.get('many_devices', '，但{error_count}个设备失败，包括：{failed_list}等')
        return template.format(error_count=len(unique_failed), failed_list=failed_list)

    def _create_response(self, language: str, message: str, is_error: bool = False):
        """创建响应结果."""
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

    # ========== 参数控制方法 ==========

    async def _handle_parameter_control(self, text: str, text_lower: str, global_config: dict):
        """处理参数控制命令."""
        if not self._has_parameter_command(text, text_lower, global_config):
            return None

        area_names = self._parse_areas(text_lower)
        is_global = not area_names

        # Try each parameter type in order
        result = await self._try_brightness_control(text, text_lower, global_config, area_names, is_global)
        if result:
            return result

        result = await self._try_brightness_complaint(text_lower, global_config, area_names, is_global)
        if result:
            return result

        result = await self._try_temperature_control(text_lower, global_config, area_names, is_global)
        if result:
            return result

        result = await self._try_volume_control(text, text_lower, global_config, area_names, is_global)
        if result:
            return result

        result = await self._try_color_control(text_lower, global_config, area_names, is_global)
        if result:
            return result

        result = await self._try_cover_position_control(text, text_lower, global_config, area_names, is_global)
        if result:
            return result

        result = await self._try_fan_speed_control(text, text_lower, global_config, area_names, is_global)
        if result:
            return result

        return None

    async def _handle_media_play_command(self, text_lower: str, language: str, global_config: dict):
        """Handle media search/play fallback commands."""
        media_config = global_config.get('media_search', {})
        action_keywords = media_config.get('action_keywords', [])
        if not action_keywords or not any(keyword in text_lower for keyword in action_keywords):
            return None

        query, content_type = self._extract_media_query(text_lower, global_config, media_config)
        if not query:
            return None

        area_names = self._parse_areas(text_lower)
        target_entities = self._match_named_entities(text_lower, ['media_player'], area_names)
        if not target_entities:
            target_entities = self._select_media_fallback_targets(media_config, area_names)
        if not target_entities:
            return None

        service_domain = media_config.get('service_domain', 'media_player')
        service_name = media_config.get('service_name', 'play_media')
        service_data = {
            'media_content_id': query,
            'media_content_type': content_type,
        }
        enqueue = media_config.get('enqueue')
        if enqueue:
            service_data['enqueue'] = enqueue

        success, errors, failed = await self._execute_device_operations(
            target_entities,
            service_domain,
            service_name,
            service_data,
        )
        if success == 0 and errors > 0:
            fail_msg = self._format_failure_message(errors, failed)
            message = self._format_response_message(
                'error',
                '设备控制失败：{error}',
                error=fail_msg.lstrip('，') or '媒体播放失败',
            )
            return self._create_response(language, message, is_error=True)

        area_text = area_names[0] if area_names else self._get_default_area_name()
        fail_msg = self._format_failure_message(errors, failed)
        device_name = self._get_default_device_name('media_player', '媒体设备')
        message = self._format_response_message(
            'success_media_play',
            '已在{area}{device}播放{query}{fail_msg}',
            area=area_text,
            device=device_name,
            query=query,
            fail_msg=fail_msg,
        )
        return self._create_response(language, message)

    def _extract_media_query(
        self, text_lower: str, global_config: dict, media_config: dict
    ) -> tuple[str | None, str]:
        """Extract the media query and content type from text."""
        content_type = media_config.get('default_content_type', 'music')
        media_type_keywords = media_config.get('media_type_keywords', {})
        for media_type, keywords in media_type_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                content_type = media_type
                break

        action_keywords = [keyword.strip().lower() for keyword in media_config.get('action_keywords', []) if keyword]
        query = text_lower.strip()
        for keyword in sorted(action_keywords, key=len, reverse=True):
            if query.startswith(keyword):
                query = query[len(keyword):].strip()
                break

        for keyword in sorted(media_type_keywords.get(content_type, []), key=len, reverse=True):
            normalized_keyword = keyword.strip().lower()
            if normalized_keyword and query.startswith(normalized_keyword):
                query = query[len(normalized_keyword):].strip()
                break

        cleanup_tokens: list[str] = []
        cleanup_tokens.extend(global_config.get('global_keywords', []))

        config = self.config or {}
        lists_config = config.get('lists', {})
        for list_name in ('area_names', 'media_player_names', 'media_names'):
            cleanup_tokens.extend(lists_config.get(list_name, {}).get('values', []))

        for keywords in media_type_keywords.values():
            cleanup_tokens.extend(keywords)

        for token in sorted({token.strip().lower() for token in cleanup_tokens if token and len(token.strip()) > 1}, key=len, reverse=True):
            query = query.replace(token.lower(), ' ')

        query = re.sub(r'(在|把|将|给|让|的|上|里|中|一下|一首|一个|一部|一张)', ' ', query)
        query = re.sub(r'\s+', ' ', query).strip()
        return (query or None), content_type

    def _select_media_fallback_targets(self, media_config: dict, area_names: list[str]) -> list[str]:
        """Select fallback media targets when no explicit entity name was found."""
        strategy = media_config.get('fallback_target_strategy', 'single_only')
        if area_names:
            return []

        media_players = list(self.hass.states.async_entity_ids('media_player'))
        if strategy == 'all':
            return media_players
        if strategy == 'first' and media_players:
            return [media_players[0]]
        if strategy == 'single_only' and len(media_players) == 1:
            return media_players
        return []

    def _has_parameter_command(self, text: str, text_lower: str, global_config: dict) -> bool:
        """Check if the text contains a parameter control command."""
        param_keywords = global_config.get('param_keywords', [])
        if any(keyword in text_lower for keyword in param_keywords):
            return True

        # Check for direct parameter patterns
        if self._has_brightness_param(text, text_lower, global_config):
            return True
        if self._has_volume_param(text, text_lower, global_config):
            return True
        if self._has_temperature_param(text_lower, global_config):
            return True
        if self._has_brightness_complaint(text_lower, global_config):
            return True
        if self._has_color_param(text_lower, global_config):
            return True
        if self._has_cover_position_param(text, text_lower, global_config):
            return True
        if self._has_fan_speed_param(text, text_lower, global_config):
            return True

        return False

    def _has_brightness_param(self, text: str, text_lower: str, global_config: dict) -> bool:
        """Check if text contains brightness parameter."""
        keywords = global_config.get('brightness_keywords', [])
        return any(kw in text_lower for kw in keywords) and re.search(r'(\d{1,3})\s*%?', text)

    def _has_volume_param(self, text: str, text_lower: str, global_config: dict) -> bool:
        """Check if text contains volume parameter."""
        keywords = global_config.get('volume_keywords', [])
        return any(kw in text_lower for kw in keywords) and re.search(r'(\d{1,3})\s*%?', text)

    def _has_temperature_param(self, text_lower: str, global_config: dict) -> bool:
        """Check if text contains temperature parameter."""
        keywords = global_config.get('temperature_keywords', [])
        return any(kw in text_lower for kw in keywords) and re.search(r'(\d{1,2})\s*度', text_lower)

    def _has_brightness_complaint(self, text_lower: str, global_config: dict) -> bool:
        """Check if text contains brightness complaint keywords."""
        complaint = global_config.get('brightness_complaint', {})
        if not complaint:
            return False
        hot_kw = complaint.get('hot_keywords', [])
        cold_kw = complaint.get('cold_keywords', [])
        return any(kw in text_lower for kw in hot_kw + cold_kw)

    def _has_color_param(self, text_lower: str, global_config: dict) -> bool:
        """Check if text contains color control keywords."""
        keywords = global_config.get('color_keywords', [])
        color_values = global_config.get('color_values', {})
        return any(kw in text_lower for kw in keywords) and any(color in text_lower for color in color_values)

    def _has_cover_position_param(self, text: str, text_lower: str, global_config: dict) -> bool:
        """Check if text contains cover position parameter."""
        keywords = global_config.get('cover_position_keywords', [])
        has_keyword = any(kw in text_lower for kw in keywords)
        has_percent = re.search(r'(\d{1,3})\s*%?', text) is not None
        return has_keyword and has_percent

    def _has_fan_speed_param(self, text: str, text_lower: str, global_config: dict) -> bool:
        """Check if text contains fan speed parameter."""
        keywords = global_config.get('fan_speed_keywords', [])
        has_keyword = any(kw in text_lower for kw in keywords)
        has_percent = re.search(r'(\d{1,3})\s*%?', text) is not None
        return has_keyword and has_percent

    async def _try_brightness_control(
        self, text: str, text_lower: str, global_config: dict,
        area_names: list, is_global: bool
    ):
        """Try to handle brightness control command."""
        keywords = global_config.get('brightness_keywords', [])
        if not any(kw in text_lower for kw in keywords):
            return None

        match = re.search(r'(\d{1,3})\s*%?', text)
        if not match:
            return None

        brightness = int(match.group(1))
        if 0 <= brightness <= 100:
            return await self._control_light_brightness(area_names, is_global, brightness)
        return None

    async def _try_brightness_complaint(
        self, text_lower: str, global_config: dict,
        area_names: list, is_global: bool
    ):
        """Try to handle brightness complaint (too hot/cold)."""
        complaint = global_config.get('brightness_complaint', {})
        if not complaint:
            return None

        hot_kw = complaint.get('hot_keywords', [])
        cold_kw = complaint.get('cold_keywords', [])
        default_brightness = complaint.get('default_brightness', {})

        if any(kw in text_lower for kw in hot_kw):
            brightness = default_brightness.get('hot_recommendation', 30)
            return await self._control_light_brightness(area_names, is_global, brightness)

        if any(kw in text_lower for kw in cold_kw):
            brightness = default_brightness.get('cold_recommendation', 70)
            return await self._control_light_brightness(area_names, is_global, brightness)

        return None

    async def _try_temperature_control(
        self, text_lower: str, global_config: dict,
        area_names: list, is_global: bool
    ):
        """Try to handle temperature control command."""
        keywords = global_config.get('temperature_keywords', [])
        if not any(kw in text_lower for kw in keywords):
            return None

        match = re.search(r'(\d{1,2})\s*度', text_lower)
        if not match:
            return None

        temp = int(match.group(1))
        min_temp, max_temp = self._get_temperature_limits()
        if min_temp <= temp <= max_temp:
            return await self._control_climate_temperature(area_names, is_global, temp)
        return None

    async def _try_volume_control(
        self, text: str, text_lower: str, global_config: dict,
        area_names: list, is_global: bool
    ):
        """Try to handle volume control command."""
        keywords = global_config.get('volume_keywords', [])
        if not any(kw in text_lower for kw in keywords):
            return None

        match = re.search(r'(\d{1,3})\s*%?', text)
        if not match:
            return None

        volume = int(match.group(1))
        if 0 <= volume <= 100:
            return await self._control_media_volume(area_names, is_global, volume)
        return None

    async def _try_color_control(
        self, text_lower: str, global_config: dict,
        area_names: list, is_global: bool
    ):
        """Try to handle light color control command."""
        color_values = global_config.get('color_values', {})
        matched_color = next((color for color in color_values if color in text_lower), None)
        if matched_color is None:
            return None

        return await self._control_light_color(area_names, is_global, matched_color, color_values[matched_color])

    async def _try_cover_position_control(
        self, text: str, text_lower: str, global_config: dict,
        area_names: list, is_global: bool
    ):
        """Try to handle cover position control command."""
        keywords = global_config.get('cover_position_keywords', [])
        if not any(kw in text_lower for kw in keywords):
            return None

        match = re.search(r'(\d{1,3})\s*%?', text)
        if not match:
            return None

        position = int(match.group(1))
        if 0 <= position <= 100:
            return await self._control_cover_position(area_names, is_global, position)
        return None

    async def _try_fan_speed_control(
        self, text: str, text_lower: str, global_config: dict,
        area_names: list, is_global: bool
    ):
        """Try to handle fan speed control command."""
        keywords = global_config.get('fan_speed_keywords', [])
        if not any(kw in text_lower for kw in keywords):
            return None

        match = re.search(r'(\d{1,3})\s*%?', text)
        if not match:
            return None

        speed = int(match.group(1))
        if 0 <= speed <= 100:
            return await self._control_fan_speed(area_names, is_global, speed)
        return None

    def _parse_areas(self, text_lower: str) -> list:
        """解析区域名称."""
        area_names = []
        # 使用缓存的配置
        config = self.config
        try:
            if config and 'lists' in config:
                areas = config['lists'].get('area_names', {}).get('values', [])
                for area in areas:
                    if area in text_lower:
                        area_names.append(area)
        except Exception:
            pass
        return area_names

    async def _control_light_brightness(self, area_names: list, is_global: bool, brightness: int):
        """控制灯光亮度."""
        devices = await self._get_devices_by_domain(['light'], area_names, is_global)
        if not devices:
            return None

        success, errors, failed = await self._execute_device_operations(
            devices,
            'light',
            self._get_domain_service('light', 'set_brightness', 'turn_on'),
            {'brightness_pct': brightness},
        )

        area_text = area_names[0] if area_names else self._get_default_area_name()
        fail_msg = self._format_failure_message(errors, failed)
        message = self._format_response_message(
            'success_brightness',
            '已将{area}{device}亮度调至{brightness}%{fail_msg}',
            area=area_text,
            device=self._get_default_device_name('light', '灯光'),
            brightness=brightness,
            fail_msg=fail_msg,
        )

        return self._create_response("zh-CN", message)

    async def _control_climate_temperature(self, area_names: list, is_global: bool, temperature: int):
        """控制空调温度."""
        devices = await self._get_devices_by_domain(['climate'], area_names, is_global)
        if not devices:
            return None

        success, errors, failed = await self._execute_device_operations(
            devices,
            'climate',
            self._get_domain_service('climate', 'set_temperature', 'set_temperature'),
            {'temperature': temperature},
        )

        area_text = area_names[0] if area_names else self._get_default_area_name()
        fail_msg = self._format_failure_message(errors, failed)
        message = self._format_response_message(
            'success_temperature',
            '已将{area}温度设置为{temperature}度{fail_msg}',
            area=area_text,
            temperature=temperature,
            fail_msg=fail_msg,
        )

        return self._create_response("zh-CN", message)

    async def _control_media_volume(self, area_names: list, is_global: bool, volume: int):
        """控制媒体音量."""
        devices = await self._get_devices_by_domain(['media_player'], area_names, is_global)
        if not devices:
            return None

        volume_level = volume / 100.0
        success, errors, failed = await self._execute_device_operations(
            devices,
            'media_player',
            self._get_domain_service('media_player', 'set_volume', 'volume_set'),
            {'volume_level': volume_level},
        )

        area_text = area_names[0] if area_names else self._get_default_area_name()
        fail_msg = self._format_failure_message(errors, failed)
        message = self._format_response_message(
            'success_volume',
            '已将{area}{device}音量调至{volume}%{fail_msg}',
            area=area_text,
            device=self._get_default_device_name('media_player', '媒体设备'),
            volume=volume,
            fail_msg=fail_msg,
        )

        return self._create_response("zh-CN", message)

    async def _control_light_color(
        self, area_names: list, is_global: bool, color_name: str, color_key: str
    ):
        """控制灯光颜色."""
        devices = await self._get_devices_by_domain(['light'], area_names, is_global)
        if not devices:
            return None

        rgb_values = (
            self.local_config.get('GlobalDeviceControl', {})
            .get('color_rgb_values', {})
            .get(color_key)
        )
        service_data = {'rgb_color': rgb_values} if rgb_values else {'color_name': color_key}

        success, errors, failed = await self._execute_device_operations(
            devices,
            'light',
            self._get_domain_service('light', 'set_color', 'turn_on'),
            service_data,
        )

        area_text = area_names[0] if area_names else self._get_default_area_name()
        fail_msg = self._format_failure_message(errors, failed)
        message = self._format_response_message(
            'success_color',
            '已将{area}{device}颜色设置为{color}{fail_msg}',
            area=area_text,
            device=self._get_default_device_name('light', '灯光'),
            color=color_name,
            fail_msg=fail_msg,
        )

        return self._create_response("zh-CN", message)

    async def _control_cover_position(self, area_names: list, is_global: bool, position: int):
        """控制窗帘位置."""
        devices = await self._get_devices_by_domain(['cover'], area_names, is_global)
        if not devices:
            return None

        success, errors, failed = await self._execute_device_operations(
            devices,
            'cover',
            self._get_domain_service('cover', 'set_position', 'set_cover_position'),
            {'position': position},
        )

        area_text = area_names[0] if area_names else self._get_default_area_name()
        fail_msg = self._format_failure_message(errors, failed)
        message = self._format_response_message(
            'success_cover_position',
            '已将{area}{device}位置调至{position}%{fail_msg}',
            area=area_text,
            device=self._get_default_device_name('cover', '窗帘'),
            position=position,
            fail_msg=fail_msg,
        )

        return self._create_response("zh-CN", message)

    async def _control_fan_speed(self, area_names: list, is_global: bool, speed: int):
        """控制风扇速度."""
        devices = await self._get_devices_by_domain(['fan'], area_names, is_global)
        if not devices:
            return None

        service_name = self._get_domain_service('fan', 'set_percentage', 'set_percentage')
        service_data = {'percentage': speed}
        if service_name == 'set_speed':
            service_data = {'speed': speed}
        success, errors, failed = await self._execute_device_operations(
            devices,
            'fan',
            service_name,
            service_data,
        )

        area_text = area_names[0] if area_names else self._get_default_area_name()
        fail_msg = self._format_failure_message(errors, failed)
        message = self._format_response_message(
            'success_fan_speed',
            '已将{area}{device}风速调至{speed}%{fail_msg}',
            area=area_text,
            device=self._get_default_device_name('fan', '风扇'),
            speed=speed,
            fail_msg=fail_msg,
        )

        return self._create_response("zh-CN", message)

    async def _get_devices_by_domain(self, domains: list, area_names: list, is_global: bool) -> list:
        """根据域获取设备."""
        if is_global:
            all_devices = []
            for domain in domains:
                try:
                    all_devices.extend(self.hass.states.async_entity_ids(domain))
                except Exception:
                    pass
            return all_devices
        else:
            return await self._get_area_devices(area_names, domains)


# 全局意图处理器实例
_global_intent_handler: LocalIntentHandler | None = None


def get_global_intent_handler(hass: HomeAssistant) -> LocalIntentHandler | None:
    """获取全局意图处理器实例."""
    global _global_intent_handler
    if _global_intent_handler is None:
        _global_intent_handler = LocalIntentHandler(hass)
    return _global_intent_handler
