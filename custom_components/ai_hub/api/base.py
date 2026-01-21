"""Base API client classes for AI Hub integration.

This module provides the base classes and utilities for building
API clients with consistent error handling, retry logic, and logging.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp

from ..const import (
    RETRY_BASE_DELAY,
    RETRY_EXPONENTIAL_BASE,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_DELAY,
    TIMEOUT_DEFAULT,
)
from ..diagnostics import get_diagnostics_collector
from ..utils.retry import RetryConfig, RetryError, async_retry

_LOGGER = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        """Initialize API error."""
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class AuthenticationError(APIError):
    """Raised when API authentication fails."""

    pass


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize rate limit error."""
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class TimeoutError(APIError):
    """Raised when API request times out."""

    pass


class ValidationError(APIError):
    """Raised when request validation fails."""

    pass


@dataclass
class APIResponse:
    """Represents an API response.

    Attributes:
        success: Whether the request was successful
        data: Response data (parsed JSON or raw text)
        status_code: HTTP status code
        headers: Response headers
        latency_ms: Request latency in milliseconds
        raw_response: Raw response object (if available)
    """

    success: bool
    data: Any = None
    status_code: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    latency_ms: float | None = None
    raw_response: Any = None

    @property
    def is_error(self) -> bool:
        """Check if response indicates an error."""
        return not self.success

    def get_error_message(self) -> str | None:
        """Extract error message from response data."""
        if self.success:
            return None

        if isinstance(self.data, dict):
            # Common error message fields
            for key in ("error", "message", "error_message", "msg"):
                if key in self.data:
                    error_val = self.data[key]
                    if isinstance(error_val, dict):
                        return error_val.get("message", str(error_val))
                    return str(error_val)

        return str(self.data) if self.data else None


