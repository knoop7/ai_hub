"""WeChat services for AI Hub - 微信通知功能.

本模块提供微信消息推送服务，使用巴法云 (Bemfa) API。

主要函数:
- handle_send_wechat_message: 发送微信消息通知

使用前需要:
1. 注册巴法云账号
2. 关注巴法云微信公众号
3. 在集成配置中设置巴法云 UID
"""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.core import HomeAssistant, ServiceCall

from ..const import BEMFA_API_URL

_LOGGER = logging.getLogger(__name__)


async def handle_send_wechat_message(
    hass: HomeAssistant,
    call: ServiceCall,
    bemfa_uid: str
) -> dict:
    """Handle Bemfa WeChat message service call."""
    try:
        if not bemfa_uid or not bemfa_uid.strip():
            return {
                "success": False,
                "error": "巴法云UID未配置，请在集成配置中设置或通过服务参数提供"
            }

        device_entity = call.data["device_entity"]
        message = call.data["message"].strip()
        url = call.data.get("url", "")

        if not device_entity or not message:
            return {"success": False, "error": "device_entity 和 message 参数必填"}

        state_obj = hass.states.get(device_entity)
        if state_obj:
            friendly_name = state_obj.attributes.get("friendly_name", device_entity)
            state_value = state_obj.state
        else:
            friendly_name = device_entity
            state_value = "无实体状态"

        device_title = f"{friendly_name}（状态：{state_value}）"

        _LOGGER.debug("WeChat device title: %s", device_title)
        _LOGGER.debug("WeChat message content: %s", message)

        payload = {
            "uid": bemfa_uid,
            "device": device_title,
            "message": message,
            "group": "default",
            "url": url,
        }

        headers = {"Content-Type": "application/json; charset=utf-8"}
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(BEMFA_API_URL, json=payload, headers=headers) as response:
                resp_text = await response.text()
                if response.status == 200:
                    _LOGGER.info("WeChat message sent successfully")
                    return {
                        "success": True,
                        "message": "WeChat message sent successfully",
                        "device": device_entity
                    }
                else:
                    _LOGGER.error("Send failed [%s]: %s", response.status, resp_text)
                    return {"success": False, "error": f"Send failed [{response.status}]: {resp_text}"}

    except aiohttp.ClientError as exc:
        _LOGGER.error("Network request error: %s", exc)
        return {"success": False, "error": f"Network request error: {exc}"}
    except Exception as exc:
        _LOGGER.exception("发送微信消息异常: %s", exc)
        return {"success": False, "error": f"发送微信消息异常: {exc}"}
