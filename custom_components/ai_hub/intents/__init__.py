"""意图模块 - 模块化重构版本."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant

from .config_cache import ConfigCache, get_config_cache
from .loader import (
    async_setup_intents,
    get_intents_config,
    get_device_operations_config,
    get_device_verification_config,
    is_device_operation,
)
from .handlers import (
    ChineseIntentHandler,
    LocalIntentHandler,
    get_global_intent_handler,
    get_local_intents_config,
)

_LOGGER = logging.getLogger(__name__)

# 导出所有公共接口
__all__ = [
    # 配置缓存
    "ConfigCache",
    "get_config_cache",
    # 配置加载
    "async_setup_intents",
    "get_intents_config",
    "get_device_operations_config",
    "get_device_verification_config",
    "is_device_operation",
    # 意图处理器
    "ChineseIntentHandler",
    "LocalIntentHandler",
    "get_global_intent_handler",
    "get_local_intents_config",
]
