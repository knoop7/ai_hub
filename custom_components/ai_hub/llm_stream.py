"""Streaming helpers for AI Hub LLM responses."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import aiohttp
from homeassistant.components import conversation
from homeassistant.helpers import llm
from homeassistant.util import ulid

from .markdown_filter import filter_markdown_streaming

_LOGGER = logging.getLogger(__name__)


async def transform_stream(
    response: aiohttp.ClientResponse,
) -> AsyncGenerator[
    conversation.AssistantContentDeltaDict | conversation.ToolResultContentDeltaDict
]:
    """Transform AI Hub SSE stream into Home Assistant deltas."""
    buffer = ""
    tool_call_buffer: dict[int, dict[str, Any]] = {}
    has_started = False

    async for chunk in response.content:
        if not chunk:
            continue

        buffer += chunk.decode("utf-8", errors="ignore")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line or line == "data: [DONE]":
                continue
            if not line.startswith("data: "):
                continue

            data_str = line[6:]
            if not data_str.strip():
                continue
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                _LOGGER.debug("SSE data parse failed: %s", data_str)
                continue

            if not data.get("choices"):
                continue
            delta = data["choices"][0].get("delta", {})
            if not has_started:
                yield {"role": "assistant"}
                has_started = True
            if "content" in delta and delta["content"]:
                yield {"content": filter_markdown_streaming(delta["content"])}
            if "tool_calls" in delta:
                for tc_delta in delta["tool_calls"]:
                    index = tc_delta.get("index", 0)
                    if index not in tool_call_buffer:
                        tool_id = tc_delta.get("id")
                        if not tool_id or not isinstance(tool_id, str) or not tool_id.strip():
                            tool_id = ulid.ulid_now()
                        tool_call_buffer[index] = {
                            "id": tool_id,
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    if (
                        "id" in tc_delta
                        and tc_delta["id"]
                        and isinstance(tc_delta["id"], str)
                        and tc_delta["id"].strip()
                    ):
                        tool_call_buffer[index]["id"] = tc_delta["id"]
                    if "function" in tc_delta:
                        func = tc_delta["function"]
                        if "name" in func:
                            tool_call_buffer[index]["function"]["name"] = func["name"]
                        if "arguments" in func:
                            tool_call_buffer[index]["function"]["arguments"] += func["arguments"]

    if tool_call_buffer:
        tool_calls = []
        for tc in tool_call_buffer.values():
            try:
                tool_id = tc["id"]
                if not tool_id or not isinstance(tool_id, str) or not tool_id.strip():
                    tool_id = ulid.ulid_now()
                args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                tool_calls.append(
                    llm.ToolInput(
                        id=tool_id,
                        tool_name=tc["function"]["name"],
                        tool_args=args,
                    )
                )
            except json.JSONDecodeError as err:
                _LOGGER.warning("Failed to parse tool call arguments: %s", err)

        if tool_calls:
            yield {"tool_calls": tool_calls}
