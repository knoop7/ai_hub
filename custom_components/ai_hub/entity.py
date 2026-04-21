"""Base entity for AI Hub integration."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any

import aiohttp
from homeassistant.components import conversation
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_flow, llm
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.util import ulid
from voluptuous_openapi import convert

from .providers import LLMMessage, create_provider
from .consts import (
    AI_HUB_CHAT_URL,
    CONF_CHAT_MODEL,
    CONF_CHAT_URL,
    CONF_LLM_PROVIDER,
    CONF_CUSTOM_API_KEY,
    CONF_ENABLE_THINKING,
    CONF_MAX_HISTORY_MESSAGES,
    CONF_MAX_TOKENS,
    CONF_TEMPERATURE,
    DOMAIN,
    ERROR_GETTING_RESPONSE,
    RECOMMENDED_IMAGE_ANALYSIS_MODEL,
    RECOMMENDED_ENABLE_THINKING,
    RECOMMENDED_MAX_HISTORY_MESSAGES,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    TIMEOUT_CHAT_API,
)
from .http import resolve_provider_name, resolve_ssl_setting
from .llm_attachment_processor import AttachmentProcessor
from .llm_message_builder import ChatMessageBuilder
from .llm_model_utils import chat_log_has_media_attachments, select_media_model
from .markdown_filter import filter_markdown_streaming

_LOGGER = logging.getLogger(__name__)


def _ensure_string(value: Any) -> str:
    """Ensure a value is a valid string for API calls.

    Args:
        value: The value to convert to string

    Returns:
        A string representation of the value, or empty string if None/empty
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        # Convert complex types to JSON string
        return json.dumps(value, ensure_ascii=False)
    # For other types, convert to string
    return str(value)
class _AIHubEntityMixin:
    """Mixin class providing common initialization logic for AI Hub entities.

    This mixin provides shared initialization behavior for all AI Hub entity types:
    - LLM conversation entities
    - TTS entities
    - STT entities

    Attributes:
        entry: The config entry
        subentry: The subentry for this entity instance
        default_model: The default model to use
        _api_key: The API key for this entity
    """

    _attr_has_entity_name = False
    _attr_should_poll = False

    def _initialize_aihub_entity(
        self,
        entry: config_entry_flow.ConfigEntry,
        subentry: config_entry_flow.ConfigSubentry,
        default_model: str,
        *,
        warn_on_missing_api_key: bool = True,
    ) -> None:
        """Initialize common AI Hub entity attributes.

        This method should be called from the entity's __init__ method.

        Args:
            entry: The config entry
            subentry: The subentry for this entity instance
            default_model: The default model to use
        """
        self.entry = entry
        self.subentry = subentry
        self.default_model = default_model
        self._attr_unique_id = subentry.subentry_id
        self._attr_name = subentry.title

        # Get API key: use custom key if provided, otherwise use main key
        custom_key_raw = subentry.data.get(CONF_CUSTOM_API_KEY, "")
        custom_key = str(custom_key_raw).strip() if custom_key_raw else ""
        main_key = entry.runtime_data if entry.runtime_data else ""
        # Ensure API key is always a string
        if custom_key:
            self._api_key = custom_key
        elif isinstance(main_key, str) and main_key.strip():
            self._api_key = main_key
        else:
            self._api_key = ""
            if warn_on_missing_api_key:
                _LOGGER.warning("No valid API key found for entity %s", subentry.title)

    def _get_device_model(self, default_model: str) -> str:
        """Get the device model for device info.

        Can be overridden by subclasses to provide custom model validation.

        Args:
            default_model: The default model to use if no model is configured

        Returns:
            The model name to use for device info
        """
        return self.subentry.data.get(CONF_CHAT_MODEL, default_model)

    def _create_device_info(self, domain: str) -> dr.DeviceInfo:
        """Create device info for this entity.

        Args:
            domain: The domain for this integration

        Returns:
            DeviceInfo object
        """
        return dr.DeviceInfo(
            identifiers={(domain, self.subentry.subentry_id)},
            name=self.subentry.title,
            manufacturer="老王杂谈说",
            model=self._get_device_model(self.default_model),
            entry_type=dr.DeviceEntryType.SERVICE,
        )


