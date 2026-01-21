"""Tests for the API client module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.ai_hub.api.base import (
    APIClient,
    APIError,
    APIResponse,
    AuthenticationError,
    RateLimitError,
    TimeoutError,
)


class TestAPIResponse:
    """Tests for APIResponse dataclass."""

    def test_success_response(self):
        """Test successful response."""
        response = APIResponse(
            success=True,
            data={"result": "ok"},
            status_code=200,
        )

        assert response.success is True
        assert response.is_error is False
        assert response.data == {"result": "ok"}
        assert response.get_error_message() is None

    def test_error_response(self):
        """Test error response."""
        response = APIResponse(
            success=False,
            data={"error": "Something went wrong"},
            status_code=400,
        )

        assert response.success is False
        assert response.is_error is True
        assert response.get_error_message() == "Something went wrong"

    def test_error_message_extraction(self):
        """Test error message extraction from various formats."""
        # Format 1: {"error": "message"}
        response1 = APIResponse(success=False, data={"error": "Error 1"})
        assert response1.get_error_message() == "Error 1"

        # Format 2: {"message": "message"}
        response2 = APIResponse(success=False, data={"message": "Error 2"})
        assert response2.get_error_message() == "Error 2"

        # Format 3: {"error": {"message": "nested"}}
        response3 = APIResponse(
            success=False,
            data={"error": {"message": "Nested error"}},
        )
        assert response3.get_error_message() == "Nested error"

        # Format 4: string data
        response4 = APIResponse(success=False, data="Plain error")
        assert response4.get_error_message() == "Plain error"


class TestAPIError:
    """Tests for API exception classes."""

    def test_api_error(self):
        """Test APIError exception."""
        error = APIError("Test error", status_code=500, response_body="body")

        assert str(error) == "Test error"
        assert error.status_code == 500
        assert error.response_body == "body"

    def test_authentication_error(self):
        """Test AuthenticationError exception."""
        error = AuthenticationError("Invalid API key", status_code=401)

        assert isinstance(error, APIError)
        assert error.status_code == 401

    def test_rate_limit_error(self):
        """Test RateLimitError exception."""
        error = RateLimitError(
            "Rate limit exceeded",
            status_code=429,
            retry_after=60.0,
        )

        assert isinstance(error, APIError)
        assert error.status_code == 429
        assert error.retry_after == 60.0

    def test_timeout_error(self):
        """Test TimeoutError exception."""
        error = TimeoutError("Request timed out")

        assert isinstance(error, APIError)
        assert str(error) == "Request timed out"


class ConcreteAPIClient(APIClient):
    """Concrete implementation of APIClient for testing."""

    def _get_base_url(self) -> str:
        return "https://api.example.com"


class TestAPIClient:
    """Tests for APIClient base class."""

    def test_init(self, mock_api_key):
        """Test client initialization."""
        client = ConcreteAPIClient(mock_api_key)

        assert client._api_key == mock_api_key
        assert client._session is None
        assert client._own_session is True

    def test_default_headers(self, mock_api_key):
        """Test default headers."""
        client = ConcreteAPIClient(mock_api_key)
        headers = client._get_default_headers()

        assert headers["Authorization"] == f"Bearer {mock_api_key}"
        assert headers["Content-Type"] == "application/json"

    def test_api_name(self, mock_api_key):
        """Test API name property."""
        client = ConcreteAPIClient(mock_api_key)
        assert client.api_name == "ConcreteAPIClient"

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_api_key):
        """Test async context manager."""
        async with ConcreteAPIClient(mock_api_key) as client:
            assert client._session is not None

        assert client._session is None or client._session.closed

    @pytest.mark.asyncio
    async def test_ensure_session(self, mock_api_key):
        """Test session creation."""
        client = ConcreteAPIClient(mock_api_key)

        session = await client._ensure_session()
        assert session is not None
        assert isinstance(session, aiohttp.ClientSession)

        await client.close()

    def test_extract_error_message(self, mock_api_key):
        """Test error message extraction."""
        client = ConcreteAPIClient(mock_api_key)

        # Dict with error key
        assert client._extract_error_message({"error": "test"}) == "test"

        # Dict with message key
        assert client._extract_error_message({"message": "test2"}) == "test2"

        # Nested error
        assert client._extract_error_message(
            {"error": {"message": "nested"}}
        ) == "nested"

        # String
        assert client._extract_error_message("string error") == "string error"

        # None/empty
        assert client._extract_error_message({}) is None
        assert client._extract_error_message(None) is None
