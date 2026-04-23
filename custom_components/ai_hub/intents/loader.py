"""意图配置加载器 - 支持多文件加载和合并."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict

from homeassistant.components.homeassistant import exposed_entities
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er

_LOGGER = logging.getLogger(__name__)

# 全局配置缓存
_INTENTS_CONFIG: dict[str, Any] | None = None
_CONFIG_LOADED = False

# 配置文件列表（按加载顺序）
CONFIG_FILES = [
    "_common.yaml",
    "auto_lists.yaml",
]

# 配置子目录（自动扫描所有 .yaml 文件）
CONFIG_DIRS = [
    "sentences",
    "responses",
]

# 固定追加文件（在目录扫描之后加载）
CONFIG_TAIL_FILES = [
    "local_control.yaml",
]

DOMAIN_TO_LIST = {
    "light": "light_names",
    "climate": "climate_names",
    "fan": "fan_names",
    "media_player": "media_player_names",
    "cover": "cover_names",
    "switch": "switch_names",
    "vacuum": "vacuum_names",
    "camera": "camera_names",
    "lock": "lock_names",
    "valve": "valve_names",
    "sensor": "sensor_names",
    "device_tracker": "tracker_names",
}

AUTO_LISTS_PATH = Path(__file__).parent / "config" / "auto_lists.yaml"


def _get_fallback_config() -> dict[str, Any]:
    """获取备用配置（仅当配置读取失败时使用）."""
    return {
        'light': ['light.turn_on', 'light.turn_off', 'light.toggle'],
        'switch': ['switch.turn_on', 'switch.turn_off', 'switch.toggle'],
        'climate': ['climate.turn_on', 'climate.turn_off'],
        'fan': ['fan.turn_on', 'fan.turn_off'],
        'cover': ['cover.open_cover', 'cover.close_cover'],
        'media_player': ['media_player.media_play', 'media_player.media_pause'],
        'lock': ['lock.lock', 'lock.unlock'],
        'vacuum': ['vacuum.start', 'vacuum.stop'],
        'script': ['script.turn_on', 'script.turn_off']
    }


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """深度合并两个字典，override 覆盖 base.

    Lists under 'data' and 'values' keys are concatenated rather than replaced,
    allowing multiple sentence files to contribute to the same intent,
    and auto_lists to supplement (not replace) static list values.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif key in ("data", "values") and isinstance(result.get(key), list) and isinstance(value, list):
            result[key] = result[key] + value
        else:
            result[key] = value
    return result


def _normalize_list_value(value: str) -> str:
    """Normalize values for list deduplication."""
    return " ".join(value.strip().split()).casefold()


def _deduplicate_list_values(config: dict) -> dict:
    """Remove duplicate entries from list values after merge."""
    lists = config.get('lists', {})
    for list_name, list_data in lists.items():
        if not isinstance(list_data, dict):
            continue
        values = list_data.get('values')
        if not isinstance(values, list):
            continue
        seen = set()
        deduped = []
        for item in values:
            if isinstance(item, str):
                key = _normalize_list_value(item)
                if key not in seen:
                    seen.add(key)
                    deduped.append(item)
            elif isinstance(item, dict):
                key = _normalize_list_value(item.get('in', ''))
                if key not in seen:
                    seen.add(key)
                    deduped.append(item)
            else:
                if item not in deduped:
                    deduped.append(item)
        list_data['values'] = deduped
    return config


def _append_unique_value(target: list[str], seen: set[str], value: str | None) -> None:
    """Append value if non-empty and unique."""
    if not value:
        return

    value = value.strip()
    if not value:
        return

    normalized = _normalize_list_value(value)
    if normalized in seen:
        return

    seen.add(normalized)
    target.append(value)


