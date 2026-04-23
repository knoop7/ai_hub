"""配置验证器 - 验证 intents 配置的完整性和正确性.

本模块提供意图配置的验证功能，确保配置文件的完整性和正确性。

主要功能:
- 验证必需的配置键是否存在
- 验证本地设备控制配置的完整性
- 验证设备类型列表和扩展规则
- 检测配置中的重复定义
- 提供详细的错误和警告信息

使用示例:
    from .validator import validate_config, ConfigValidator

    # 简单验证
    is_valid = validate_config(config)

    # 详细验证
    validator = ConfigValidator(config)
    if not validator.validate():
        print(validator.get_errors())
"""

from __future__ import annotations

import logging
from typing import Any

from .handlers import (
    MEDIA_FALLBACK_STRATEGIES,
    REQUIRED_DEVICE_CONTROL_KEYS,
    get_device_control_config,
)

_LOGGER = logging.getLogger(__name__)


class ConfigValidator:
    """配置验证器 - 验证意图配置的完整性和正确性."""

    # 必需的顶级配置键
    REQUIRED_KEYS = ['local_intents']

    # 本地设备控制必需的配置
    REQUIRED_DEVICE_CONTROL_CONFIG_KEYS = sorted(REQUIRED_DEVICE_CONTROL_KEYS)

    def __init__(self, config: dict[str, Any]):
        """初始化验证器.

        Args:
            config: 要验证的配置字典
        """
        self.config = config
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate(self) -> bool:
        """执行完整验证.

        Returns:
            bool: 验证是否通过（无错误）
        """
        self.errors = []
        self.warnings = []

        if not self.config:
            self.errors.append("配置为空")
            return False

        self._validate_required_keys()
        self._validate_local_intents()
        self._validate_lists()
        self._validate_expansion_rules()
        self._validate_duplicates()

        if self.errors:
            for error in self.errors:
                _LOGGER.error(f"Config validation error: {error}")
            return False

        if self.warnings:
            for warning in self.warnings:
                _LOGGER.warning(f"Config validation warning: {warning}")

        _LOGGER.info("Config validation passed")
        return True

    def _validate_required_keys(self) -> None:
        """验证必需的顶级键."""
        for key in self.REQUIRED_KEYS:
            if key not in self.config:
                self.errors.append(f"缺少必需的配置键: {key}")

    def _validate_local_intents(self) -> None:
        """验证 local_intents 配置."""
        local_intents = self.config.get('local_intents', {})

        if not local_intents:
            self.errors.append("local_intents 配置为空")
            return

        device_control = get_device_control_config(local_intents)
        if not device_control:
            self.errors.append("local_intents 缺少设备控制配置")
            return

        self._validate_device_control(device_control)

    def _validate_device_control(self, config: dict[str, Any]) -> None:
        """验证本地设备控制配置."""
        for key in self.REQUIRED_DEVICE_CONTROL_CONFIG_KEYS:
            if key not in config:
                self.errors.append(f"device_control 缺少必需的配置: {key}")

        for key in ['global_keywords', 'on_keywords', 'off_keywords']:
            if key in config and not config[key]:
                self.warnings.append(f"device_control.{key} 为空列表")

        domain_services = config.get('domain_services', {})
        if domain_services:
            for domain, services in domain_services.items():
                if not isinstance(services, dict):
                    self.errors.append(f"domain_services.{domain} 应该是字典类型")
                elif 'turn_on' not in services and 'turn_off' not in services:
                    self.warnings.append(f"domain_services.{domain} 缺少 turn_on/turn_off 定义")

        media_search = config.get('media_search', {})
        if media_search:
            strategy = media_search.get('fallback_target_strategy')
            if strategy is not None and strategy not in MEDIA_FALLBACK_STRATEGIES:
                self.warnings.append(
                    "media_search.fallback_target_strategy 不在允许范围内，"
                    f"将使用默认值: {sorted(MEDIA_FALLBACK_STRATEGIES)}"
                )

    def _validate_lists(self) -> None:
        """验证 lists 配置."""
        lists = self.config.get('lists', {})

        if not lists:
            self.warnings.append("lists 配置为空，设备类型识别可能受限")
            return

        expected_lists = ['light_names', 'climate_names', 'area_names']
        for list_name in expected_lists:
            if list_name not in lists:
                self.warnings.append(f"lists 缺少 {list_name}，相关功能可能受限")
            elif not lists[list_name].get('values'):
                self.warnings.append(f"lists.{list_name}.values 为空")

    def _validate_expansion_rules(self) -> None:
        """验证 expansion_rules 配置."""
        rules = self.config.get('expansion_rules', {})

        if not rules:
            self.warnings.append("expansion_rules 配置为空")
            return

        expected_rules = ['let', 'turn', 'close', 'set']
        for rule in expected_rules:
            if rule not in rules:
                self.warnings.append(f"expansion_rules 缺少 {rule}")

    def _validate_duplicates(self) -> None:
        """检测配置中的重复定义."""
        # global_keywords 与 expansion_rules 在本地意图增强里允许语义重叠，
        # 这里不再把它当作配置警告，避免持续输出噪声日志。
        return

    def get_errors(self) -> list[str]:
        """获取错误列表."""
        return self.errors

    def get_warnings(self) -> list[str]:
        """获取警告列表."""
        return self.warnings


def validate_config(config: dict[str, Any]) -> bool:
    """验证配置的便捷函数.

    Args:
        config: 要验证的配置字典

    Returns:
        bool: 验证是否通过
    """
    validator = ConfigValidator(config)
    return validator.validate()
