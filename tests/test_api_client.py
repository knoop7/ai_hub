"""Tests for the API client module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import sys
from types import ModuleType, SimpleNamespace

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


def _install_homeassistant_stubs() -> None:
    if "homeassistant" in sys.modules:
        return

    homeassistant = ModuleType("homeassistant")
    homeassistant.__path__ = []
    core = ModuleType("homeassistant.core")
    core.HomeAssistant = object

    components = ModuleType("homeassistant.components")
    components.__path__ = []
    component_homeassistant = ModuleType("homeassistant.components.homeassistant")
    component_homeassistant.exposed_entities = SimpleNamespace(
        async_should_expose=lambda hass, platform, entity_id: True
    )

    helpers = ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    intent = ModuleType("homeassistant.helpers.intent")

    class _IntentHandler:
        pass

    class _IntentResponse:
        def __init__(self, language: str | None = None):
            self.language = language
            self.speech = None
            self.error = None

        def async_set_speech(self, message: str) -> None:
            self.speech = message

        def async_set_error(self, code, message: str) -> None:
            self.error = (code, message)

    intent.IntentHandler = _IntentHandler
    intent.IntentResponse = _IntentResponse
    intent.IntentResponseErrorCode = SimpleNamespace(UNKNOWN="unknown")
    intent.Intent = object

    area_registry = ModuleType("homeassistant.helpers.area_registry")
    area_registry.async_get = lambda hass: None
    device_registry = ModuleType("homeassistant.helpers.device_registry")
    device_registry.async_get = lambda hass: None
    entity_registry = ModuleType("homeassistant.helpers.entity_registry")
    entity_registry.async_get = lambda hass: None

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.homeassistant"] = component_homeassistant
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.intent"] = intent
    sys.modules["homeassistant.helpers.area_registry"] = area_registry
    sys.modules["homeassistant.helpers.device_registry"] = device_registry
    sys.modules["homeassistant.helpers.entity_registry"] = entity_registry


class _FakeStates:
    def __init__(self, entity_ids):
        self._entity_ids = entity_ids

    def async_entity_ids(self, domain=None):
        if domain is None:
            return list(self._entity_ids)
        return [entity_id for entity_id in self._entity_ids if entity_id.startswith(f"{domain}.")]

    def get(self, entity_id):
        return None


class _FakeHass:
    def __init__(self, entity_ids):
        self.states = _FakeStates(entity_ids)
        self.services = SimpleNamespace(async_call=None)


def test_intent_config_cache_reads_merged_structure():
    _install_homeassistant_stubs()
    from custom_components.ai_hub.intents.config_cache import ConfigCache

    cache = ConfigCache()
    cache.get_config = lambda force_reload=False: {
        "local_intents": {
            "GlobalDeviceControl": {
                "global_keywords": ["所有", "全屋"],
            }
        },
        "expansion_rules": {"turn": "打开|关闭"},
    }

    assert cache.get_global_keywords() == ["所有", "全屋"]
    assert "打开" in cache.get_local_features()


def test_intent_config_cache_keeps_legacy_structure_support():
    _install_homeassistant_stubs()
    from custom_components.ai_hub.intents.config_cache import ConfigCache

    cache = ConfigCache()
    cache.get_config = lambda force_reload=False: {
        "intents": {
            "ai_hub": {
                "local_intents": {
                    "GlobalDeviceControl": {
                        "global_keywords": ["全部"],
                    }
                },
                "defaults": {
                    "error_messages": {
                        "llm_config_error": "配置错误",
                    }
                },
            }
        }
    }

    assert cache.get_global_keywords() == ["全部"]
    assert cache.get_error_message("llm_config_error") == "配置错误"


def test_extract_media_query_and_fallback_target_strategy():
    _install_homeassistant_stubs()
    from custom_components.ai_hub.intents.handlers import LocalIntentHandler

    handler = LocalIntentHandler(_FakeHass(["media_player.only_one"]))
    handler._config = {
        "lists": {
            "area_names": {"values": ["客厅"]},
            "media_player_names": {"values": ["电视"]},
            "media_names": {"values": ["电视"]},
        }
    }
    handler._local_config = {
        "GlobalDeviceControl": {
            "global_keywords": ["所有"],
            "media_search": {
                "action_keywords": ["播放", "放"],
                "default_content_type": "music",
                "fallback_target_strategy": "single_only",
                "media_type_keywords": {
                    "movie": ["电影"],
                    "track": ["歌曲", "歌"],
                },
            },
        }
    }

    query, content_type = handler._extract_media_query(
        "在客厅电视播放电影星际穿越",
        handler.local_config["GlobalDeviceControl"],
        handler.local_config["GlobalDeviceControl"]["media_search"],
    )

    assert query.endswith("星际穿越")
    assert content_type == "movie"
    assert handler._select_media_fallback_targets({"fallback_target_strategy": "single_only"}, []) == [
        "media_player.only_one"
    ]


def test_local_intent_handler_matches_area_scoped_all_lights_commands():
    _install_homeassistant_stubs()
    from custom_components.ai_hub.intents.handlers import LocalIntentHandler

    handler = LocalIntentHandler(_FakeHass([]))
    handler._config = {
        "lists": {
            "area_names": {"values": ["客厅"]},
            "light_names": {"values": ["灯", "灯光"]},
        }
    }
    handler._local_config = {
        "GlobalDeviceControl": {
            "global_keywords": ["所有", "全部", "全屋"],
            "device_type_keywords": "{{lists}}",
            "control_domains": ["light"],
            "on_keywords": ["打开", "开启", "开"],
            "off_keywords": ["关闭", "关掉", "关"],
            "param_keywords": [],
            "brightness_keywords": [],
            "volume_keywords": [],
            "color_keywords": [],
            "temperature_keywords": [],
        }
    }

    assert handler.should_handle("打开客厅所有的灯") is True
    assert handler.should_handle("关闭客厅所有的灯") is True
    assert handler.should_handle("打开") is False
    assert handler.should_handle("关闭") is False
def test_error_message_extraction():
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
