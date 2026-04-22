"""Shared helpers for compatible LLM providers."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from ..http import async_check_endpoint_health


def finalize_buffered_tool_calls(
    tool_call_buffer: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert buffered tool-call fragments into normalized tool calls."""
    tool_calls = []
    for tool_call in tool_call_buffer.values():
        try:
            arguments = tool_call["function"].get("arguments", "")
            parsed_args = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            parsed_args = {}
        tool_calls.append(
            {
                "id": tool_call["id"],
                "type": "function",
                "function": {
                    "name": tool_call["function"].get("name", "tool"),
                    "arguments": json.dumps(parsed_args, ensure_ascii=False),
                },
            }
        )
    return tool_calls


async def check_provider_health(
    api_url: str,
    *,
    ssl: bool | None,
    timeout: float = 10,
) -> bool:
    """Check endpoint health using the provider base URL."""
    parsed = urlparse(api_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return await async_check_endpoint_health(base, ssl=ssl, timeout=timeout)
