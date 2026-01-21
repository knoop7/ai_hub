"""Pytest configuration and fixtures for AI Hub tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_api_key():
    """Provide a mock API key for testing."""
    return "test_api_key_12345"


@pytest.fixture
def mock_siliconflow_key():
    """Provide a mock SiliconFlow API key for testing."""
    return "test_siliconflow_key_12345"