def _build_auto_lists_config(hass: HomeAssistant) -> dict[str, Any]:
    """Build auto-generated lists from HA areas and entities."""
    area_reg = ar.async_get(hass)
    entity_reg = er.async_get(hass)

    lists: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)

    for area in area_reg.areas.values():
        _append_unique_value(lists["area_names"], seen["area_names"], area.name)

    for entity_id in hass.states.async_entity_ids():
        state = hass.states.get(entity_id)
        if state is None:
            continue

        if not exposed_entities.async_should_expose(hass, "conversation", entity_id):
            continue

        domain = entity_id.split(".", 1)[0]
        list_name = DOMAIN_TO_LIST.get(domain)
        if list_name is None:
            continue

        _append_unique_value(lists[list_name], seen[list_name], state.name)

        registry_entry = entity_reg.async_get(entity_id)
        if registry_entry is not None:
            _append_unique_value(lists[list_name], seen[list_name], registry_entry.original_name)
            _append_unique_value(lists[list_name], seen[list_name], registry_entry.name)

    return {
        "lists": {
            key: {"values": values}
            for key, values in sorted(lists.items())
            if values
        }
    }


def _sync_auto_lists_config_sync(data: dict[str, Any]) -> bool:
    """Write auto-generated list config if content changed."""
    import yaml  # type: ignore[import]

    serialized = (
        "# This file is auto-generated by AI Hub.\n"
        "# It supplements _common.yaml with Home Assistant areas and entity names.\n"
        "# Manual edits may be overwritten.\n\n"
        + yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    )

    if AUTO_LISTS_PATH.exists():
        current = AUTO_LISTS_PATH.read_text(encoding="utf-8")
        if current == serialized:
            return False

    AUTO_LISTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTO_LISTS_PATH.write_text(serialized, encoding="utf-8")
    return True


async def async_sync_intent_lists(hass: HomeAssistant) -> bool:
    """Sync HA areas and entity names into auto-generated auto_lists.yaml."""
    global _INTENTS_CONFIG, _CONFIG_LOADED

    data = _build_auto_lists_config(hass)
    changed = await hass.async_add_executor_job(_sync_auto_lists_config_sync, data)
    if changed:
        _INTENTS_CONFIG = None
        _CONFIG_LOADED = False
        _LOGGER.debug("Auto intent lists updated from Home Assistant registry")
    return changed


def _load_intents_config_sync() -> dict[str, Any]:
    """同步加载配置 - 支持多文件合并."""
    import yaml  # type: ignore[import]

    # 优先尝试新的多文件配置
    config_dir = Path(__file__).parent / "config"

    if config_dir.exists():
        merged_config: Dict[str, Any] = {}
        loaded_files = []

        for filename in CONFIG_FILES:
            file_path = config_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_config = yaml.safe_load(f) or {}
                        merged_config = _deep_merge(merged_config, file_config)
                        loaded_files.append(filename)
                except Exception as e:
                    _LOGGER.warning(f"Failed to load config file {filename}: {e}")

        for dirname in CONFIG_DIRS:
            dir_path = config_dir / dirname
            if dir_path.exists() and dir_path.is_dir():
                for yaml_file in sorted(dir_path.glob("*.yaml")):
                    filename = f"{dirname}/{yaml_file.name}"
                    try:
                        with open(yaml_file, 'r', encoding='utf-8') as f:
                            file_config = yaml.safe_load(f) or {}
                            merged_config = _deep_merge(merged_config, file_config)
                            loaded_files.append(filename)
                    except Exception as e:
                        _LOGGER.warning(f"Failed to load config file {filename}: {e}")

        for filename in CONFIG_TAIL_FILES:
            file_path = config_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_config = yaml.safe_load(f) or {}
                        merged_config = _deep_merge(merged_config, file_config)
                        loaded_files.append(filename)
                except Exception as e:
                    _LOGGER.warning(f"Failed to load config file {filename}: {e}")

        if merged_config:
            merged_config = _deduplicate_list_values(merged_config)
            _LOGGER.debug(f"Successfully loaded config from multiple files: {loaded_files}")
            return merged_config

    _LOGGER.warning("No config files found")
    return {}


