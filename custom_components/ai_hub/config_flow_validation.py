"""Validation helpers for AI Hub config flows."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .consts import (
    AI_HUB_CHAT_URL,
    CONFIG_FLOW_TEST_MAX_TOKENS,
    CONFIG_FLOW_TEST_MESSAGE,
    RECOMMENDED_CHAT_MODEL,
    SILICONFLOW_API_KEY_URL,
    SILICONFLOW_REGISTER_URL,
    TIMEOUT_CONFIG_FLOW_VALIDATION,
)
from .http import build_json_headers, client_timeout

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
        "model": RECOMMENDED_CHAT_MODEL,
        "messages": [{"role": "user", "content": CONFIG_FLOW_TEST_MESSAGE}],
        "max_tokens": CONFIG_FLOW_TEST_MAX_TOKENS,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                AI_HUB_CHAT_URL,
                json=payload,
                headers=build_json_headers(api_key),
                timeout=client_timeout(TIMEOUT_CONFIG_FLOW_VALIDATION),
            ) as response:
                if response.status == 401:
                    raise ValueError("invalid_auth")
                if response.status != 200:
                    error_text = await response.text()
                    detail = error_text if error_text.strip() else f"HTTP {response.status}"
                    raise ValueError(f"cannot_connect:{detail}")
    except aiohttp.ClientError as err:
        detail = str(err).strip() or type(err).__name__
        raise ValueError(f"cannot_connect:{detail}") from err
    except asyncio.TimeoutError as err:
        detail = str(err).strip() or type(err).__name__
        raise ValueError(f"cannot_connect:{detail}") from err
