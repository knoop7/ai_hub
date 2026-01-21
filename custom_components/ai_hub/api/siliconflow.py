"""SiliconFlow API client for AI Hub integration.

This module provides a client for interacting with SiliconFlow's API,
primarily for speech-to-text (STT/ASR) functionality.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

from ..const import (
    AI_HUB_STT_AUDIO_FORMATS,
    RECOMMENDED_STT_MODEL,
    SILICONFLOW_API_BASE,
    STT_MAX_FILE_SIZE_MB,
    TIMEOUT_STT_API,
)
from .base import APIClient, APIResponse, ValidationError

_LOGGER = logging.getLogger(__name__)


class SiliconFlowClient(APIClient):
    """Client for SiliconFlow API.

    Provides methods for:
    - Speech-to-text transcription

    Example:
        async with SiliconFlowClient(api_key) as client:
            result = await client.transcribe_audio(
                audio_file="/path/to/audio.wav",
                model="FunAudioLLM/SenseVoiceSmall"
            )
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the SiliconFlow client.

        Args:
            api_key: SiliconFlow API key
            base_url: Optional custom base URL
            **kwargs: Additional arguments for APIClient
        """
        super().__init__(api_key, timeout=TIMEOUT_STT_API, **kwargs)
        self._base_url = base_url or SILICONFLOW_API_BASE

    @property
    def api_name(self) -> str:
        """Return the name of this API."""
        return "siliconflow"

    def _get_base_url(self) -> str:
        """Return the base URL for the API."""
        return self._base_url

    def _get_default_headers(self) -> dict[str, str]:
        """Return default headers for requests."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            # Don't set Content-Type for multipart form data
        }

    async def transcribe_audio(
        self,
        audio_file: str | bytes,
        model: str = RECOMMENDED_STT_MODEL,
        filename: str | None = None,
        validate: bool = True,
    ) -> APIResponse:
        """Transcribe audio to text.

        Args:
            audio_file: Path to audio file or raw audio bytes
            model: STT model to use (default: SenseVoiceSmall)
            filename: Optional filename for raw bytes
            validate: Whether to validate the file before upload

        Returns:
            APIResponse containing transcription text

        Raises:
            ValidationError: If file validation fails
        """
        # Handle file path
        if isinstance(audio_file, str):
            if validate:
                self._validate_audio_file(audio_file)

            with open(audio_file, "rb") as f:
                audio_data = f.read()
            filename = filename or os.path.basename(audio_file)
        else:
            audio_data = audio_file
            filename = filename or "audio.wav"

        # Determine content type from filename
        file_ext = os.path.splitext(filename)[1].lower().lstrip(".")
        content_type = f"audio/{file_ext}" if file_ext else "audio/wav"

        # Build form data
        form_data = aiohttp.FormData()
        form_data.add_field(
            "file",
            audio_data,
            filename=filename,
            content_type=content_type,
        )
        form_data.add_field("model", model)

        response = await self.post(
            "/audio/transcriptions",
            form_data=form_data,
            timeout=TIMEOUT_STT_API,
        )

        # Extract text from response
        if response.success and isinstance(response.data, dict):
            text = response.data.get("text", "")
            response.data["text"] = text

        return response

    def _validate_audio_file(self, file_path: str) -> None:
        """Validate audio file before upload.

        Args:
            file_path: Path to the audio file

        Raises:
            ValidationError: If validation fails
        """
        if not os.path.exists(file_path):
            raise ValidationError(f"Audio file not found: {file_path}")

        if os.path.isdir(file_path):
            raise ValidationError(f"Path is a directory, not a file: {file_path}")

        # Check file size
        file_size = os.path.getsize(file_path)
        max_size = STT_MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_size:
            raise ValidationError(
                f"Audio file too large: {file_size / (1024*1024):.1f}MB "
                f"(max: {STT_MAX_FILE_SIZE_MB}MB)"
            )

        # Check file extension
        file_ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        if file_ext not in AI_HUB_STT_AUDIO_FORMATS:
            raise ValidationError(
                f"Unsupported audio format: {file_ext}. "
                f"Supported formats: {', '.join(AI_HUB_STT_AUDIO_FORMATS)}"
            )

    async def health_check(self) -> bool:
        """Check if SiliconFlow API is reachable."""
        try:
            session = await self._ensure_session()
            async with session.get(
                self._base_url,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                return response.status < 500
        except Exception as e:
            _LOGGER.debug("SiliconFlow health check failed: %s", e)
            return False
