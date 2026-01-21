"""ZhipuAI API client for AI Hub integration.

This module provides a client for interacting with ZhipuAI's API,
including chat completions and image generation.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import aiohttp

from ..const import (
    TIMEOUT_CHAT_API,
    TIMEOUT_IMAGE_API,
)
from .base import APIClient, APIResponse

_LOGGER = logging.getLogger(__name__)


class ZhipuAIClient(APIClient):
    """Client for ZhipuAI API.

    Provides methods for:
    - Chat completions (streaming and non-streaming)
    - Image generation

    Example:
        async with ZhipuAIClient(api_key) as client:
            response = await client.chat_completion(
                model="glm-4-flash",
                messages=[{"role": "user", "content": "Hello!"}]
            )
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the ZhipuAI client.

        Args:
            api_key: ZhipuAI API key
            base_url: Optional custom base URL
            **kwargs: Additional arguments for APIClient
        """
        super().__init__(api_key, timeout=TIMEOUT_CHAT_API, **kwargs)
        self._base_url = base_url or "https://open.bigmodel.cn"

    @property
    def api_name(self) -> str:
        """Return the name of this API."""
        return "zhipuai"

    def _get_base_url(self) -> str:
        """Return the base URL for the API."""
        return self._base_url

    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 250,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> APIResponse | AsyncGenerator[dict[str, Any], None]:
        """Create a chat completion.

        Args:
            model: Model to use (e.g., "glm-4-flash")
            messages: List of messages in the conversation
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            tools: Optional list of tools for function calling
            stream: Whether to stream the response
            **kwargs: Additional parameters for the API

        Returns:
            APIResponse for non-streaming, AsyncGenerator for streaming
        """
        request_data: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        # Only add optional parameters if they have non-default values
        if temperature != 0.3:
            request_data["temperature"] = temperature
        if max_tokens != 250:
            request_data["max_tokens"] = max_tokens
        if tools:
            request_data["tools"] = tools

        # Add any additional parameters
        request_data.update(kwargs)

        if stream:
            return self._stream_chat_completion(request_data)
        else:
            return await self.post(
                "/api/paas/v4/chat/completions",
                json_data=request_data,
                timeout=TIMEOUT_CHAT_API,
            )

    async def _stream_chat_completion(
        self,
        request_data: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream chat completion response.

        Args:
            request_data: Request data for the API

        Yields:
            Parsed SSE data chunks
        """
        url = f"{self._get_base_url()}/api/paas/v4/chat/completions"
        headers = self._get_default_headers()
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_CHAT_API)

        session = await self._ensure_session()

        async with session.post(
            url,
            json=request_data,
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                _LOGGER.error("ZhipuAI streaming error: %s", error_text)
                raise Exception(f"Streaming request failed: {error_text}")

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
                        data_str = line[6:]  # Remove "data: " prefix
                        if not data_str.strip():
                            continue

                        try:
                            data = json.loads(data_str)
                            yield data
                        except json.JSONDecodeError:
                            _LOGGER.debug("SSE data parse failed: %s", data_str)
                            continue

    async def generate_image(
        self,
        prompt: str,
        model: str = "cogview-3-flash",
        size: str = "1024x1024",
        **kwargs: Any,
    ) -> APIResponse:
        """Generate an image using CogView.

        Args:
            prompt: Image description
            model: Model to use (default: cogview-3-flash)
            size: Image size (default: 1024x1024)
            **kwargs: Additional parameters

        Returns:
            APIResponse containing image URL(s)
        """
        request_data: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
        }
        request_data.update(kwargs)

        return await self.post(
            "/api/paas/v4/images/generations",
            json_data=request_data,
            timeout=TIMEOUT_IMAGE_API,
        )

    async def analyze_image(
        self,
        image_url: str,
        prompt: str,
        model: str = "glm-4v-flash",
        **kwargs: Any,
    ) -> APIResponse:
        """Analyze an image using vision model.

        Args:
            image_url: URL or base64 data URL of the image
            prompt: Analysis prompt
            model: Vision model to use
            **kwargs: Additional parameters

        Returns:
            APIResponse containing analysis results
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        return await self.chat_completion(
            model=model,
            messages=messages,
            **kwargs,
        )

    async def health_check(self) -> bool:
        """Check if ZhipuAI API is reachable."""
        try:
            session = await self._ensure_session()
            async with session.get(
                self._base_url,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                return response.status < 500
        except Exception as e:
            _LOGGER.debug("ZhipuAI health check failed: %s", e)
            return False
