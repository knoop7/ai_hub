"""Attachment processing helpers for LLM requests."""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

from homeassistant.components import media_source
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .http import client_timeout

_LOGGER = logging.getLogger(__name__)


class AttachmentProcessor:
    """Resolve Home Assistant attachments into provider-friendly parts."""

    def __init__(self, hass: Any, entity_id: str) -> None:
        self.hass = hass
        self.entity_id = entity_id

    async def process_attachments(self, attachments: list[Any]) -> list[dict[str, Any]]:
        """Process attachments and return successful image parts."""
        successful_images = []
        _LOGGER.debug("Processing %d attachments for user message", len(attachments))

        for i, attachment in enumerate(attachments):
            _LOGGER.debug("Processing attachment %d: %s", i, attachment)
            if not (attachment.mime_type and attachment.mime_type.startswith("image/")):
                _LOGGER.debug(
                    "Skipping non-image attachment: %s (mime: %s)",
                    attachment,
                    getattr(attachment, "mime_type", "unknown"),
                )
                continue

            image_data = await self.get_image_data_from_attachment(attachment)
            if image_data:
                successful_images.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                )
            else:
                _LOGGER.warning("Could not get image data from attachment: %s", attachment)

        return successful_images

    async def get_image_data_from_attachment(self, attachment: Any) -> str | None:
        """Extract base64 image data from an attachment."""
        try:
            if hasattr(attachment, "path") and attachment.path:
                return await self._read_image_from_path(attachment.path)

            if hasattr(attachment, "media_content_id") and attachment.media_content_id:
                image_bytes = await self._async_get_media_content(attachment.media_content_id)
                if image_bytes:
                    return base64.b64encode(image_bytes).decode()
                return None

            if hasattr(attachment, "content") and attachment.content:
                if isinstance(attachment.content, bytes):
                    return base64.b64encode(attachment.content).decode()
                if isinstance(attachment.content, str):
                    return attachment.content

            _LOGGER.warning("Attachment format not supported: %s", attachment)
            return None
        except Exception as err:
            _LOGGER.error("Failed to process image attachment %s: %s", attachment, err, exc_info=True)
            return None

    async def _read_image_from_path(self, path: str) -> str | None:
        try:
            image_bytes = await asyncio.to_thread(self._read_file_bytes, str(path))
            return base64.b64encode(image_bytes).decode()
        except Exception as err:
            _LOGGER.error("Failed to read file %s: %s", path, err, exc_info=True)
            return None

    async def _async_download_image_from_url(self, url: str) -> bytes | None:
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url, timeout=client_timeout(30)) as response:
                if response.status == 200:
                    return await response.read()
                _LOGGER.warning("Failed to download image from URL: %s, status: %s", url, response.status)
                return None
        except Exception as err:
            _LOGGER.warning("Error downloading image from URL %s: %s", url, err)
            return None

    async def _async_get_media_content(self, media_content_id: str) -> bytes | None:
        try:
            if media_content_id.startswith("media-source://"):
                return await self._resolve_media_source(media_content_id)
            if media_content_id.startswith(("/api/image/serve/", "api/image/serve/")):
                return await self._fetch_served_image(media_content_id)
            if media_content_id.startswith(("http://", "https://")):
                return await self._async_download_image_from_url(media_content_id)
            _LOGGER.warning("Unsupported media content ID format: %s", media_content_id)
            return None
        except Exception as err:
            _LOGGER.error("Unexpected error getting media content %s: %s", media_content_id, err, exc_info=True)
            return None

    async def _resolve_media_source(self, media_content_id: str) -> bytes | None:
        if not media_source.is_media_source_id(media_content_id):
            _LOGGER.warning("Invalid media source ID: %s", media_content_id)
            return None

        try:
            media_item = await media_source.async_resolve_media(self.hass, media_content_id, self.entity_id)
        except Exception as err:
            _LOGGER.error("Error resolving media source %s: %s", media_content_id, err, exc_info=True)
            return None

        if not (media_item and hasattr(media_item, "url") and media_item.url):
            _LOGGER.warning("Could not resolve media source or no URL: %s", media_content_id)
            return None
        return await self._download_from_url(self._build_full_url(media_item.url))

    def _build_full_url(self, url: str) -> str:
        if not url.startswith("/"):
            return url
        try:
            if hasattr(self.hass.config, "external_url") and self.hass.config.external_url:
                base_url = self.hass.config.external_url.rstrip("/")
            elif hasattr(self.hass.config, "internal_url") and self.hass.config.internal_url:
                base_url = self.hass.config.internal_url.rstrip("/")
            else:
                base_url = "http://localhost:8123"
        except Exception as err:
            _LOGGER.warning("Could not get Home Assistant URL, using localhost: %s", err)
            base_url = "http://localhost:8123"
        return f"{base_url}{url}"

    async def _fetch_served_image(self, url: str) -> bytes | None:
        if not url.startswith("/"):
            url = f"/{url}"
        return await self._download_from_url(url)

    async def _download_from_url(self, url: str) -> bytes | None:
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url, timeout=client_timeout(30)) as response:
                if response.status == 200:
                    return await response.read()
                _LOGGER.warning("Failed to download from %s, status: %s", url, response.status)
                return None
        except Exception as err:
            _LOGGER.error("Error downloading from %s: %s", url, err, exc_info=True)
            return None

    @staticmethod
    def _read_file_bytes(file_path: str) -> bytes:
        with open(file_path, "rb") as file_handle:
            return file_handle.read()
