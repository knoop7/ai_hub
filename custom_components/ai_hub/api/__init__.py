"""API client module for AI Hub integration.

This module provides a unified API client layer for all external API calls,
including SiliconFlow, Edge TTS, and Bemfa.

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

# Backwards compatibility alias
ZhipuAIClient = SiliconFlowClient

__all__ = [
    # Base classes
    "APIClient",
    "APIError",
    "APIResponse",
    "AuthenticationError",
    "RateLimitError",
    "TimeoutError",
    # Specific clients
    "SiliconFlowClient",
    "ZhipuAIClient",  # Backwards compatibility
]
