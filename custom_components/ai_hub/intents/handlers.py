"""意图处理器 - 本地意图和中文意图处理."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from .loader import get_global_config
from .response_utils import create_intent_result, format_response_message
from .sentence_matcher import matches_sentence_template

_LOGGER = logging.getLogger(__name__)

REQUIRED_DEVICE_CONTROL_KEYS = {
    'global_keywords',
    'on_keywords',
    'off_keywords',
    'domain_services',
    'control_domains',
}
DEFAULT_MIN_TEMPERATURE = 16
DEFAULT_MAX_TEMPERATURE = 30
MEDIA_FALLBACK_SINGLE_ONLY = 'single_only'
MEDIA_FALLBACK_FIRST = 'first'
MEDIA_FALLBACK_ALL = 'all'
MEDIA_FALLBACK_STRATEGIES = {
    MEDIA_FALLBACK_SINGLE_ONLY,
    MEDIA_FALLBACK_FIRST,
    MEDIA_FALLBACK_ALL,
}


def get_local_intents_config() -> dict[str, Any] | None:
    """获取本地意图配置."""
    config = get_global_config()
    if not config:
        return None
    return config.get('local_intents', {})


def get_device_control_config(local_intents: dict[str, Any] | None) -> dict[str, Any]:
    """Return the configured local device control block.

    This keeps backward compatibility with the legacy `GlobalDeviceControl`
    key while allowing any handler name that exposes the same config shape.
    """
    if not isinstance(local_intents, dict):
        return {}

    legacy_config = local_intents.get('GlobalDeviceControl')
    if isinstance(legacy_config, dict):
        return legacy_config

    for value in local_intents.values():
        if not isinstance(value, dict):
            continue
        if REQUIRED_DEVICE_CONTROL_KEYS.issubset(value.keys()):
            return value

    return {}


class LocalIntentHandler:
    """本地意图处理器 - 处理全局设备控制等本地意图."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._config = None  # 延迟加载
        self._local_config = None
        self._local_sentence_patterns = None

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

    def _get_global_device_control_config(self) -> dict[str, Any]:
        """Return the configured local device control block."""
        if not self.local_config:
            return {}
        return get_device_control_config(self.local_config)

    def _get_default_area_name(self) -> str:
        """获取默认区域名称."""
        global_config = self._get_global_device_control_config()
        return global_config.get('default_area_name', '')

    def _get_response_template(self, key: str) -> str:
        """Read response templates from config."""
        global_config = self._get_global_device_control_config()
        responses = global_config.get('responses', {})
        return responses.get(key, "")

    def _format_response_message(self, key: str, **kwargs: Any) -> str:
        """Format a configured response template with safe defaults."""
        template = self._get_response_template(key)
        return format_response_message(template, **kwargs)

    def _get_temperature_limits(self) -> tuple[int, int]:
        """Get configured temperature range."""
        global_config = self._get_global_device_control_config()
        temperature_config = global_config.get('temperature', {})
        return (
            temperature_config.get('min_temperature', DEFAULT_MIN_TEMPERATURE),
            temperature_config.get('max_temperature', DEFAULT_MAX_TEMPERATURE),
        )

    def _get_domain_service(self, domain: str, operation: str, fallback: str) -> str:
        """Read service names from config instead of hardcoding them in handlers."""
        global_config = self._get_global_device_control_config()
        domain_services = global_config.get('domain_services', {})
        return domain_services.get(domain, {}).get(operation, fallback)

    def _get_default_device_name(self, domain: str, fallback: str = "") -> str:
        """Read default device labels from config."""
        global_config = self._get_global_device_control_config()
        default_device_names = global_config.get('default_device_names', {})
        return default_device_names.get(domain, fallback)

    def should_handle(self, text: str) -> bool:
        """智能判断是否应该使用本地意图处理."""
        if not self.local_config:
            return False

        global_config = self._get_global_device_control_config()
        if not global_config:
            return False

        text_lower = text.lower().strip()

        should_handle = self._matches_local_sentence_template(text_lower)
        _LOGGER.debug("Local intent check: '%s' -> %s", text, should_handle)
        return should_handle

    def matches_sentence_template(self, text: str) -> bool:
        """Return whether the text matches a configured local sentence template."""
        if not self.local_config:
            return False

        global_config = self._get_global_device_control_config()
        if not global_config:
            return False

        text_lower = text.lower().strip()
        return matches_sentence_template(self, text_lower)

    def _has_explicit_action_word(self, text_lower: str, global_config: dict) -> bool:
        """Return whether text contains a configured imperative action word."""
        action_words = global_config.get('on_keywords', []) + global_config.get('off_keywords', [])
        return any(action in text_lower for action in action_words)

    async def handle(self, text: str, language: str = "zh-CN"):
        """处理本地意图."""
        if not self.should_handle(text):
            return None

        global_config = self._get_global_device_control_config()
        text_lower = text.lower().strip()

        # 仅保留 YAML 未覆盖的本地增强开关控制
        is_on = self._has_explicit_action(text_lower, global_config, global_config.get('on_keywords', []))
        is_off = self._has_explicit_action(text_lower, global_config, global_config.get('off_keywords', []))

        if not (is_on or is_off):
            return None

        # 解析设备、设备类型和区域
        area_names, device_types = self._parse_device_and_area(text_lower, global_config)
        target_entities = self._match_named_entities(text_lower, device_types or None, area_names)
        global_keywords = global_config.get('global_keywords', [])
        has_global_keyword = any(keyword in text_lower for keyword in global_keywords)

        if not device_types and not target_entities:
            return None

        if device_types and not target_entities and not area_names and not has_global_keyword:
            return None

        # 执行通用开关控制
        return await self._execute_control(
            area_names, device_types, is_on, global_config, language, target_entities
        )

    def _has_explicit_action(
        self,
        text_lower: str,
        global_config: dict,
        action_words: list[str],
    ) -> bool:
        """Return whether text contains one of the configured action words."""
        return any(action in text_lower for action in action_words)

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
            ]
            for name in candidate_names:
                if not isinstance(name, str):
                    continue
                normalized_name = name.strip().lower()
                if len(normalized_name) < 2:
                    continue
                if self._contains_exact_entity_name(text_lower, normalized_name):
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

    @staticmethod
    def _contains_exact_entity_name(text_lower: str, entity_name: str) -> bool:
        """Return whether the utterance contains the entity name with safe boundaries."""
        start = 0
        while True:
            index = text_lower.find(entity_name, start)
            if index == -1:
                return False

            before_ok = index == 0 or not text_lower[index - 1].isalnum()
            end_index = index + len(entity_name)
            after_ok = end_index == len(text_lower) or not text_lower[end_index].isalnum()
            if before_ok and after_ok:
                return True

            start = index + 1

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
                count=all_success,
                area=area_text,
                fail_msg=fail_msg,
            )

            success_results = [
                {
                    "type": "entity",
                    "name": self._get_device_friendly_name(device_id),
                    "id": device_id,
                }
                for device_id in all_devices
                if self.hass.states.get(device_id) is not None
            ]

            return self._create_response(language, message, success_results=success_results)

        except Exception as e:
            message = self._format_response_message('error', error=str(e))
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

        global_config = self._get_global_device_control_config()
        failure_config = global_config.get('failure_message', {})
        unique_failed = list(set(failed_devices))
        max_devices = failure_config.get('max_devices_list', 3)
        failed_list = '、'.join(unique_failed[:max_devices])
        if len(unique_failed) <= max_devices:
            template = failure_config.get('few_devices', '')
            return template.format(error_count=len(unique_failed), failed_list=failed_list)

        template = failure_config.get('many_devices', '')
        return template.format(error_count=len(unique_failed), failed_list=failed_list)

    def _create_response(
        self,
        language: str,
        message: str,
        is_error: bool = False,
        success_results: list[dict[str, Any]] | None = None,
    ):
        """创建响应结果."""
        return create_intent_result(
            language,
            message,
            is_error=is_error,
            success_results=success_results,
        )


# 全局意图处理器实例
_global_intent_handler: LocalIntentHandler | None = None


def get_global_intent_handler(hass: HomeAssistant) -> LocalIntentHandler | None:
    """获取全局意图处理器实例."""
    global _global_intent_handler
    if _global_intent_handler is None:
        _global_intent_handler = LocalIntentHandler(hass)
    return _global_intent_handler
