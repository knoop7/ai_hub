"""Ollama-compatible LLM provider for AI Hub integration."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from ..http import async_post_json, async_stream_response_text
from . import LLMMessage, LLMProvider, LLMResponse
from .common_compatible import check_provider_health, finalize_buffered_tool_calls

_LOGGER = logging.getLogger(__name__)


def _normalize_ollama_api_url(url: str | None) -> str:
    """Normalize Ollama URLs to the `/api/chat` endpoint."""
    default_url = "http://localhost:11434/api/chat"
    if not url:
        return default_url

    normalized = url.rstrip("/")
    parsed = urlparse(normalized)
    path = parsed.path.rstrip("/")

    if path.endswith("/api/chat"):
        return normalized

    if not path:
        return f"{normalized}/api/chat"

    return f"{normalized}/api/chat"


def _coerce_arguments(arguments: Any) -> str:
    """Normalize tool-call arguments to a JSON string."""
    if isinstance(arguments, str):
        return arguments
    if isinstance(arguments, dict):
        return json.dumps(arguments, ensure_ascii=False)
    return json.dumps({"value": arguments}, ensure_ascii=False)


def _parse_tool_calls(tool_calls: Any) -> list[dict[str, Any]] | None:
    """Convert Ollama tool calls to the shared normalized structure."""
    if not isinstance(tool_calls, list):
        return None

    normalized: list[dict[str, Any]] = []
    for item in tool_calls:
        if not isinstance(item, dict):
            continue
        function = item.get("function", {})
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if not name:
            continue
        normalized.append(
            {
                "id": item.get("id") or f"stream_{uuid4().hex}",
                "type": "function",
                "function": {
                    "name": str(name),
                    "arguments": _coerce_arguments(function.get("arguments", {})),
                },
            }
        )

    return normalized or None


class OllamaCompatibleProvider(LLMProvider):
    """Ollama provider using the native `/api/chat` protocol."""

    _name = "ollama_compatible"

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "ollama_compatible"

    @property
    def supported_models(self) -> list[str]:
        """Return list of supported models."""
        return []

    def supports_vision(self) -> bool:
        """Check if vision is supported."""
        model = self.config.model.lower()
        return any(keyword in model for keyword in ("vision", "llava", "moondream"))

    def supports_tools(self) -> bool:
        """Check if tools are supported."""
        return True

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _get_api_url(self) -> str:
        """Get the Ollama chat API URL."""
        return _normalize_ollama_api_url(self.config.base_url)

    def _build_request(
        self,
        messages: list[LLMMessage],
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build an Ollama `/api/chat` request."""
        request: dict[str, Any] = {
            "model": self.config.model,
            "messages": [msg.to_dict() for msg in messages],
            "stream": stream,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }

        if tools:
            request["tools"] = tools

        if self.config.enable_thinking:
            request["think"] = True

        extra = dict(self.config.extra)
        extra_options = extra.pop("options", None)
        if isinstance(extra_options, dict):
            request["options"].update(extra_options)
        request.update(extra)
        request.update(kwargs)
        return request

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a non-streaming Ollama completion."""
        request = self._build_request(messages, stream=False, tools=tools, **kwargs)
        headers = self._get_headers()
        url = self._get_api_url()
        ssl = False if url.startswith("http://") else None

        data = await async_post_json(
            url,
            payload=request,
            headers=headers,
            ssl=ssl,
            timeout=self.config.timeout,
            error_label="API error",
        )

        message = data.get("message", {})
        if not isinstance(message, dict):
            message = {}

        return LLMResponse(
            content=str(message.get("content", "") or data.get("response", "") or ""),
            tool_calls=_parse_tool_calls(message.get("tool_calls")),
            model=data.get("model"),
            finish_reason=data.get("done_reason"),
            raw_response=data,
        )

    async def complete_stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str | dict[str, Any], None]:
        """Generate a streaming completion from Ollama's `/api/chat` endpoint."""
        request = self._build_request(messages, stream=True, tools=tools, **kwargs)
        headers = self._get_headers()
        url = self._get_api_url()
        ssl = False if url.startswith("http://") else None

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
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                message = data.get("message")
                if not isinstance(message, dict):
                    response_text = data.get("response")
                    if isinstance(response_text, str) and response_text:
                        yield response_text
                    continue

                content = message.get("content")
                if isinstance(content, str) and content:
                    yield content

                parsed_tool_calls = _parse_tool_calls(message.get("tool_calls"))
                if parsed_tool_calls:
                    for index, tool_call in enumerate(parsed_tool_calls):
                        tool_call_buffer[index] = tool_call

        if tool_call_buffer:
            tool_calls = finalize_buffered_tool_calls(tool_call_buffer)
            if tool_calls:
                yield {"tool_calls": tool_calls}

    async def health_check(self) -> bool:
        """Check if the Ollama API is reachable."""
        try:
            url = self._get_api_url()
            ssl = False if url.startswith("http://") else None
            return await check_provider_health(url, ssl=ssl, timeout=10)
        except Exception as err:
            _LOGGER.debug("Ollama health check failed: %s", err)
            return False