class AIHubBaseLLMEntity(Entity, _AIHubEntityMixin):
    """Base entity for AI Hub LLM."""

    def __init__(
        self,
        entry: config_entry_flow.ConfigEntry,
        subentry: config_entry_flow.ConfigSubentry,
        default_model: str,
        *,
        warn_on_missing_api_key: bool = True,
    ) -> None:
        """Initialize the entity."""
        # Use mixin initialization
        self._initialize_aihub_entity(
            entry,
            subentry,
            default_model,
            warn_on_missing_api_key=warn_on_missing_api_key,
        )
        # Create device info using mixin method
        self._attr_device_info = self._create_device_info(DOMAIN)

    def _get_device_model(self, default_model: str) -> str:
        """Get the device model with validation for LLM entities.

        Args:
            default_model: The default model to use if no model is configured

        Returns:
            The validated model name to use for device info
        """
        device_model = self.subentry.data.get(CONF_CHAT_MODEL) or default_model
        if not isinstance(device_model, str) or not device_model.strip():
            device_model = default_model
        return device_model

    def _get_model_config(self, chat_log: conversation.ChatLog | None = None) -> dict[str, Any]:
        """Get model configuration from options."""
        options = self.subentry.data
        configured_model = options.get(CONF_CHAT_MODEL) or self.default_model
        # Ensure configured_model is a valid string
        if not isinstance(configured_model, str) or not configured_model.strip():
            configured_model = self.default_model

        # Check if we need to switch to vision model
        final_model = configured_model
        if chat_log and chat_log_has_media_attachments(chat_log):
            vision_models = ["glm-4.1v-thinking", "glm-4v-flash"]
            final_model = select_media_model(
                configured_model,
                vision_models,
                RECOMMENDED_IMAGE_ANALYSIS_MODEL,
            )
            if final_model != configured_model:
                _LOGGER.debug(
                    "Auto-switching to vision model %s for media attachments (original: %s)",
                    final_model,
                    configured_model,
                )

        # Only use parameters that the working service uses (top_p causes API error!)
        # Ensure model is always a valid string
        model_value = final_model or self.default_model
        if not isinstance(model_value, str) or not model_value.strip():
            model_value = self.default_model

        return {
            "model": model_value,
            "temperature": options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE),
            "enable_thinking": bool(
                options.get(CONF_ENABLE_THINKING, RECOMMENDED_ENABLE_THINKING)
            ),
            "max_tokens": options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS),
        }

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure: dict[str, Any] | None = None,
    ) -> None:
        """Generate an answer for the chat log."""
        options = self.subentry.data
        model_config = self._get_model_config(chat_log)

        # Build messages from chat log (attachment processing will be done during conversion)
        messages = await self._async_convert_chat_log_to_messages(chat_log)

        # Add JSON format instruction to system message if structure is requested
        if structure and messages:
            for i, message in enumerate(messages):
                if message.get("role") == "system":
                    # Add JSON format requirement to system message
                    original_content = message.get("content", "")
                    if "JSON" not in original_content:
                        message["content"] = (
                            original_content +
                            "\n\nWhen providing structured data like automation names/"
                            "descriptions, respond ONLY with valid JSON. Use the exact "
                            "JSON structure requested in the prompt. Do not include any "
                            "markdown formatting, explanations, or additional text."
                        )
                    break

        # Add tools if available
        tools = []
        if chat_log.llm_api:
            tools.extend([
                self._format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ])

        # Build minimal request parameters using only essential parameters
        # Ensure model is a valid non-empty string
        model_name = model_config.get("model", "")
        if not model_name or not isinstance(model_name, str):
            model_name = self.default_model
            _LOGGER.warning("Model name was invalid, using default: %s", model_name)

        # Validate all message contents before sending
        for i, msg in enumerate(messages):
            msg_content = msg.get("content")
            if msg_content is None:
                msg["content"] = ""
                _LOGGER.warning("Message %d had None content, replaced with empty string", i)
            elif isinstance(msg_content, list):
                # Validate each part in content list
                for j, part in enumerate(msg_content):
                    if part.get("type") == "text" and not isinstance(part.get("text"), str):
                        part["text"] = str(part.get("text", ""))
                        _LOGGER.warning("Message %d part %d had non-string text, converted", i, j)

        # Get API URL from config before the request
        api_url = options.get(CONF_CHAT_URL) or AI_HUB_CHAT_URL
        if not isinstance(api_url, str) or not api_url.strip():
            api_url = AI_HUB_CHAT_URL
            _LOGGER.warning("API URL was invalid, using default: %s", api_url)

        provider_name = resolve_provider_name(api_url, options.get(CONF_LLM_PROVIDER))

        request_params = {
            "model": model_name,
            "messages": messages,
            "stream": True,
        }

        if provider_name == "openai_compatible":
            request_params["enable_thinking"] = bool(
                model_config.get("enable_thinking", RECOMMENDED_ENABLE_THINKING)
            )

        if tools:
            request_params["tools"] = tools

        try:
            # Validate API key before making request
            if not self._api_key:
                _LOGGER.error("Cannot make API request: API key is empty or not configured")
                raise HomeAssistantError("API key is not configured")

            # Ensure API key is a string
            if not isinstance(self._api_key, str):
                self._api_key = str(self._api_key)

            _LOGGER.debug(
                "API Request: provider=%s, model=%s, messages_count=%d",
                provider_name,
                model_name,
                len(messages)
            )

            llm_messages = [
                LLMMessage(
                    role=msg["role"],
                    content=msg.get("content", ""),
                    tool_calls=msg.get("tool_calls"),
                    tool_call_id=msg.get("tool_call_id"),
                )
                for msg in messages
            ]

            provider = create_provider(
                provider_name,
                {
                    "api_key": self._api_key,
                    "model": model_name,
                    "base_url": api_url,
                    "temperature": model_config.get("temperature", RECOMMENDED_TEMPERATURE),
                    "max_tokens": model_config.get("max_tokens", RECOMMENDED_MAX_TOKENS),
                    "enable_thinking": model_config.get("enable_thinking", RECOMMENDED_ENABLE_THINKING),
                },
            )

            if provider is not None:
                _LOGGER.debug(
                    "Invoking provider=%s stream=%s tools=%d",
                    provider_name,
                    not bool(tools),
                    len(tools),
                )
                if not tools:
                    async for _ in chat_log.async_add_delta_content_stream(
                        self.entity_id,
                        self._transform_provider_stream(provider.complete_stream(llm_messages, tools=tools)),
                    ):
                        pass
                    return

                response = await provider.complete(llm_messages, tools=tools)
                tool_calls = self._convert_provider_tool_calls(response.tool_calls)
                assistant_content = conversation.AssistantContent(
                    agent_id=self.entity_id,
                    content=response.content or None,
                    tool_calls=tool_calls or None,
                    native=response.raw_response,
                )
                async for _ in chat_log.async_add_assistant_content(assistant_content):
                    pass
                return

            # Call AI Hub API with streaming via HTTP
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
            request_ssl = resolve_ssl_setting(api_url, AI_HUB_CHAT_URL)

            # Use Home Assistant's shared session for better performance
            session = async_get_clientsession(self.hass)
            async with session.post(
                api_url,
                json=request_params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_CHAT_API),
                ssl=request_ssl,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    _LOGGER.error("API request failed: %s", error_text)
                    raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE}: {error_text}")

                # Process streaming response using the new API
                [
                    content
                    async for content in chat_log.async_add_delta_content_stream(
                        self.entity_id, self._transform_stream(response)
                    )
                ]

        except aiohttp.ClientError as err:
            _LOGGER.error("Network error calling AI Hub API: %s", err)
            raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE}: Network error") from err
        except Exception as err:
            _LOGGER.error("Error calling AI Hub API: %s", err)
            raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE}: {err}") from err

    async def _transform_provider_stream(
        self,
        stream: AsyncGenerator[str, None],
    ) -> AsyncGenerator[conversation.AssistantContentDeltaDict, None]:
        """Convert provider text chunks into Home Assistant streaming deltas."""
        has_started = False
        async for chunk in stream:
            if not chunk:
                continue
            if not has_started:
                yield {"role": "assistant"}
                has_started = True

            filtered_content = filter_markdown_streaming(chunk)
            if filtered_content:
                yield {"content": filtered_content}

    def _convert_provider_tool_calls(
        self,
        tool_calls: list[dict[str, Any]] | None,
    ) -> list[llm.ToolInput]:
        """Convert provider tool calls to Home Assistant ToolInput objects."""
        if not tool_calls:
            return []

        converted: list[llm.ToolInput] = []
        for tool_call in tool_calls:
            try:
                function_data = tool_call.get("function", {})
                arguments = function_data.get("arguments", {})
                if isinstance(arguments, str):
                    arguments = json.loads(arguments) if arguments else {}
                if not isinstance(arguments, dict):
                    arguments = {"value": arguments}

                tool_id = tool_call.get("id") or ulid.ulid_now()
                converted.append(
                    llm.ToolInput(
                        id=tool_id,
                        tool_name=function_data.get("name", "tool"),
                        tool_args=arguments,
                    )
                )
            except Exception as err:
                _LOGGER.warning("Failed to convert provider tool call: %s", err)

        return converted

    async def _async_convert_chat_log_to_messages(
        self, chat_log: conversation.ChatLog
    ) -> list[dict[str, Any]]:
        """Convert chat log to AI Hub message format."""
        attachment_processor = AttachmentProcessor(self.hass, self.entity_id)
        builder = ChatMessageBuilder(
            attachment_processor,
            self.subentry.data.get(CONF_MAX_HISTORY_MESSAGES, RECOMMENDED_MAX_HISTORY_MESSAGES),
            tool_message_converter=self._convert_tool_message,
        )
        return await builder.async_convert_chat_log_to_messages(chat_log)

    def _convert_tool_message(
        self, content: conversation.Content
    ) -> list[dict[str, Any]]:
        """Convert tool result to AI Hub format.

        Returns a list: normally one ``role: tool`` message; when the tool result
        carries an ``image_base64`` field, the base64 is stripped from the tool
        content and a follow-up ``role: user`` multimodal message is appended so
        the vision model can actually see the image.
        """
        # Ensure tool_call_id is always a valid string
        # API requires a non-empty tool_call_id
        tool_call_id = content.tool_call_id
        if not tool_call_id or not isinstance(tool_call_id, str) or not tool_call_id.strip():
            # Generate a valid ID if missing - this maintains API compatibility
            tool_call_id = ulid.ulid_now()
            _LOGGER.debug("Generated tool_call_id for tool result: %s", tool_call_id)

        tool_result = content.tool_result
        image_b64: str | None = None
        image_mime = "image/jpeg"
        tool_name = ""

        # Strip image_base64 from the tool payload so we don't ship the raw
        # base64 twice (once as text, once as image_url).
        if isinstance(tool_result, dict) and isinstance(
            tool_result.get("image_base64"), str
        ):
            sanitized = {k: v for k, v in tool_result.items() if k != "image_base64"}
            image_b64 = tool_result["image_base64"]
            image_mime = str(sanitized.get("content_type") or "image/jpeg")
            tool_name = str(sanitized.get("camera_entity") or sanitized.get("tool") or "")
            sanitized["image_base64"] = (
                f"<image attached as image_url follow-up, {len(image_b64)} base64 chars>"
            )
            tool_result_payload: Any = sanitized
        else:
            tool_result_payload = tool_result

        tool_message: dict[str, Any] = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": (
                json.dumps(tool_result_payload, ensure_ascii=False, default=str)
                if tool_result_payload is not None
                else "{}"
            ),
        }

        if not image_b64:
            return [tool_message]

        follow_up: dict[str, Any] = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Image from tool result ({tool_name}). "
                        "Analyze this picture and continue the task."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image_mime};base64,{image_b64}"},
                },
            ],
        }
        return [tool_message, follow_up]

    def _format_tool(
        self, tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
    ) -> dict[str, Any]:
        """Format tool for AI Hub API."""
        return ChatMessageBuilder.format_tool(tool, custom_serializer)

    def _convert_schema(
        self, schema: dict[str, Any], custom_serializer: Callable[[Any], Any] | None
    ) -> dict[str, Any]:
        """Convert schema to AI Hub format."""
        return ChatMessageBuilder.convert_schema(schema, custom_serializer)

    async def _transform_stream(
        self,
        response: aiohttp.ClientResponse,
    ) -> AsyncGenerator[
        conversation.AssistantContentDeltaDict | conversation.ToolResultContentDeltaDict
    ]:
        """Transform AI Hub SSE stream into HA format."""
        buffer = ""
        tool_call_buffer: dict[int, dict[str, Any]] = {}
        has_started = False

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
                    except json.JSONDecodeError:
                        _LOGGER.debug("SSE data parse failed: %s", data_str)
                        continue

                    if not data.get("choices"):
                        continue

                    delta = data["choices"][0].get("delta", {})

                    # Start assistant message if not started
                    if not has_started:
                        yield {"role": "assistant"}
                        has_started = True

                    # Handle content delta
                    if "content" in delta and delta["content"]:
                        # Filter markdown from content using streaming filter to preserve spaces
                        filtered_content = filter_markdown_streaming(delta["content"])
                        yield {"content": filtered_content}

                    # Handle tool calls
                    if "tool_calls" in delta:
                        for tc_delta in delta["tool_calls"]:
                            index = tc_delta.get("index", 0)

                            # Initialize tool call buffer if needed
                            if index not in tool_call_buffer:
                                # Ensure we always have a valid id
                                tool_id = tc_delta.get("id")
                                if not tool_id or not isinstance(tool_id, str) or not tool_id.strip():
                                    tool_id = ulid.ulid_now()
                                tool_call_buffer[index] = {
                                    "id": tool_id,
                                    "type": "function",
                                    "function": {
                                        "name": "",
                                        "arguments": "",
                                    },
                                }

                            # Update tool call data - only update id if it's a valid non-empty string
                            if (
                                "id" in tc_delta
                                and tc_delta["id"]
                                and isinstance(tc_delta["id"], str)
                                and tc_delta["id"].strip()
                            ):
                                tool_call_buffer[index]["id"] = tc_delta["id"]
                            if "function" in tc_delta:
                                func = tc_delta["function"]
                                if "name" in func:
                                    tool_call_buffer[index]["function"]["name"] = func["name"]
                                if "arguments" in func:
                                    tool_call_buffer[index]["function"]["arguments"] += func["arguments"]

        # Yield final tool calls if any
        if tool_call_buffer:
            tool_calls = []
            for tc in tool_call_buffer.values():
                try:
                    # Ensure id is valid before creating ToolInput
                    tool_id = tc["id"]
                    if not tool_id or not isinstance(tool_id, str) or not tool_id.strip():
                        tool_id = ulid.ulid_now()

                    args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                    tool_calls.append(
                        llm.ToolInput(
                            id=tool_id,
                            tool_name=tc["function"]["name"],
                            tool_args=args,
                        )
                    )
                except json.JSONDecodeError as err:
                    _LOGGER.warning("Failed to parse tool call arguments: %s", err)

            if tool_calls:
                yield {"tool_calls": tool_calls}

class AIHubEntityBase(Entity, _AIHubEntityMixin):
    """Base entity for AI Hub integration.

    This class is used by TTS and STT entities which don't need the full
    LLM functionality but require the same initialization logic.
    """

    def __init__(
        self,
        entry: config_entry_flow.ConfigEntry,
        subentry: config_entry_flow.ConfigSubentry,
        default_model: str,
        *,
        warn_on_missing_api_key: bool = True,
    ) -> None:
        """Initialize the entity."""
        # Use mixin initialization
        self._initialize_aihub_entity(
            entry,
            subentry,
            default_model,
            warn_on_missing_api_key=warn_on_missing_api_key,
        )
        # Create device info using mixin method
        self._attr_device_info = self._create_device_info(DOMAIN)
