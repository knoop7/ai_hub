"""SiliconFlow LLM provider for AI Hub integration.

This module provides the SiliconFlow implementation of the LLM provider interface.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import aiohttp

from ..const import (
    AI_HUB_CHAT_MODELS,
    AI_HUB_CHAT_URL,
    VISION_MODELS,
)
from . import LLMMessage, LLMProvider, LLMResponse, register_provider

_LOGGER = logging.getLogger(__name__)


class SiliconFlowProvider(LLMProvider):
    """SiliconFlow LLM provider implementation.

    Supports:
    - Chat completions (streaming and non-streaming)
    - Tool/function calling
    - Vision models for image understanding

    Example:
        config = LLMConfig(
            api_key="your-api-key",
            model="Qwen/Qwen2.5-7B-Instruct",
        )
        provider = SiliconFlowProvider(config)

        response = await provider.complete([
            LLMMessage(role="user", content="Hello!")
        ])
    """

    # Class-level attributes for registration
    _name = "siliconflow"

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "siliconflow"

    @property
    def supported_models(self) -> list[str]:
        """Return list of supported models."""
        return AI_HUB_CHAT_MODELS

    def supports_vision(self) -> bool:
        """Check if the current model supports vision."""
        return self.config.model in VISION_MODELS

    def supports_tools(self) -> bool:
        """Check if the provider supports tools."""
        return True

    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def _get_api_url(self) -> str:
        """Get the API URL."""
        return self.config.base_url or AI_HUB_CHAT_URL

    def _build_request(
        self,
        messages: list[LLMMessage],
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Build the API request body.

        Args:
            messages: List of messages
            stream: Whether to stream the response
            tools: Optional list of tools
            **kwargs: Additional parameters

        Returns:
            Request body dictionary
        """
        request: dict[str, Any] = {
            "model": self.config.model,
            "messages": [msg.to_dict() for msg in messages],
            "stream": stream,
        }

        # Add optional parameters
        if self.config.temperature != 0.3:
            request["temperature"] = self.config.temperature

        if self.config.max_tokens != 250:
            request["max_tokens"] = self.config.max_tokens

        if tools:
            request["tools"] = tools

        # Add any extra parameters from config
        request.update(self.config.extra)

        # Add any additional kwargs
        request.update(kwargs)

        return request

    async def complete(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools for function calling
            **kwargs: Additional parameters

        Returns:
            LLMResponse containing the generated content
        """
        request = self._build_request(messages, stream=False, tools=tools, **kwargs)
        headers = self._get_headers()
        url = self._get_api_url()

        timeout = aiohttp.ClientTimeout(total=self.config.timeout)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=request, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    _LOGGER.error("SiliconFlow API error: %s", error_text)
                    raise Exception(f"API error: {error_text}")

                data = await response.json()

        # Parse response
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        return LLMResponse(
            content=message.get("content", ""),
            tool_calls=message.get("tool_calls"),
            usage=data.get("usage"),
            model=data.get("model"),
            finish_reason=choice.get("finish_reason"),
            raw_response=data,
        )

    async def complete_stream(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming completion.

        Args:
            messages: List of conversation messages
            tools: Optional list of tools
            **kwargs: Additional parameters

        Yields:
            Generated content chunks
        """
        request = self._build_request(messages, stream=True, tools=tools, **kwargs)
        headers = self._get_headers()
        url = self._get_api_url()

        timeout = aiohttp.ClientTimeout(total=self.config.timeout)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=request, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    _LOGGER.error("SiliconFlow streaming error: %s", error_text)
                    raise Exception(f"API error: {error_text}")

                buffer = ""
                async for chunk in response.content:
                    if not chunk:
                        continue

                    chunk_text = chunk.decode("utf-8", errors="ignore")
                    buffer += chunk_text

                    # Process complete lines
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        # Skip empty lines and end markers
                        if not line or line == "data: [DONE]":
                            continue

                        # Process SSE data lines
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if not data_str.strip():
                                continue

                            try:
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                _LOGGER.debug("SSE parse failed: %s", data_str)
                                continue

    async def health_check(self) -> bool:
        """Check if the SiliconFlow API is reachable."""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://api.siliconflow.cn") as response:
                    return response.status < 500
        except Exception as e:
            _LOGGER.debug("SiliconFlow health check failed: %s", e)
            return False


# Register the provider
register_provider("siliconflow", SiliconFlowProvider)