class APIClient(ABC):
    """Abstract base class for API clients.

    This class provides common functionality for all API clients:
    - Automatic retry with exponential backoff
    - Error handling and logging
    - Performance metrics collection
    - Session management

    Subclasses should implement:
    - _get_base_url(): Return the base URL for the API
    - _get_default_headers(): Return default headers for requests
    """

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession | None = None,
        timeout: float = TIMEOUT_DEFAULT,
        retry_config: RetryConfig | None = None,
    ) -> None:
        """Initialize the API client.

        Args:
            api_key: API key for authentication
            session: Optional aiohttp session (will be created if not provided)
            timeout: Request timeout in seconds
            retry_config: Retry configuration
        """
        self._api_key = api_key
        self._session = session
        self._own_session = session is None
        self._timeout = timeout
        self._retry_config = retry_config or RetryConfig(
            max_attempts=RETRY_MAX_ATTEMPTS,
            base_delay=RETRY_BASE_DELAY,
            max_delay=RETRY_MAX_DELAY,
            exponential_base=RETRY_EXPONENTIAL_BASE,
        )
        self._diagnostics = get_diagnostics_collector()

    @property
    def api_name(self) -> str:
        """Return the name of this API for logging/diagnostics."""
        return self.__class__.__name__

    @abstractmethod
    def _get_base_url(self) -> str:
        """Return the base URL for the API."""
        pass

    def _get_default_headers(self) -> dict[str, str]:
        """Return default headers for requests."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an active session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "APIClient":
        """Enter async context."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context."""
        await self.close()

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json_data: dict[str, Any] | None = None,
        form_data: aiohttp.FormData | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        retry: bool = True,
    ) -> APIResponse:
        """Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (will be appended to base URL)
            json_data: JSON body data
            form_data: Form data for multipart requests
            headers: Additional headers
            timeout: Request timeout (overrides default)
            retry: Whether to retry on transient failures

        Returns:
            APIResponse object

        Raises:
            APIError: On API errors
            AuthenticationError: On authentication failures
            RateLimitError: On rate limit exceeded
            TimeoutError: On request timeout
        """
        url = f"{self._get_base_url()}{endpoint}"
        request_headers = self._get_default_headers()
        if headers:
            request_headers.update(headers)

        request_timeout = aiohttp.ClientTimeout(total=timeout or self._timeout)

        async def do_request() -> APIResponse:
            session = await self._ensure_session()
            start_time = datetime.now()

            try:
                kwargs: dict[str, Any] = {
                    "headers": request_headers,
                    "timeout": request_timeout,
                }

                if json_data is not None:
                    kwargs["json"] = json_data
                elif form_data is not None:
                    kwargs["data"] = form_data
                    # Remove Content-Type for multipart, let aiohttp set it
                    if "Content-Type" in request_headers:
                        del kwargs["headers"]["Content-Type"]

                async with session.request(method, url, **kwargs) as response:
                    latency = (datetime.now() - start_time).total_seconds() * 1000

                    # Parse response
                    content_type = response.headers.get("Content-Type", "")
                    if "application/json" in content_type:
                        data = await response.json()
                    else:
                        data = await response.text()

                    # Record diagnostics
                    self._diagnostics.record_api_call(
                        self.api_name,
                        success=response.status < 400,
                        latency_ms=latency,
                        status_code=response.status,
                    )

                    # Handle error responses
                    if response.status >= 400:
                        await self._handle_error_response(response, data)

                    return APIResponse(
                        success=True,
                        data=data,
                        status_code=response.status,
                        headers=dict(response.headers),
                        latency_ms=latency,
                    )

            except aiohttp.ClientError as e:
                latency = (datetime.now() - start_time).total_seconds() * 1000
                self._diagnostics.record_api_call(
                    self.api_name,
                    success=False,
                    latency_ms=latency,
                    error=str(e),
                )
                raise

            except asyncio.TimeoutError as e:
                latency = (datetime.now() - start_time).total_seconds() * 1000
                self._diagnostics.record_api_call(
                    self.api_name,
                    success=False,
                    latency_ms=latency,
                    error="timeout",
                )
                raise TimeoutError(f"Request timed out after {self._timeout}s") from e

        if retry:
            try:
                return await async_retry(do_request, config=self._retry_config)
            except RetryError as e:
                if e.last_exception:
                    raise e.last_exception
                raise APIError(str(e))
        else:
            return await do_request()

    async def _handle_error_response(
        self,
        response: aiohttp.ClientResponse,
        data: Any,
    ) -> None:
        """Handle error responses and raise appropriate exceptions.

        Args:
            response: aiohttp response object
            data: Parsed response data

        Raises:
            AuthenticationError: On 401/403 status
            RateLimitError: On 429 status
            APIError: On other error statuses
        """
        status = response.status
        error_msg = self._extract_error_message(data) or f"HTTP {status} error"

        if status in (401, 403):
            self._diagnostics.record_error(
                self.api_name,
                f"Authentication error: {error_msg}",
            )
            raise AuthenticationError(
                error_msg,
                status_code=status,
                response_body=str(data),
            )

        if status == 429:
            retry_after = response.headers.get("Retry-After")
            retry_after_seconds = float(retry_after) if retry_after else None
            self._diagnostics.record_error(
                self.api_name,
                f"Rate limit exceeded: {error_msg}",
            )
            raise RateLimitError(
                error_msg,
                status_code=status,
                response_body=str(data),
                retry_after=retry_after_seconds,
            )

        self._diagnostics.record_error(
            self.api_name,
            f"API error ({status}): {error_msg}",
        )
        raise APIError(
            error_msg,
            status_code=status,
            response_body=str(data),
        )

    def _extract_error_message(self, data: Any) -> str | None:
        """Extract error message from response data."""
        if isinstance(data, dict):
            # Common error message fields
            for key in ("error", "message", "error_message", "msg"):
                if key in data:
                    error_val = data[key]
                    if isinstance(error_val, dict):
                        return error_val.get("message", str(error_val))
                    return str(error_val)

        if isinstance(data, str):
            return data

        return None

    async def get(
        self,
        endpoint: str,
        **kwargs: Any,
    ) -> APIResponse:
        """Make a GET request."""
        return await self._request("GET", endpoint, **kwargs)

    async def post(
        self,
        endpoint: str,
        **kwargs: Any,
    ) -> APIResponse:
        """Make a POST request."""
        return await self._request("POST", endpoint, **kwargs)

    async def health_check(self) -> bool:
        """Check if the API is reachable.

        Returns:
            True if the API is reachable, False otherwise
        """
        try:
            session = await self._ensure_session()
            async with session.get(
                self._get_base_url(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                return response.status < 500
        except Exception as e:
            _LOGGER.debug("Health check failed for %s: %s", self.api_name, e)
            return False
