"""意图处理器 - 本地意图和中文意图处理."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from .loader import get_global_config
from .response_utils import create_intent_result, format_response_message

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


@dataclass(slots=True)
class SentenceMatchResult:
    """Structured result for a strict local sentence match."""

    template: str
    slots: dict[str, str]


@dataclass(slots=True)
class _CompiledTemplate:
    template: str
    pattern: re.Pattern[str]


def match_sentence_template(handler: Any, text: str) -> SentenceMatchResult | None:
    """Return the first strict local sentence match result."""
    candidates = get_local_sentence_patterns(handler)
    if not candidates:
        return None

    normalized_text = re.sub(r'\s+', ' ', text.lower().strip()).strip()
    for candidate in candidates:
        match = candidate.pattern.fullmatch(normalized_text)
        if not match:
            continue
        slots: dict[str, str] = {}
        for key, value in match.groupdict().items():
            if not isinstance(value, str) or not value.strip():
                continue
            base_key = key.split('__', 1)[0]
            slots.setdefault(base_key, value.strip())
        _inject_literal_slots(handler, candidate.template, normalized_text, slots)
        return SentenceMatchResult(template=candidate.template, slots=slots)

    return None


def matches_sentence_template(handler: Any, text: str) -> bool:
    """Return whether text matches any configured local sentence template."""
    return match_sentence_template(handler, text) is not None


def get_local_sentence_patterns(handler: Any) -> list[_CompiledTemplate]:
    """Compile local sentence templates into strict regex patterns once."""
    if handler._local_sentence_patterns is not None:
        return handler._local_sentence_patterns

    config = handler.config or {}
    templates = config.get('local_sentence_templates', [])
    if not isinstance(templates, list):
        handler._local_sentence_patterns = []
        return handler._local_sentence_patterns

    patterns: list[_CompiledTemplate] = []
    for template in templates:
        if not isinstance(template, str) or not template.strip():
            continue
        try:
            regex = template_to_regex(handler, template, config)
            patterns.append(_CompiledTemplate(template=template, pattern=re.compile(regex)))
        except (ValueError, re.error):
            continue

    handler._local_sentence_patterns = patterns
    return handler._local_sentence_patterns


def template_to_regex(
    handler: Any,
    template: str,
    config: dict[str, Any],
    seen_tokens: set[str] | None = None,
    group_counters: dict[str, int] | None = None,
) -> str:
    """Convert a sentence template into an anchored strict regex."""
    seen_tokens = set() if seen_tokens is None else set(seen_tokens)
    group_counters = {} if group_counters is None else group_counters

    def _convert(fragment: str) -> str:
        parts: list[str] = []
        i = 0
        while i < len(fragment):
            char = fragment[i]
            if char == '[':
                end = find_matching(fragment, i, '[', ']')
                inner = _convert(fragment[i + 1:end])
                parts.append(f'(?:{inner})?')
                i = end + 1
                continue
            if char == '<':
                end = find_matching(fragment, i, '<', '>')
                token = fragment[i + 1:end].strip()
                parts.append(
                    expand_template_token(
                        handler,
                        token,
                        config,
                        slot_name=token,
                        seen_tokens=seen_tokens,
                        group_counters=group_counters,
                    )
                )
                i = end + 1
                continue
            if char == '{':
                end = find_matching(fragment, i, '{', '}')
                token = fragment[i + 1:end].split(':', 1)[0].strip()
                parts.append(
                    expand_template_token(
                        handler,
                        token,
                        config,
                        slot_name=token,
                        fallback='(?!)',
                        seen_tokens=seen_tokens,
                        group_counters=group_counters,
                    )
                )
                i = end + 1
                continue
            if char.isspace():
                parts.append(r'\s*')
            elif char in '()|':
                parts.append(char)
            else:
                parts.append(re.escape(char))
            i += 1
        return ''.join(parts)

    body = _convert(template.strip())
    return rf'^\s*{body}[\s。！？?!.，,:：]*$'


def expand_template_token(
    handler: Any,
    token: str,
    config: dict[str, Any],
    *,
    slot_name: str | None = None,
    fallback: str = '(?!)',
    seen_tokens: set[str] | None = None,
    group_counters: dict[str, int] | None = None,
) -> str:
    """Expand a rule/list token into regex."""
    seen_tokens = set() if seen_tokens is None else set(seen_tokens)
    group_counters = {} if group_counters is None else group_counters
    normalized_token = token.strip()
    strict_slot_regex = resolve_strict_slot_regex(
        handler,
        normalized_token,
        config,
        slot_name=slot_name,
        group_counters=group_counters,
    )
    if strict_slot_regex is not None:
        return strict_slot_regex

    expansion_rules = config.get('expansion_rules', {}) if isinstance(config, dict) else {}
    if normalized_token in expansion_rules and isinstance(expansion_rules[normalized_token], str):
        if normalized_token in seen_tokens:
            return fallback

        next_seen = set(seen_tokens)
        next_seen.add(normalized_token)
        body = template_to_regex_fragment(
            handler,
            expansion_rules[normalized_token],
            config,
            next_seen,
            group_counters,
        )
        return wrap_named_group(slot_name, body, group_counters) if slot_name else f'(?:{body})'

    lists_config = config.get('lists', {}) if isinstance(config, dict) else {}
    list_config = lists_config.get(normalized_token)
    if isinstance(list_config, dict):
        values = list_config.get('values')
        if isinstance(values, list):
            options: list[str] = []
            for value in values:
                if isinstance(value, str):
                    options.append(re.escape(value.strip()))
                elif isinstance(value, dict) and isinstance(value.get('in'), str):
                    options.append(re.escape(value['in'].strip()))
            if options:
                return f'(?:{"|".join(options)})'

    return fallback


def resolve_strict_slot_regex(
    handler: Any,
    token: str,
    config: dict[str, Any],
    *,
    slot_name: str | None = None,
    group_counters: dict[str, int] | None = None,
) -> str | None:
    """Resolve template slots to strict named groups."""
    if not token:
        return None

    value_options = get_slot_values(handler, token, config)
    if not value_options:
        return None

    escaped = [re.escape(value) for value in sorted(value_options, key=len, reverse=True)]
    body = f'(?:{"|".join(escaped)})'
    if slot_name:
        return wrap_named_group(slot_name, body, group_counters or {})
    return body


def get_slot_values(handler: Any, token: str, config: dict[str, Any]) -> list[str]:
    """Return allowed concrete values for a template slot."""
    lists_config = config.get('lists', {}) if isinstance(config, dict) else {}
    values: list[str] = []
    seen: set[str] = set()

    def _append(value: str | None) -> None:
        if not isinstance(value, str):
            return
        normalized = value.strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        values.append(normalized)

    list_config = lists_config.get(token)
    if isinstance(list_config, dict):
        raw_values = list_config.get('values', [])
        if isinstance(raw_values, list):
            for item in raw_values:
                if isinstance(item, str):
                    _append(item)
                elif isinstance(item, dict):
                    _append(item.get('in'))

    if not values and looks_like_entity_name_slot(token):
        for list_name, list_config in lists_config.items():
            if not isinstance(list_name, str) or not list_name.endswith('_names'):
                continue
            if not isinstance(list_config, dict):
                continue
            raw_values = list_config.get('values', [])
            if not isinstance(raw_values, list):
                continue
            for item in raw_values:
                if isinstance(item, str):
                    _append(item)
                elif isinstance(item, dict):
                    _append(item.get('in'))

        try:
            for entity_id in handler.hass.states.async_entity_ids():
                state = handler.hass.states.get(entity_id)
                if state is None:
                    continue
                _append(getattr(state, 'name', None))
                attributes = getattr(state, 'attributes', {}) or {}
                _append(attributes.get('friendly_name'))
        except Exception:
            pass

    return values


def looks_like_entity_name_slot(token: str) -> bool:
    """Return whether a slot token is intended to capture an entity name."""
    normalized = token.strip().lower()
    return normalized == 'name' or normalized.endswith('_name')


def template_to_regex_fragment(
    handler: Any,
    fragment: str,
    config: dict[str, Any],
    seen_tokens: set[str] | None = None,
    group_counters: dict[str, int] | None = None,
) -> str:
    """Convert a template fragment into a non-anchored regex."""
    regex = template_to_regex(handler, fragment, config, seen_tokens, group_counters)
    prefix = '^\\s*'
    suffix = '[\\s。！？?!.，,:：]*$'
    if regex.startswith(prefix):
        regex = regex[len(prefix):]
    if regex.endswith(suffix):
        regex = regex[:-len(suffix)]
    return regex


def find_matching(text: str, start: int, opener: str, closer: str) -> int:
    """Find the matching closing delimiter."""
    depth = 0
    for index in range(start, len(text)):
        if text[index] == opener:
            depth += 1
        elif text[index] == closer:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f'Unmatched template delimiter: {opener}')


def wrap_named_group(slot_name: str | None, body: str, group_counters: dict[str, int]) -> str:
    """Wrap regex body in a uniquely named capture group."""
    if not slot_name:
        return f'(?:{body})'

    safe_name = re.sub(r'\W+', '_', slot_name.strip())
    if not safe_name:
        return f'(?:{body})'
    if safe_name[0].isdigit():
        safe_name = f'slot_{safe_name}'

    count = group_counters.get(safe_name, 0) + 1
    group_counters[safe_name] = count
    group_name = safe_name if count == 1 else f'{safe_name}__{count}'
    return f'(?P<{group_name}>{body})'


def _inject_literal_slots(handler: Any, template: str, normalized_text: str, slots: dict[str, str]) -> None:
    """Backfill semantic slots from matched yaml literals when templates use raw words."""
    global_config = handler._get_global_device_control_config()

    if 'turn_on' not in slots:
        for keyword in global_config.get('on_keywords', []):
            normalized_keyword = keyword.strip().lower() if isinstance(keyword, str) else ''
            if normalized_keyword and normalized_keyword in template and normalized_keyword in normalized_text:
                slots['turn_on'] = normalized_keyword
                break

    if 'turn_off' not in slots:
        for keyword in global_config.get('off_keywords', []):
            normalized_keyword = keyword.strip().lower() if isinstance(keyword, str) else ''
            if normalized_keyword and normalized_keyword in template and normalized_keyword in normalized_text:
                slots['turn_off'] = normalized_keyword
                break

    if 'all' not in slots:
        for keyword in global_config.get('global_keywords', []):
            normalized_keyword = keyword.strip().lower() if isinstance(keyword, str) else ''
            if normalized_keyword and normalized_keyword in template and normalized_keyword in normalized_text:
                slots['all'] = normalized_keyword
                break


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

        should_handle = matches_sentence_template(self, text_lower)
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

    async def handle(self, text: str, language: str = "zh-CN"):
        """处理本地意图."""
        match_result = match_sentence_template(self, text)
        if match_result is None:
            return None

        global_config = self._get_global_device_control_config()
        is_on, is_off = self._resolve_action_from_match(match_result)

        if not (is_on or is_off):
            return None

        # 解析设备、设备类型和区域
        area_names, device_types = self._parse_device_and_area(global_config, match_result.slots)
        target_entities = self._match_named_entities(match_result.slots, device_types or None, area_names)
        has_global_keyword = self._resolve_global_from_match(match_result, global_config)
        requested_name = match_result.slots.get('name')

        if requested_name and not target_entities:
            return None

        if not device_types and not target_entities:
            return None

        if device_types and not target_entities and not area_names and not has_global_keyword:
            return None

        # 执行通用开关控制
        return await self._execute_control(
            area_names, device_types, is_on, global_config, language, target_entities
        )

    def _resolve_action_from_match(
        self,
        match_result: SentenceMatchResult,
    ) -> tuple[bool, bool]:
        """Resolve action direction from the matched yaml sentence."""
        if match_result.slots.get('turn_on'):
            return True, False
        if match_result.slots.get('turn_off'):
            return False, True
        return False, False

    def _resolve_global_from_match(
        self,
        match_result: SentenceMatchResult,
        global_config: dict[str, Any],
    ) -> bool:
        """Resolve global-control intent from matched slots or matched yaml literals."""
        return bool(match_result.slots.get('all'))

    def _parse_device_and_area(self, global_config: dict, slots: dict[str, str]) -> tuple:
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
                    normalized_area = area.strip().lower() if isinstance(area, str) else ''
                    if normalized_area and (
                        slots.get('area_names') == normalized_area
                        or slots.get('area') == normalized_area
                    ):
                        area_names.append(area)
        except Exception:
            pass

        # 获取设备类型，只依赖已匹配槽位
        lists_config = config.get('lists', {}) if config else {}
        for domain in global_config.get('control_domains', []):
            list_names = [f'{domain}_names']
            if domain == 'device_tracker' and 'tracker_names' in lists_config:
                list_names.append('tracker_names')

            for list_name in list_names:
                slot_value = slots.get(list_name) or slots.get('name')
                if not slot_value:
                    continue

                keywords_list = lists_config.get(list_name, {}).get('values', [])
                if not isinstance(keywords_list, list):
                    continue

                for keyword in keywords_list:
                    normalized_keyword = keyword.strip().lower() if isinstance(keyword, str) else ''
                    if normalized_keyword and slot_value == normalized_keyword:
                        device_types.append(domain)
                        break

                if domain in device_types:
                    break

        return area_names, list(set(device_types))

    def _match_named_entities(
        self,
        slots: dict[str, str],
        allowed_domains: list[str] | None = None,
        area_names: list[str] | None = None,
    ) -> list[str]:
        """Match exposed entities by friendly name from the utterance."""
        area_names = area_names or []
        matches: list[tuple[str, str]] = []
        requested_name = slots.get('name')
        if not requested_name:
            return []

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
                if normalized_name == requested_name:
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

            devices_by_domain = {}
            for device_id in all_devices:
                domain = device_id.split('.')[0]
                if domain not in devices_by_domain:
                    devices_by_domain[domain] = []
                devices_by_domain[domain].append(device_id)

            for domain, devices in devices_by_domain.items():
                service_name = domain_services.get(domain, {}).get(service_key, service_key)
                success, errors, failed = await self._execute_device_operations(
                    devices, domain, service_name
                )
                all_success += success
                all_errors += errors
                all_failed_devices.extend(failed)

            fail_msg = self._format_failure_message(all_errors, all_failed_devices)
            area_text = area_names[0] if area_names else ""
            if all_success == 0 and all_errors > 0:
                message = self._format_response_message(
                    'error',
                    error=fail_msg.strip('，, ') or "state verification failed",
                )
                return self._create_response(language, message, is_error=True)

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
        if area_name in target_areas:
            return True
        area_lower = area_name.lower()
        for target in target_areas:
            if target.lower() in area_lower or area_lower in target.lower():
                return True
        return False

    def _expected_state_after_service(
        self,
        domain: str,
        service_name: str,
        before_state: str | None,
    ) -> str | None:
        if service_name == "turn_on" and domain in {"light", "switch", "fan", "input_boolean", "automation"}:
            return "on"
        if service_name == "turn_off" and domain in {"light", "switch", "fan", "input_boolean", "automation"}:
            return "off"
        if service_name == "toggle" and domain in {"light", "switch", "fan", "input_boolean"}:
            if before_state == "on":
                return "off"
            if before_state == "off":
                return "on"
        if domain == "cover" and service_name in {"open_cover", "turn_on"}:
            return "open"
        if domain == "cover" and service_name in {"close_cover", "turn_off"}:
            return "closed"
        if domain == "lock" and service_name == "lock":
            return "locked"
        if domain == "lock" and service_name == "unlock":
            return "unlocked"
        if domain == "valve" and service_name == "open_valve":
            return "open"
        if domain == "valve" and service_name == "close_valve":
            return "closed"
        if domain == "media_player" and service_name == "media_play":
            return "playing"
        if domain == "media_player" and service_name == "media_pause":
            return "paused"
        return None

    async def _verify_device_operation(
        self,
        device_id: str,
        domain: str,
        service_name: str,
        before_state: str | None,
    ) -> bool:
        expected = self._expected_state_after_service(domain, service_name, before_state)
        if expected is None:
            return True

        global_config = get_global_config() or {}
        device_ops = global_config.get('device_operations', {})
        verification = device_ops.get('verification', {})
        wait_times = verification.get('wait_times', [0.15, 0.35, 0.7])
        timeout = float(verification.get('total_timeout', 2))
        deadline = time.monotonic() + max(0.5, timeout)

        for wait_time in wait_times:
            state = self.hass.states.get(device_id)
            if state is not None and state.state == expected:
                return True
            if time.monotonic() >= deadline:
                break
            await asyncio.sleep(float(wait_time))

        state = self.hass.states.get(device_id)
        return bool(state is not None and state.state == expected)

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
                before_state_obj = self.hass.states.get(device_id)
                before_state = before_state_obj.state if before_state_obj else None
                data = {'entity_id': device_id, **service_data}
                await self.hass.services.async_call(domain, service_name, data, blocking=True)
                verified = await self._verify_device_operation(
                    device_id,
                    domain,
                    service_name,
                    before_state,
                )
                if verified:
                    success_count += 1
                else:
                    error_count += 1
                    failed_devices.append(self._get_device_friendly_name(device_id))
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
