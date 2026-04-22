"""Anthropic-compatible LLM provider for AI Hub integration."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import urlparse

import aiohttp
from homeassistant.util import ulid

from ..http import (
    async_check_endpoint_health,
    async_post_json,
    async_stream_response_text,
    build_json_headers,
    client_timeout,
    resolve_ssl_setting,
)
from .common_compatible import check_provider_health, finalize_buffered_tool_calls
from . import LLMMessage, LLMProvider, LLMResponse

_LOGGER = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
class AnthropicCompatibleProvider(LLMProvider):
    """Anthropic Messages API provider."""

    _name = "anthropic_compatible"

    @property
    def name(self) -> str:
        return "anthropic_compatible"

    @property
    def supported_models(self) -> list[str]:
        return []

    def supports_vision(self) -> bool:
        return False

    def supports_tools(self) -> bool:
        return True

    def _get_headers(self) -> dict[str, str]:
        headers = build_json_headers(self.config.api_key)
        headers["anthropic-version"] = _ANTHROPIC_VERSION
        if self.config.api_key:
            headers["x-api-key"] = self.config.api_key
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _get_api_url(self) -> str:
        url = self.config.base_url or _DEFAULT_API_URL
        if not url:
            return _DEFAULT_API_URL

        normalized = url.rstrip("/")
        if normalized.endswith("/v1/messages"):
            return normalized
        if normalized.endswith("/messages"):
            return normalized
        if normalized.endswith("/v1"):
            return f"{normalized}/messages"
        return f"{normalized}/v1/messages"

    def _convert_content_blocks(self, content: str | list[dict[str, Any]]) -> str | list[dict[str, Any]]:
        if isinstance(content, str):
            return content

        blocks: list[dict[str, Any]] = []
        for part in content:
            if part.get("type") == "text":
                blocks.append({"type": "text", "text": str(part.get("text", ""))})
        return blocks or ""

    def _convert_messages(self, messages: list[LLMMessage]) -> tuple[str | None, list[dict[str, Any]]]:
        system_parts: list[str] = []
        converted: list[dict[str, Any]] = []

        for message in messages:
            if message.role == "system":
                if isinstance(message.content, str) and message.content.strip():
                    system_parts.append(message.content)
                continue

            if message.role in {"user", "assistant"}:
                anthropic_message: dict[str, Any] = {
                    "role": message.role,
                    "content": self._convert_content_blocks(message.content),
                }
                if message.role == "assistant" and message.tool_calls:
                    content_blocks = anthropic_message["content"]
                    if isinstance(content_blocks, str):
                        content_blocks = [{"type": "text", "text": content_blocks}] if content_blocks else []
                    for tool_call in message.tool_calls:
                        function_data = tool_call.get("function", {})
                        arguments = function_data.get("arguments", {})
                        if isinstance(arguments, str):
                            try:
                                arguments = json.loads(arguments)
                            except json.JSONDecodeError:
                                arguments = {"raw_arguments": arguments}
                        content_blocks.append(
                            {
                                "type": "tool_use",
                                "id": tool_call.get("id") or function_data.get("name", "tool_call"),
                                "name": function_data.get("name", "tool"),
                                "input": arguments if isinstance(arguments, dict) else {"value": arguments},
                            }
                        )
                    anthropic_message["content"] = content_blocks
                converted.append(anthropic_message)
                continue

            if message.role == "tool":
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message.tool_call_id or "tool_call",
                                "content": str(message.content),
                            }
                        ],
                    }
                )

        system = "\n\n".join(part for part in system_parts if part) or None
        return system, converted

    def _convert_tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        if not tools:
            return None

        converted = []
        for tool in tools:
            function = tool.get("function", {})
            converted.append(
                {
                    "name": function.get("name", "tool"),
                    "description": function.get("description", ""),
                    "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return converted

    def _extract_text(self, content_blocks: list[dict[str, Any]]) -> str:
        return "".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")

    def _extract_response_text(self, data: dict[str, Any]) -> str:
        """Extract text from Anthropic-compatible responses.

        Some third-party compatible endpoints do not return the exact official
        Anthropic payload shape, so we accept a few common variants.
        """
        content = data.get("content", [])
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text = self._extract_text(content)
            if text:
                return text

        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        if isinstance(data.get("text"), str):
            return data["text"]

        message = data.get("message")
        if isinstance(message, dict):
            if isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(message.get("content"), list):
                text = self._extract_text(message["content"])
                if text:
                    return text

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                if isinstance(first.get("text"), str):
                    return first["text"]
                message = first.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    return message["content"]

        return ""

    def _extract_response_tool_calls(self, data: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Extract tool calls from Anthropic-compatible responses."""
        content = data.get("content", [])
        if isinstance(content, list):
            tool_calls = self._extract_tool_calls(content)
            if tool_calls:
                return tool_calls

        message = data.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                tool_calls = self._extract_tool_calls(content)
                if tool_calls:
                    return tool_calls

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    tool_calls = message.get("tool_calls")
                    if isinstance(tool_calls, list):
                        return tool_calls

        return None

    def _extract_tool_calls(self, content_blocks: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        tool_calls = []
        for block in content_blocks:
            if block.get("type") != "tool_use":
                continue
            tool_calls.append(
                {
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name", "tool"),
                        "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                    },
                }
            )
        return tool_calls or None

    def _build_request(
        self,
        messages: list[LLMMessage],
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        system, anthropic_messages = self._convert_messages(messages)
        request: dict[str, Any] = {
            "model": self.config.model,
            "messages": anthropic_messages,
            "stream": stream,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if system:
            request["system"] = system

        anthropic_tools = self._convert_tools(tools)
        if anthropic_tools:
            request["tools"] = anthropic_tools

        request.update(self.config.extra)
        request.update(kwargs)
        return request

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        request = self._build_request(messages, stream=False, tools=tools, **kwargs)
        headers = self._get_headers()
        url = self._get_api_url()
        ssl = resolve_ssl_setting(url, _DEFAULT_API_URL)

        data = await async_post_json(
            url,
            payload=request,
            headers=headers,
            ssl=ssl,
            timeout=self.config.timeout,
            error_label="API error",
        )

        content_blocks = data.get("content", [])
        usage = data.get("usage")
        if isinstance(usage, dict):
            usage = {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            }

        text_content = self._extract_response_text(data)
        tool_calls = self._extract_response_tool_calls(data)
        if not text_content and not tool_calls:
            _LOGGER.debug("Anthropic-compatible empty response payload: %s", data)

        return LLMResponse(
            content=text_content,
            tool_calls=tool_calls,
            usage=usage,
            model=data.get("model"),
            finish_reason=data.get("stop_reason"),
            raw_response=data,
        )

    async def complete_stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str | dict[str, Any], None]:
        request = self._build_request(messages, stream=True, tools=tools, **kwargs)
        headers = self._get_headers()
        url = self._get_api_url()
        ssl = resolve_ssl_setting(url, _DEFAULT_API_URL)

        buffer = ""
        tool_call_buffer: dict[int, dict[str, Any]] = {}
        async for chunk_text in async_stream_response_text(
            url,
            payload=request,
            headers=headers,
            ssl=ssl,
            timeout=self.config.timeout,
            error_label="API error",
        ):
            buffer += chunk_text

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()

                if not line or line.startswith("event:"):
                    continue
                if not line.startswith("data: "):
                    continue

                data_str = line[6:]

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    _LOGGER.debug("Anthropic SSE parse failed: %s", data_str)
                    continue

                if data.get("type") == "content_block_start":
                    content_block = data.get("content_block", {})
                    if content_block.get("type") == "tool_use":
                        index = int(data.get("index", 0))
                        tool_id = content_block.get("id")
                        if not isinstance(tool_id, str) or not tool_id.strip():
                            tool_id = ulid.ulid_now()
                        tool_input = content_block.get("input", {})
                        if not isinstance(tool_input, dict):
                            tool_input = {"value": tool_input}
                        tool_call_buffer[index] = {
                            "id": tool_id,
                            "type": "function",
                            "function": {
                                "name": str(content_block.get("name", "tool")),
                                "arguments": json.dumps(tool_input, ensure_ascii=False),
                            },
                        }
                    continue

                if data.get("type") == "content_block_delta":
                    index = int(data.get("index", 0))
                    delta = data.get("delta", {})
                    delta_type = delta.get("type")
                    if delta_type == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            yield text
                        continue

                    if delta_type == "input_json_delta":
                        partial_json = delta.get("partial_json", "")
                        if not partial_json:
                            continue
                        if index not in tool_call_buffer:
                            tool_call_buffer[index] = {
                                "id": ulid.ulid_now(),
                                "type": "function",
                                "function": {"name": "tool", "arguments": ""},
                            }
                        tool_call_buffer[index]["function"]["arguments"] += partial_json

        if tool_call_buffer:
            tool_calls = finalize_buffered_tool_calls(tool_call_buffer)
            if tool_calls:
                yield {"tool_calls": tool_calls}

    async def health_check(self) -> bool:
        try:
            url = self._get_api_url()
            ssl = resolve_ssl_setting(url, _DEFAULT_API_URL)

            return await check_provider_health(url, ssl=ssl, timeout=10)
        except Exception as err:
            _LOGGER.debug("Anthropic health check failed: %s", err)
            return False
