"""API client module for AI Hub integration.

This module provides a unified API client layer for all external API calls,
including ZhipuAI, SiliconFlow, Edge TTS, and Bemfa.

Features:
- Unified error handling
- Automatic retry with exponential backoff
- Request/response logging
- Performance metrics collection
- Rate limiting support
"""

from __future__ import annotations

from .base import (
    APIClient,
    APIError,
    APIResponse,
    AuthenticationError,
    RateLimitError,
    TimeoutError,
)
from .siliconflow import SiliconFlowClient
from .zhipuai import ZhipuAIClient

__all__ = [
    # Base classes
    "APIClient",
    "APIError",
    "APIResponse",
    "AuthenticationError",
    "RateLimitError",
    "TimeoutError",
    # Specific clients
    "ZhipuAIClient",
    "SiliconFlowClient",
]
