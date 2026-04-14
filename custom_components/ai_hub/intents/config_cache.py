"""配置缓存管理器 - 避免重复加载配置文件."""

from __future__ import annotations

import logging
from typing import Any

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
        """获取默认配置."""
        config = self._get_ai_hub_intent_config()
        if config:
            return config.get('defaults', {})
        return {}

    def get_global_keywords(self) -> list[str]:
        """获取全局关键词."""
        config = self._get_ai_hub_intent_config()
        global_config = config.get('local_intents', {}).get('GlobalDeviceControl', {})
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

    def get_automation_config(self, key: str, default_value=None) -> Any:
        """获取自动化配置."""
        config = self._get_ai_hub_intent_config()
        if config:
            if key in config:
                return config[key]
            defaults = config.get('defaults', {})
            if key in defaults:
                return defaults[key]

        # 如果都没有，返回传入的默认值
        return default_value

    def get_responses_config(self) -> dict[str, Any]:
        """获取响应配置."""
        config = self._get_ai_hub_intent_config()
        if config:
            if 'responses' in config:
                return config['responses']
            defaults = config.get('defaults', {})
            if 'responses' in defaults:
                return defaults['responses']

        return {}

    def get_verification_config(self) -> dict[str, Any]:
        """获取验证配置."""
        config = self._get_ai_hub_intent_config()
        if config:
            if 'verification' in config:
                return config['verification']
            defaults = config.get('defaults', {})
            if 'verification' in defaults:
                return defaults['verification']

        # 最后的硬编码备用值
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
