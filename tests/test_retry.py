"""Tests for the retry utility module."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.ai_hub.utils.retry import (
    RetryConfig,
    RetryContext,
    RetryError,
    async_retry,
    async_retry_with_backoff,
    calculate_delay,
    is_retryable_exception,
)


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert config.jitter_factor == 0.1

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=60.0,
            jitter=False,
        )

        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 60.0
        assert config.jitter is False


class TestCalculateDelay:
    """Tests for calculate_delay function."""

    def test_first_attempt_delay(self):
        """Test delay for first attempt (attempt=0)."""
        config = RetryConfig(base_delay=1.0, jitter=False)
        delay = calculate_delay(0, config)
        assert delay == 1.0

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)

        assert calculate_delay(0, config) == 1.0  # 1 * 2^0 = 1
        assert calculate_delay(1, config) == 2.0  # 1 * 2^1 = 2
        assert calculate_delay(2, config) == 4.0  # 1 * 2^2 = 4
        assert calculate_delay(3, config) == 8.0  # 1 * 2^3 = 8

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        config = RetryConfig(
            base_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False,
        )

        # 1 * 2^3 = 8, but capped at 5
        delay = calculate_delay(3, config)
        assert delay == 5.0

    def test_jitter_adds_variance(self):
        """Test that jitter adds variance to delay."""
        config = RetryConfig(base_delay=10.0, jitter=True, jitter_factor=0.1)

        delays = [calculate_delay(0, config) for _ in range(100)]

        # All delays should be close to 10.0 (within jitter range)
        assert all(9.0 <= d <= 11.0 for d in delays)

        # With 100 samples, we should see some variance
        assert len(set(delays)) > 1


class TestIsRetryableException:
    """Tests for is_retryable_exception function."""

    def test_retryable_exceptions(self):
        """Test that retryable exceptions are identified correctly."""
        config = RetryConfig()

        assert is_retryable_exception(aiohttp.ClientError(), config)
        assert is_retryable_exception(asyncio.TimeoutError(), config)
        assert is_retryable_exception(ConnectionError(), config)
        assert is_retryable_exception(OSError(), config)

    def test_non_retryable_exceptions(self):
        """Test that non-retryable exceptions are identified correctly."""
        config = RetryConfig()

        assert not is_retryable_exception(ValueError(), config)
        assert not is_retryable_exception(KeyError(), config)
        assert not is_retryable_exception(TypeError(), config)

    def test_retryable_status_codes(self):
        """Test retryable HTTP status codes."""
        config = RetryConfig()

        # Create mock ClientResponseError with retryable status
        for status in (408, 429, 500, 502, 503, 504):
            exc = aiohttp.ClientResponseError(
                MagicMock(),
                (),
                status=status,
            )
            assert is_retryable_exception(exc, config)

    def test_non_retryable_status_codes(self):
        """Test non-retryable HTTP status codes."""
        config = RetryConfig()

        for status in (400, 401, 403, 404, 422):
            exc = aiohttp.ClientResponseError(
                MagicMock(),
                (),
                status=status,
            )
            assert not is_retryable_exception(exc, config)


class TestAsyncRetry:
    """Tests for async_retry function."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Test successful execution on first attempt."""
        mock_func = AsyncMock(return_value="success")

        result = await async_retry(mock_func)

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retries(self):
        """Test successful execution after retries."""
        mock_func = AsyncMock(
            side_effect=[asyncio.TimeoutError(), asyncio.TimeoutError(), "success"]
        )
        config = RetryConfig(max_attempts=3, base_delay=0.01)

        result = await async_retry(mock_func, config=config)

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_exhausted_retries(self):
        """Test that RetryError is raised when retries are exhausted."""
        mock_func = AsyncMock(side_effect=asyncio.TimeoutError())
        config = RetryConfig(max_attempts=3, base_delay=0.01)

        with pytest.raises(RetryError) as exc_info:
            await async_retry(mock_func, config=config)

        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_exception, asyncio.TimeoutError)

    @pytest.mark.asyncio
    async def test_non_retryable_exception_raises_immediately(self):
        """Test that non-retryable exceptions are raised immediately."""
        mock_func = AsyncMock(side_effect=ValueError("test error"))
        config = RetryConfig(max_attempts=3, base_delay=0.01)

        with pytest.raises(ValueError):
            await async_retry(mock_func, config=config)

        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """Test that on_retry callback is called."""
        mock_func = AsyncMock(
            side_effect=[asyncio.TimeoutError(), "success"]
        )
        callback = MagicMock()
        config = RetryConfig(max_attempts=3, base_delay=0.01, on_retry=callback)

        await async_retry(mock_func, config=config)

        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == 1  # Attempt number
        assert isinstance(args[1], asyncio.TimeoutError)


class TestAsyncRetryDecorator:
    """Tests for async_retry_with_backoff decorator."""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Test decorator with successful function."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)

        @async_retry_with_backoff(config)
        async def my_func():
            return "success"

        result = await my_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_with_retries(self):
        """Test decorator with retries."""
        call_count = 0
        config = RetryConfig(max_attempts=3, base_delay=0.01)

        @async_retry_with_backoff(config)
        async def my_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise asyncio.TimeoutError()
            return "success"

        result = await my_func()
        assert result == "success"
        assert call_count == 2


class TestRetryContext:
    """Tests for RetryContext class."""

    @pytest.mark.asyncio
    async def test_context_success(self):
        """Test successful operation with context."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)

        async with RetryContext(config) as ctx:
            while ctx.should_retry:
                ctx.success()
                break

        assert not ctx.should_retry

    @pytest.mark.asyncio
    async def test_context_with_retries(self):
        """Test context with retries."""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        attempt_count = 0

        async with RetryContext(config) as ctx:
            while ctx.should_retry:
                attempt_count += 1
                try:
                    if attempt_count < 2:
                        raise asyncio.TimeoutError()
                    ctx.success()
                    break
                except asyncio.TimeoutError as e:
                    await ctx.handle_error(e)

        assert attempt_count == 2

    @pytest.mark.asyncio
    async def test_context_exhausted(self):
        """Test context when retries are exhausted."""
        config = RetryConfig(max_attempts=2, base_delay=0.01)

        with pytest.raises(RetryError):
            async with RetryContext(config) as ctx:
                while ctx.should_retry:
                    try:
                        raise asyncio.TimeoutError()
                    except asyncio.TimeoutError as e:
                        await ctx.handle_error(e)
