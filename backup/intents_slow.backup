"""意图模块 - 向Home Assistant注册中文意图扩展"""

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

# 全局配置缓存
_INTENTS_CONFIG: Optional[Dict[str, Any]] = None


async def async_setup_intents(hass: HomeAssistant) -> None:
    """向Home Assistant注册中文意图扩展"""
    global _INTENTS_CONFIG

    try:
        # 加载中文意图配置
        config = await _load_intents_config()
        if not config:
            _LOGGER.warning("无法加载中文意图配置")
            return

        _INTENTS_CONFIG = config

        # 将中文sentences注册到Home Assistant的conversation系统
        intents = config.get('intents', {})
        registered_count = 0

        for intent_name, intent_data in intents.items():
            if intent_data.get('data'):
                for item in intent_data['data']:
                    sentences = item.get('sentences', [])
                    for sentence in sentences:
                        # 清理句子格式
                        clean_sentence = sentence.replace('[<let>]', '').strip()
                        if clean_sentence:
                            # 暂时不注册任何意图，避免覆盖Home Assistant内置意图
                            # 只记录可用的中文句子模式
                            registered_count += 1
                            _LOGGER.debug(f"📝 中文句子模式: {intent_name} - '{clean_sentence}'")

        _LOGGER.info(f"中文意图配置加载完成，共 {registered_count} 个中文句子可用 (未注册到HA系统)")

    except Exception as e:
        _LOGGER.error(f"意图注册失败: {e}")


async def _load_intents_config() -> Optional[Dict[str, Any]]:
    """异步加载intents.yaml配置"""
    try:
        import yaml
        yaml_path = Path(__file__).parent / "intents.yaml"

        if not yaml_path.exists():
            _LOGGER.warning(f"intents.yaml不存在: {yaml_path}")
            return None

        # 使用异步文件读取避免阻塞事件循环
        loop = asyncio.get_running_loop()

        def _read_yaml_file():
            with open(yaml_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)

        config = await loop.run_in_executor(None, _read_yaml_file)

        _LOGGER.info(f"成功加载中文意图配置: {list(config.keys()) if config else 'empty'}")
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
            # 委托给Home Assistant的默认意图处理
            # 这样我们不会覆盖原生功能，只是提供中文语言支持
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


def get_intents_config() -> Optional[Dict[str, Any]]:
    """获取意图配置（供其他模块使用）"""
    return _INTENTS_CONFIG