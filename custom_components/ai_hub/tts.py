"""Text to speech support for AI Hub using Edge TTS - 支持流式输出和 prosody 参数."""

from __future__ import annotations

import logging
import time
from typing import Any
from collections.abc import AsyncGenerator

from propcache.api import cached_property

from homeassistant.components.tts import (
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    TTSAudioRequest,
    TTSAudioResponse,
    Voice,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import device_registry as dr

try:
    import edge_tts
    import edge_tts.exceptions
except ImportError:
    try:
        import edgeTTS
        raise Exception('Please uninstall edgeTTS and install edge_tts instead.')
    except ImportError:
        raise Exception('edge_tts is required. Please install edge_tts.')

from .const import (
    CONF_TTS_VOICE,
    CONF_TTS_LANG,
    TTS_DEFAULT_VOICE,
    TTS_DEFAULT_LANG,
    EDGE_TTS_VOICES,
    DOMAIN,
)
from .entity import AIHubEntityBase

# Create supported languages dynamically
SUPPORTED_LANGUAGES = {
    **dict(zip(EDGE_TTS_VOICES.values(), EDGE_TTS_VOICES.keys())),
    'zh-CN': 'zh-CN-XiaoxiaoNeural',
}

_LOGGER = logging.getLogger(__name__)

# Prosody 参数选项
PROSODY_OPTIONS = ['pitch', 'rate', 'volume']


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TTS entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "tts":
            continue

        async_add_entities(
            [AIHubTextToSpeechEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class AIHubTextToSpeechEntity(TextToSpeechEntity, AIHubEntityBase):
    """AI Hub text-to-speech entity using Edge TTS."""

    _attr_has_entity_name = False
    _attr_supported_options = ['voice'] + PROSODY_OPTIONS
    _attr_supports_streaming_input = True

    def __init__(self, config_entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the TTS entity."""
        super().__init__(config_entry, subentry, TTS_DEFAULT_VOICE)
        self._attr_available = True

        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="老王杂谈说",
            model="Edge TTS",
            sw_version=edge_tts.__version__,
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    @property
    def options(self) -> dict[str, Any]:
        """Return the options for this entity."""
        return self.subentry.data

    @cached_property
    def default_options(self) -> dict[str, Any]:
        """Return default options."""
        return {
            ATTR_VOICE: TTS_DEFAULT_VOICE,
            'pitch': '+0Hz',
            'rate': '+0%',
            'volume': '+0%',
        }

    @property
    def default_language(self) -> str:
        """Return the default language from configured voice."""
        if CONF_TTS_LANG in self.subentry.data:
            return self.subentry.data[CONF_TTS_LANG]
        voice = self.subentry.data.get(CONF_TTS_VOICE, TTS_DEFAULT_VOICE)
        return EDGE_TTS_VOICES.get(voice, TTS_DEFAULT_LANG)

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return list([*SUPPORTED_LANGUAGES.keys(), *EDGE_TTS_VOICES.keys()])

    @property
    def _supported_voices(self) -> list[Voice]:
        """Return supported voices."""
        return [Voice(voice_id, voice_id) for voice_id in EDGE_TTS_VOICES.keys()]

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice]:
        """Return a list of supported voices for a language."""
        if language is None:
            return self._supported_voices
        return [
            Voice(voice_id, voice_id)
            for voice_id, voice_lang in EDGE_TTS_VOICES.items()
            if voice_lang == language
        ]

    def _get_default_voice_for_language(self, language: str) -> str:
        """Get default voice for a language."""
        default_voices = {
            "zh-CN": "zh-CN-XiaoxiaoNeural",
            "zh-TW": "zh-TW-HsiaoChenNeural",
            "zh-HK": "zh-HK-HiuMaanNeural",
            "en-US": "en-US-JennyNeural",
            "en-GB": "en-GB-LibbyNeural",
            "ja-JP": "ja-JP-NanamiNeural",
            "ko-KR": "ko-KR-SunHiNeural",
            "fr-FR": "fr-FR-DeniseNeural",
            "de-DE": "de-DE-KatjaNeural",
            "es-ES": "es-ES-ElviraNeural",
            "it-IT": "it-IT-ElsaNeural",
            "pt-BR": "pt-BR-FranciscaNeural",
            "ru-RU": "ru-RU-SvetlanaNeural",
        }
        return default_voices.get(language, TTS_DEFAULT_VOICE)

    def _resolve_voice(self, language: str, options: dict[str, Any] | None) -> str:
        """Resolve voice from options, config, or language default."""
        voice = None
        if options and options.get('voice'):
            voice = options['voice']
        else:
            voice = self.subentry.data.get(CONF_TTS_VOICE, TTS_DEFAULT_VOICE)

        # 如果 voice 是语言代码，转换为对应的默认语音
        if voice in SUPPORTED_LANGUAGES:
            voice = SUPPORTED_LANGUAGES[voice]

        if voice not in EDGE_TTS_VOICES:
            voice = self._get_default_voice_for_language(language)
            if voice not in EDGE_TTS_VOICES:
                voice = TTS_DEFAULT_VOICE

        return voice

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> TtsAudioType:
        """Load TTS audio."""
        return "mp3", await self._process_tts_audio(message, language, options or {})

    async def _process_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> bytes:
        """Process TTS with prosody support."""
        if not message or not message.strip():
            raise HomeAssistantError("文本内容不能为空")

        voice = self._resolve_voice(language, options)

        # Prosody 参数
        pitch = options.get('pitch', '+0Hz')
        rate = options.get('rate', '+0%')
        volume = options.get('volume', '+0%')

        _LOGGER.debug(
            'TTS: message="%s", voice="%s", pitch=%s, rate=%s, volume=%s',
            message[:50], voice, pitch, rate, volume
        )

        start_time = time.perf_counter()

        try:
            communicate = edge_tts.Communicate(
                text=message,
                voice=voice,
                pitch=pitch,
                rate=rate,
                volume=volume,
            )

            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            _LOGGER.debug("TTS 生成耗时: %.1fms, 音频大小: %d bytes", elapsed_ms, len(audio_bytes))

            if not audio_bytes:
                raise HomeAssistantError("未生成音频数据")

            return audio_bytes

        except edge_tts.exceptions.NoAudioReceived as exc:
            _LOGGER.warning("Edge TTS 未收到音频: %s", message[:50])
            raise HomeAssistantError(f"TTS 未收到音频: {message[:50]}") from exc
        except Exception as exc:
            _LOGGER.error("Edge TTS 生成失败: %s", exc)
            # 使用默认参数重试
            if voice != TTS_DEFAULT_VOICE:
                _LOGGER.warning("尝试使用默认语音重试...")
                try:
                    communicate = edge_tts.Communicate(text=message, voice=TTS_DEFAULT_VOICE)
                    audio_bytes = b""
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_bytes += chunk["data"]
                    if audio_bytes:
                        _LOGGER.info("使用默认语音成功")
                        return audio_bytes
                except Exception as retry_exc:
                    _LOGGER.error("默认语音重试失败: %s", retry_exc)
            raise HomeAssistantError(f"TTS 生成失败: {exc}") from exc

    # ========== 流式输出支持 ==========

    async def async_stream_tts_audio(self, request: TTSAudioRequest) -> TTSAudioResponse:
        """Stream TTS audio - Home Assistant 2024.1+ support."""
        return TTSAudioResponse("mp3", self._stream_tts_audio(request))

    async def _stream_tts_audio(self, request: TTSAudioRequest) -> AsyncGenerator[bytes, None]:
        """Stream TTS audio generation."""
        _LOGGER.debug("开始流式TTS, options: %s", request.options)

        separators = "\n。.，,；;！!？?、"
        buffer = ""
        count = 0

        async for message in request.message_gen:
            _LOGGER.debug("流式TTS收到: %s", message)
            count += 1
            min_len = 2 ** count * 10

            for char in message:
                buffer += char
                msg = buffer.strip()
                if len(msg) >= min_len and char in separators:
                    audio = await self._generate_stream_audio(msg, request.language, request.options)
                    if audio:
                        yield audio
                    buffer = ""

        if msg := buffer.strip():
            audio = await self._generate_stream_audio(msg, request.language, request.options)
            if audio:
                yield audio

    async def _generate_stream_audio(
        self, message: str, language: str, options: dict[str, Any] | None
    ) -> bytes | None:
        """Generate audio for streaming."""
        if not message:
            return None

        voice = self._resolve_voice(language, options)
        pitch = options.get('pitch', '+0Hz') if options else '+0Hz'
        rate = options.get('rate', '+0%') if options else '+0%'
        volume = options.get('volume', '+0%') if options else '+0%'

        try:
            communicate = edge_tts.Communicate(
                text=message,
                voice=voice,
                pitch=pitch,
                rate=rate,
                volume=volume,
            )

            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]

            return audio_bytes if audio_bytes else None

        except edge_tts.exceptions.NoAudioReceived:
            _LOGGER.warning("流式TTS未收到音频: %s", message[:30])
            return None
        except Exception as exc:
            _LOGGER.error("流式TTS失败: %s", exc)
            return None
