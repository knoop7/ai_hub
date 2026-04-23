"""配置缓存管理器 - 避免重复加载配置文件."""

from __future__ import annotations

import logging
from typing import Any

from .handlers import get_device_control_config

_LOGGER = logging.getLogger(__name__)


class ConfigCache:
    """配置缓存管理器，使用 loader 模块的全局缓存."""

    def _get_ai_hub_intent_config(self) -> dict[str, Any]:
        """Get AI Hub specific config from the merged intent structure."""
        config = self.get_config()
        if not config:
            return {}

        if isinstance(config.get('local_intents'), dict):
            return config

        intents = config.get('intents', {})
        if isinstance(intents, dict) and isinstance(intents.get('ai_hub'), dict):
            return intents['ai_hub']

        return {}

    def get_config(self, force_reload: bool = False) -> dict[str, Any] | None:
        """获取配置，使用 loader 的缓存."""
        from .loader import get_global_config, reload_config

        if force_reload:
            return reload_config()
        return get_global_config()

    def _get_defaults(self) -> dict[str, Any]:
        """获取默认配置.

        在新架构中, defaults 位于 device_operations.defaults 下;
        同时兼容旧架构的顶级 defaults 键.
        """
        config = self._get_ai_hub_intent_config()
        if not config:
            return {}
        if 'defaults' in config:
            return config['defaults']
        device_ops = config.get('device_operations', {})
        if 'defaults' in device_ops:
            return device_ops['defaults']
        return {}

    def get_global_keywords(self) -> list[str]:
        """获取全局关键词."""
        config = self._get_ai_hub_intent_config()
        global_config = get_device_control_config(config.get('local_intents', {}))
        if global_config and 'global_keywords' in global_config:
            return global_config['global_keywords']

        # 如果没有，从默认配置获取
        defaults = self._get_defaults()
        return defaults.get('global_keywords', ["所有", "全部", "一切"])

    def get_local_features(self) -> list[str]:
        """获取本地特征关键词."""
        config = self._get_ai_hub_intent_config()
        expansion_rules = config.get('expansion_rules', {})
        local_features = []
        for value in expansion_rules.values():
            if isinstance(value, str) and '|' in value:
                local_features.extend(value.split('|'))
        if local_features:
            return local_features

        # 如果没有，从默认配置获取
        defaults = self._get_defaults()
        return defaults.get('local_features', ["所有设备", "全部设备", "所有灯", "全部灯"])

    def get_responses_config(self) -> dict[str, Any]:
        """获取响应配置."""
        config = self._get_ai_hub_intent_config()
        if config and 'responses' in config:
            return config['responses']
        return {}

    def get_verification_config(self) -> dict[str, Any]:
        """获取验证配置.

        在新架构中, verification 位于 device_operations.verification 下;
        同时兼容旧架构的顶级 verification 和 defaults.verification 键.
        """
        config = self._get_ai_hub_intent_config()
        if config:
            device_ops = config.get('device_operations', {})
            if 'verification' in device_ops:
                return device_ops['verification']
            if 'verification' in config:
                return config['verification']
            defaults = self._get_defaults()
            if 'verification' in defaults:
                return defaults['verification']

        return {
            'total_timeout': 3,
            'max_retries': 3,
            'wait_times': [0.5, 0.8, 1.1]
        }

    def get_device_state_simulation(self) -> dict[str, Any]:
        """获取设备状态模拟配置."""
        defaults = self._get_defaults()
        return defaults.get('device_state_simulation', {
            "lights": {"living_room_main": "off", "living_room_ambient": "on"},
            "switches": {},
            "climate": {},
            "covers": {},
            "media_players": {},
            "locks": {},
            "vacuums": {}
        })

    def get_error_message(self, message_key: str) -> str:
        """获取错误消息."""
        defaults = self._get_defaults()
        error_messages = defaults.get('error_messages', {})
        return error_messages.get(message_key, f"未知错误: {message_key}")

    def get_timeout_config(self, timeout_key: str, default_value: int = 3) -> int:
        """获取超时配置."""
        defaults = self._get_defaults()
        timeouts = defaults.get('timeouts', {})
        return timeouts.get(timeout_key, default_value)


# 全局配置缓存实例
_config_cache = ConfigCache()


def get_config_cache() -> ConfigCache:
    """获取配置缓存实例."""
    return _config_cache