async def _load_intents_config_once() -> dict[str, Any] | None:
    """一次性加载配置 - 异步版本，支持多文件合并."""
    global _INTENTS_CONFIG, _CONFIG_LOADED

    # 如果已经加载过，直接返回
    if _CONFIG_LOADED and _INTENTS_CONFIG is not None:
        return _INTENTS_CONFIG

    try:

        # 使用异步执行器避免阻塞
        loop = asyncio.get_running_loop()
        config = await loop.run_in_executor(None, _load_intents_config_sync)

        if not config:
            _LOGGER.error("Config is empty")
            return None

        # 保存到全局变量
        _INTENTS_CONFIG = config
        _CONFIG_LOADED = True

        # 验证关键配置
        local_intents = config.get('local_intents', {})
        from .handlers import get_device_control_config
        if get_device_control_config(local_intents):
            _LOGGER.info("Intent config loaded - contains device control config")
        else:
            _LOGGER.warning("Intent config loaded - missing device control config")

        return config

    except Exception as e:
        _LOGGER.error(f"Failed to load config: {e}")
        return None


async def async_setup_intents(hass: HomeAssistant) -> None:
    """向 Home Assistant 注册中文意图扩展."""
    global _INTENTS_CONFIG

    try:
        config = await _load_intents_config_once()
        if not config:
            _LOGGER.warning("Cannot load Chinese intent config")
            return

        _INTENTS_CONFIG = config

        # 验证配置
        from .validator import validate_config
        if not validate_config(config):
            _LOGGER.warning("Intent config validation failed, some features may be limited")

        # 统计句子数量
        intents = config.get('intents', {})
        registered_count = sum(
            len(item.get('sentences', []))
            for intent_data in intents.values()
            for item in intent_data.get('data', [])
        )

        _LOGGER.info(f"Chinese intent config loaded ({registered_count} sentences)")

    except Exception as e:
        _LOGGER.error(f"Local intent initialization failed: {e}")


def get_intents_config() -> dict[str, Any] | None:
    """获取意图配置（供其他模块使用）."""
    return _INTENTS_CONFIG if _CONFIG_LOADED else None


def get_device_operations_config() -> dict[str, Any]:
    """从缓存获取设备操作配置."""
    # 使用已加载的缓存配置
    config = _INTENTS_CONFIG if _CONFIG_LOADED else _load_intents_config_sync()

    # 尝试从 device_operations.control_operations 获取
    device_ops = config.get('device_operations', {})
    if 'control_operations' in device_ops:
        return device_ops['control_operations']

    # 回退到旧路径
    return config.get('control_operations', _get_fallback_config())


def get_device_verification_config() -> dict[str, Any]:
    """从缓存获取设备验证配置."""
    # 使用已加载的缓存配置
    config = _INTENTS_CONFIG if _CONFIG_LOADED else _load_intents_config_sync()

    # 尝试从 device_operations.verification 获取
    device_ops = config.get('device_operations', {})
    if 'verification' in device_ops:
        return device_ops['verification']

    # 回退默认值
    return {
        'total_timeout': 3,
        'max_retries': 3,
        'wait_times': [0.5, 0.8, 1.1]
    }


def is_device_operation(tool_name: str) -> bool:
    """判断是否是设备控制操作."""
    config = get_device_operations_config()

    for device_type, operations in config.items():
        if isinstance(operations, list) and tool_name in operations:
            return True

    return False


def get_global_config() -> dict[str, Any] | None:
    """获取全局配置（使用缓存）."""
    global _INTENTS_CONFIG, _CONFIG_LOADED
    if _CONFIG_LOADED and _INTENTS_CONFIG:
        return _INTENTS_CONFIG
    # 如果未加载，同步加载一次
    if not _CONFIG_LOADED:
        _INTENTS_CONFIG = _load_intents_config_sync()
        _CONFIG_LOADED = True
    return _INTENTS_CONFIG


def reload_config() -> dict[str, Any]:
    """强制重新加载配置（用于调试）."""
    global _INTENTS_CONFIG, _CONFIG_LOADED
    _CONFIG_LOADED = False
    _INTENTS_CONFIG = None
    return _load_intents_config_sync()
