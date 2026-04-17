"""Validation helpers for AI Hub config flows."""

from __future__ import annotations

from typing import Any

import aiohttp
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import AI_HUB_CHAT_URL
from .http import build_json_headers, client_timeout

SILICONFLOW_REGISTER_URL = "https://cloud.siliconflow.cn/i/U3e0rmsr"
SILICONFLOW_API_KEY_URL = "https://cloud.siliconflow.cn/account/ak"
FLOW_DESCRIPTION_PLACEHOLDERS = {
    "register_url": SILICONFLOW_REGISTER_URL,
    "api_key_url": SILICONFLOW_API_KEY_URL,
}


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    del hass
    api_key = data.get(CONF_API_KEY, "").strip()
    if not api_key:
        return

    payload = {
        "model": "Qwen/Qwen3-8B",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 10,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            AI_HUB_CHAT_URL,
            json=payload,
            headers=build_json_headers(api_key),
            timeout=client_timeout(10),
        ) as response:
            if response.status == 401:
                raise ValueError("invalid_auth")
            if response.status != 200:
                await response.text()
                raise ValueError("cannot_connect")
