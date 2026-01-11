"""Services for AI Hub integration."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path

import yaml

import aiohttp
# import requests  # 使用异步 aiohttp 替代同步 requests
import voluptuous as vol
from homeassistant.components import camera
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AI_HUB_CHAT_URL,
    AI_HUB_IMAGE_GEN_URL,
    AI_HUB_STT_AUDIO_FORMATS,
    AI_HUB_STT_MODELS,
    AI_HUB_TTS_URL,
    BEMFA_API_URL,
    CONF_API_KEY,
    CONF_BEMFA_UID,
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_SILICONFLOW_API_KEY,
    CONF_STT_FILE,
    CONF_TEMPERATURE,
    CONF_CUSTOM_COMPONENTS_PATH,
    CONF_FORCE_TRANSLATION,
    CONF_TARGET_COMPONENT,
    DEFAULT_REQUEST_TIMEOUT,
    DOMAIN,
    EDGE_TTS_VOICES,
    ERROR_GETTING_RESPONSE,
    IMAGE_SIZES,
    RECOMMENDED_IMAGE_ANALYSIS_MODEL,
    RECOMMENDED_IMAGE_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_STT_MODEL,
    RECOMMENDED_TEMPERATURE,
    SERVICE_ANALYZE_IMAGE,
    SERVICE_GENERATE_IMAGE,
    SERVICE_STT_TRANSCRIBE,
    SERVICE_TTS_SPEECH,
    SERVICE_TTS_STREAM,
    SERVICE_SEND_WECHAT_MESSAGE,
    SERVICE_TRANSLATE_COMPONENTS,
    SERVICE_TRANSLATE_BLUEPRINTS,
    SILICONFLOW_ASR_URL,
    STT_MAX_FILE_SIZE_MB,
    TTS_DEFAULT_VOICE,
)

_LOGGER = logging.getLogger(__name__)

# Schema for image analysis service
IMAGE_ANALYZER_SCHEMA = {
    vol.Optional("image_file"): cv.string,
    vol.Optional("image_entity"): cv.entity_id,
    vol.Required("message"): cv.string,
    vol.Optional("model", default=RECOMMENDED_IMAGE_ANALYSIS_MODEL): cv.string,
    vol.Optional("temperature", default=RECOMMENDED_TEMPERATURE): vol.Coerce(float),
    vol.Optional("max_tokens", default=RECOMMENDED_MAX_TOKENS): cv.positive_int,
    vol.Optional("stream", default=False): cv.boolean,
}

# Schema for image generation service
IMAGE_GENERATOR_SCHEMA = {
    vol.Required("prompt"): cv.string,
    vol.Optional("size", default="1024x1024"): vol.In(IMAGE_SIZES),
    vol.Optional("model", default=RECOMMENDED_IMAGE_MODEL): cv.string,
}

# Schema for Edge TTS service
TTS_SCHEMA = {
    vol.Required("text"): cv.string,
    vol.Optional("voice", default=TTS_DEFAULT_VOICE): vol.In(list(EDGE_TTS_VOICES.keys())),
    vol.Optional("media_player_entity"): cv.entity_id,
}

# Schema for streaming Edge TTS service
TTS_STREAM_SCHEMA = {
    vol.Required("text"): cv.string,
    vol.Optional("voice", default=TTS_DEFAULT_VOICE): vol.In(list(EDGE_TTS_VOICES.keys())),
    vol.Optional("chunk_size", default=4096): vol.Coerce(int),
}

# Schema for Silicon Flow STT service
STT_SCHEMA = {
    vol.Required(CONF_STT_FILE): cv.string,
    vol.Optional("model", default=RECOMMENDED_STT_MODEL): vol.In(AI_HUB_STT_MODELS),
}

# Schema for Bemfa WeChat service
WECHAT_SCHEMA = {
    vol.Required("device_entity"): cv.entity_id,
    vol.Required("message"): cv.string,
    vol.Optional("url", default=""): cv.string,
}

# Schema for translation service
TRANSLATION_SCHEMA = {
    vol.Optional("list_components", default=False): cv.boolean,
    vol.Optional("force_translation", default=False): cv.boolean,
    vol.Optional("target_component", default=""): cv.string,
}

# Schema for blueprints translation service
BLUEPRINTS_TRANSLATION_SCHEMA = {
    vol.Optional("list_blueprints", default=False): cv.boolean,
    vol.Optional("target_blueprint", default=""): cv.string,
    vol.Optional("retranslate", default=False): cv.boolean,
}


async def async_setup_services(hass: HomeAssistant, config_entry) -> None:
    """Set up services for AI Hub integration."""

    api_key = config_entry.runtime_data
    bemfa_uid = config_entry.data.get(CONF_BEMFA_UID) if hasattr(config_entry, 'data') else None

    # Store bemfa_uid in config_entry for easy access
    if bemfa_uid:
        setattr(config_entry, 'bemfa_uid', bemfa_uid)

    # Function to check if we have required API keys for services
    def has_zhipu_api_key() -> bool:
        return api_key is not None and api_key.strip() != ""

    def has_bemfa_uid() -> bool:
        return bemfa_uid is not None and bemfa_uid.strip() != ""

    async def handle_analyze_image(call: ServiceCall) -> dict:
        """Handle image analysis service call."""
        try:
            if not has_zhipu_api_key():
                return {
                    "success": False,
                    "error": "智谱AI API密钥未配置，请先在集成配置中设置API密钥"
                }

            image_data = None

            # Get image from file
            if image_file := call.data.get("image_file"):
                image_data = await _load_image_from_file(hass, image_file)

            # Get image from camera entity
            elif image_entity := call.data.get("image_entity"):
                image_data = await _load_image_from_camera(hass, image_entity)

            if not image_data:
                raise ServiceValidationError("必须提供 image_file 或 image_entity 参数")

            # Resize and convert image to save bandwidth
            processed_image_data = await _process_image(image_data)
            base64_image = base64.b64encode(processed_image_data).decode()

            # Prepare API request
            model = call.data.get("model", RECOMMENDED_IMAGE_ANALYSIS_MODEL)
            message = call.data["message"]
            temperature = call.data.get("temperature", RECOMMENDED_TEMPERATURE)
            max_tokens = call.data.get("max_tokens", RECOMMENDED_MAX_TOKENS)
            stream = call.data.get("stream", False)

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            # Try exact format from AI Hub official documentation
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            },
                            {
                                "type": "text",
                                "text": message
                            }
                        ]
                    }
                ]
            }

            # Only add non-problematic parameters
            if stream:
                payload["stream"] = True

            # Make API call
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    AI_HUB_CHAT_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        _LOGGER.error("API request failed: %s", error_text)
                        raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE}: {error_text}")

                    if stream:
                        return await _handle_stream_response(hass, response)
                    else:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        return {
                            "success": True,
                            "content": content,
                            "model": model,
                        }

        except Exception as err:
            _LOGGER.error("Error analyzing image: %s", err)
            return {
                "success": False,
                "error": str(err)
            }

    async def handle_generate_image(call: ServiceCall) -> dict:
        """Handle image generation service call."""
        try:
            if not has_zhipu_api_key():
                return {
                    "success": False,
                    "error": "智谱AI API密钥未配置，请先在集成配置中设置API密钥"
                }
            prompt = call.data["prompt"]
            size = call.data.get("size", "1024x1024")
            model = call.data.get("model", RECOMMENDED_IMAGE_MODEL)

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": model,
                "prompt": prompt,
                "size": size,
            }

            # Make API call
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    AI_HUB_IMAGE_GEN_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=120),  # Image generation takes longer
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        _LOGGER.error("Image generation API request failed: %s", error_text)
                        raise HomeAssistantError(f"{ERROR_GETTING_RESPONSE}: {error_text}")

                    result = await response.json()

                    # Process the response based on AI Hub's actual API response format
                    if "data" in result and len(result["data"]) > 0:
                        image_data = result["data"][0]
                        image_url = image_data.get("url", "")
                        if image_url:
                            return {
                                "success": True,
                                "image_url": image_url,
                                "prompt": prompt,
                                "size": size,
                                "model": model,
                            }
                        else:
                            # If base64 image is returned instead of URL
                            b64_json = image_data.get("b64_json", "")
                            if b64_json:
                                return {
                                    "success": True,
                                    "image_base64": b64_json,
                                    "prompt": prompt,
                                    "size": size,
                                    "model": model,
                                }

                    raise HomeAssistantError("无法获取生成的图像")

        except Exception as err:
            _LOGGER.error("Error generating image: %s", err)
            return {
                "success": False,
                "error": str(err)
            }

    async def handle_tts_speech(call: ServiceCall) -> dict:
        """Handle TTS service call."""
        try:
            if not has_zhipu_api_key():
                return {
                    "success": False,
                    "error": "智谱AI API密钥未配置，请先在集成配置中设置API密钥"
                }
            text = call.data["text"]
            voice = call.data.get("voice", TTS_DEFAULT_VOICE)
            media_player_entity = call.data.get("media_player_entity")

            # 验证参数
            if not text or not text.strip():
                raise ServiceValidationError("文本内容不能为空")

            if voice not in EDGE_TTS_VOICES:
                raise ServiceValidationError(f"不支持的语音类型: {voice}")

            # 构建 TTS API 请求
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": "cogtts",
                "input": text,
                "voice": voice,
                "response_format": "wav",
            }

            timeout = aiohttp.ClientTimeout(total=DEFAULT_REQUEST_TIMEOUT / 1000)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    AI_HUB_TTS_URL,
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        _LOGGER.error(
                            "智谱AI TTS API 错误: %s - %s",
                            response.status,
                            error_text
                        )
                        return {
                            "success": False,
                            "error": f"TTS API 请求失败: {response.status}"
                        }

                    # 处理响应
                    response_data = await response.json()

                    if not response_data:
                        return {"success": False, "error": "API 响应为空"}

                    # 解码音频为 WAV 格式
                    from .helpers import decode_base64_audio
                    wav_audio_data = decode_base64_audio(response_data)

                    # 将WAV数据编码为base64供返回使用
                    audio_base64 = base64.b64encode(wav_audio_data).decode('utf-8')

                    # 如果指定了媒体播放器实体，直接播放
                    if media_player_entity:
                        try:
                            # 将音频数据保存为临时文件
                            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                                temp_file.write(wav_audio_data)
                                temp_file_path = temp_file.name

                            # 调用媒体播放器的播放服务
                            await hass.services.async_call(
                                "media_player",
                                "play_media",
                                {
                                    "entity_id": media_player_entity,
                                    "media_content_id": f"file://{temp_file_path}",
                                    "media_content_type": "audio/wav",
                                },
                                blocking=True,
                            )

                            # 延迟删除临时文件
                            await asyncio.sleep(1)
                            try:
                                os.unlink(temp_file_path)
                            except OSError:
                                pass  # 文件可能已被系统删除

                            return {
                                "success": True,
                                "message": "语音播放成功",
                                "media_player": media_player_entity,
                            }

                        except Exception as exc:
                            _LOGGER.error("媒体播放失败: %s", exc)
                            return {
                                "success": False,
                                "error": f"媒体播放失败: {exc}",
                                "audio_data": audio_base64,
                            }

                    # 返回音频数据供其他用途
                    return {
                        "success": True,
                        "audio_data": audio_base64,
                        "audio_format": "wav",
                        "voice": voice,
                    }

        except ServiceValidationError as exc:
            _LOGGER.error("TTS service validation error: %s", exc)
            return {"success": False, "error": str(exc)}
        except aiohttp.ClientError as exc:
            _LOGGER.error("TTS service network error: %s", exc)
            return {"success": False, "error": f"网络请求失败: {exc}"}
        except asyncio.TimeoutError as exc:
            _LOGGER.error("TTS service timeout: %s", exc)
            return {"success": False, "error": "请求超时"}
        except Exception as exc:
            _LOGGER.error("TTS service error: %s", exc, exc_info=True)
            return {"success": False, "error": f"TTS 生成失败: {exc}"}

    async def handle_tts_stream(call: ServiceCall) -> dict:
        """Handle streaming Edge TTS service call."""
        try:
            # 导入 edge_tts
            try:
                import edge_tts
            except ImportError:
                return {
                    "success": False,
                    "error": "edge_tts 库未安装，请先安装: pip install edge-tts"
                }

            text = call.data["text"]
            voice = call.data.get("voice", TTS_DEFAULT_VOICE)
            chunk_size = call.data.get("chunk_size", 4096)

            # 验证参数
            if not text or not text.strip():
                raise ServiceValidationError("文本内容不能为空")

            if voice not in EDGE_TTS_VOICES:
                raise ServiceValidationError(f"不支持的语音类型: {voice}")

            _LOGGER.info("Starting streaming TTS: text='%s', voice='%s'", text[:50], voice)

            # 创建 Edge TTS communicate 对象
            communicate = edge_tts.Communicate(text=text, voice=voice)

            # 准备流式响应
            audio_chunks = []
            total_bytes = 0
            chunk_count = 0

            # 流式获取音频数据
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data = chunk["data"]
                    audio_chunks.append(audio_data)
                    total_bytes += len(audio_data)
                    chunk_count += 1

                    # 当累积的数据达到 chunk_size 时，通过事件推送
                    if total_bytes >= chunk_size:
                        combined_chunk = b"".join(audio_chunks)
                        # 触发事件，通知前端有新数据可用
                        hass.bus.async_fire(
                            f"{DOMAIN}_tts_stream_chunk",
                            {
                                "voice": voice,
                                "chunk_index": len(audio_chunks),
                                "chunk_size": len(combined_chunk),
                                "total_bytes": total_bytes,
                                # 将音频数据编码为 base64 以便通过 JSON 传输
                                "audio_chunk": base64.b64encode(combined_chunk).decode("utf-8"),
                                "content_type": "audio/mpeg",
                            }
                        )
                        audio_chunks = []

            # 发送最后一个块和完成事件
            if audio_chunks:
                final_chunk = b"".join(audio_chunks)
                hass.bus.async_fire(
                    f"{DOMAIN}_tts_stream_chunk",
                    {
                        "voice": voice,
                        "chunk_index": chunk_count + 1,
                        "chunk_size": len(final_chunk),
                        "total_bytes": total_bytes,
                        "audio_chunk": base64.b64encode(final_chunk).decode("utf-8"),
                        "content_type": "audio/mpeg",
                    }
                )

            # 发送流完成事件
            hass.bus.async_fire(
                f"{DOMAIN}_tts_stream_complete",
                {
                    "voice": voice,
                    "total_chunks": chunk_count,
                    "total_bytes": total_bytes,
                    "text": text,
                }
            )

            _LOGGER.info(
                "Streaming TTS completed: %d chunks, %d bytes",
                chunk_count,
                total_bytes
            )

            return {
                "success": True,
                "method": "stream",
                "voice": voice,
                "total_chunks": chunk_count,
                "total_bytes": total_bytes,
                "message": "音频流已通过事件总线推送，请监听 ai_hub_tts_stream_chunk 事件",
            }

        except ServiceValidationError as exc:
            _LOGGER.error("Streaming TTS validation error: %s", exc)
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            _LOGGER.error("Streaming TTS error: %s", exc, exc_info=True)
            return {"success": False, "error": f"流式 TTS 生成失败: {exc}"}

    async def handle_stt_transcribe(call: ServiceCall) -> dict:
        """Handle Silicon Flow STT service call."""
        try:
            # Check if Silicon Flow API key is configured
            siliconflow_api_key = getattr(
                config_entry, 'data', {}).get(CONF_SILICONFLOW_API_KEY) if hasattr(
                config_entry, 'data') else None
            if not siliconflow_api_key or not siliconflow_api_key.strip():
                return {
                    "success": False,
                    "error": "硅基流动API密钥未配置，请先在集成配置中设置"
                }
            audio_file = call.data[CONF_STT_FILE]
            model = call.data.get("model", RECOMMENDED_STT_MODEL)

            # 验证参数
            if not audio_file or not audio_file.strip():
                raise ServiceValidationError("音频文件路径不能为空")

            if model not in AI_HUB_STT_MODELS:
                raise ServiceValidationError(f"不支持的模型: {model}")

            # 加载音频文件
            try:
                # 处理相对路径
                if not os.path.isabs(audio_file):
                    audio_file = os.path.join(hass.config.config_dir, audio_file)

                if not os.path.exists(audio_file):
                    raise ServiceValidationError(f"音频文件不存在: {audio_file}")

                if os.path.isdir(audio_file):
                    raise ServiceValidationError(f"提供的路径是一个目录: {audio_file}")

                # 检查文件大小
                file_size = os.path.getsize(audio_file)
                if file_size > STT_MAX_FILE_SIZE_MB * 1024 * 1024:
                    raise ServiceValidationError(f"音频文件过大，最大支持 {STT_MAX_FILE_SIZE_MB}MB")

                # 检查文件格式
                file_ext = os.path.splitext(audio_file)[1].lower().lstrip('.')
                if file_ext not in SILICONFLOW_STT_AUDIO_FORMATS:
                    raise ServiceValidationError(
                        f"不支持的音频格式: {file_ext}，支持的格式: {
                            ', '.join(SILICONFLOW_STT_AUDIO_FORMATS)}")

                # 读取音频文件
                with open(audio_file, "rb") as f:
                    audio_data = f.read()

            except IOError as err:
                raise ServiceValidationError(f"读取音频文件失败: {err}")

            # 构建 STT API 请求
            headers = {
                "Authorization": f"Bearer {siliconflow_api_key}",
            }

            # 准备文件上传
            form_data = aiohttp.FormData()
            form_data.add_field(
                "file",
                audio_data,
                filename=os.path.basename(audio_file),
                content_type=f"audio/{file_ext}"
            )
            form_data.add_field("model", model)

            timeout = aiohttp.ClientTimeout(total=DEFAULT_REQUEST_TIMEOUT / 1000)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    SILICONFLOW_ASR_URL,
                    headers=headers,
                    data=form_data
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        _LOGGER.error(
                            "智谱AI STT API 错误: %s - %s",
                            response.status,
                            error_text
                        )
                        return {
                            "success": False,
                            "error": f"STT API 请求失败: {response.status}"
                        }

                    # 处理非流式响应 (Silicon Flow STT API 不支持流式)
                    response_data = await response.json()

                    if "text" not in response_data:
                        _LOGGER.error("STT API 响应格式错误: %s", response_data)
                        return {"success": False, "error": "API 响应格式错误"}

                    transcribed_text = response_data["text"]

                    return {
                        "success": True,
                        "text": transcribed_text,
                        "model": model,
                        "audio_file": audio_file,
                        "file_size_mb": round(file_size / (1024 * 1024), 2),
                    }

        except ServiceValidationError as exc:
            _LOGGER.error("STT service validation error: %s", exc)
            return {"success": False, "error": str(exc)}
        except aiohttp.ClientError as exc:
            _LOGGER.error("STT service network error: %s", exc)
            return {"success": False, "error": f"网络请求失败: {exc}"}
        except asyncio.TimeoutError as exc:
            _LOGGER.error("STT service timeout: %s", exc)
            return {"success": False, "error": "请求超时"}
        except Exception as exc:
            _LOGGER.error("STT service error: %s", exc, exc_info=True)
            return {"success": False, "error": f"STT 转录失败: {exc}"}

    async def handle_send_wechat_message(call: ServiceCall) -> dict:
        """Handle Bemfa WeChat message service call."""
        try:
            # Get Bemfa UID from config entry or service data
            bemfa_uid = getattr(config_entry, 'bemfa_uid', None) or call.data.get("bemfa_uid")

            if not bemfa_uid or not bemfa_uid.strip():
                return {
                    "success": False,
                    "error": "巴法云UID未配置，请在集成配置中设置或通过服务参数提供"
                }

            device_entity = call.data["device_entity"]
            message = call.data["message"].strip()
            url = call.data.get("url", "")

            if not device_entity or not message:
                return {
                    "success": False,
                    "error": "device_entity 和 message 参数必填"
                }

            # Get entity state
            state_obj = hass.states.get(device_entity)
            if state_obj:
                friendly_name = state_obj.attributes.get("friendly_name", device_entity)
                state_value = state_obj.state
            else:
                friendly_name = device_entity
                state_value = "无实体状态"

            # Create title with entity name and state
            device_title = f"{friendly_name}（状态：{state_value}）"

            # Message content remains as the original message only
            message_content = message

            _LOGGER.debug("微信设备标题：%s", device_title)
            _LOGGER.debug("微信消息内容：%s", message_content)

            # Use device field as title
            payload = {
                "uid": bemfa_uid,
                "device": device_title,  # Use device field for entity name and state
                "message": message_content,  # Message contains only the user-provided message
                "group": "default",  # Always use default group
                "url": url,
            }

            headers = {"Content-Type": "application/json; charset=utf-8"}
            timeout = aiohttp.ClientTimeout(total=10)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    BEMFA_API_URL,
                    json=payload,
                    headers=headers
                ) as response:
                    resp_text = await response.text()
                    if response.status == 200:
                        _LOGGER.info("微信消息发送成功")
                        return {
                            "success": True,
                            "message": "微信消息发送成功",
                            "device": device_entity
                        }
                    else:
                        _LOGGER.error("发送失败 [%s]: %s", response.status, resp_text)
                        return {
                            "success": False,
                            "error": f"发送失败 [{response.status}]: {resp_text}"
                        }

        except aiohttp.ClientError as exc:
            _LOGGER.error("网络请求错误: %s", exc)
            return {"success": False, "error": f"网络请求错误: {exc}"}
        except Exception as exc:
            _LOGGER.exception("发送微信消息异常: %s", exc)
            return {"success": False, "error": f"发送微信消息异常: {exc}"}

    async def handle_translate_components(call: ServiceCall) -> dict:
        """Handle translation service call - 使用异步版本."""
        try:
            # Get parameters
            list_components = call.data.get("list_components", False)
            target_component = call.data.get("target_component", "").strip()
            force_translation = call.data.get("force_translation", False)

            # 仅列出模式不需要API密钥
            if not list_components:
                # Check if Zhipu API key is available
                if not has_zhipu_api_key():
                    return {
                        "success": False,
                        "error": "智谱AI API密钥未配置，请先配置AI Hub集成"
                    }

            if list_components:
                _LOGGER.info("列出已安装的集成...")
            else:
                _LOGGER.info("开始组件翻译（异步）...")

            # 使用异步版本直接调用，不需要 async_add_executor_job
            result = await async_translate_all_components(
                custom_components_path="custom_components",
                api_key=api_key if not list_components else None,
                force_translation=force_translation,
                target_component=target_component,
                list_components=list_components
            )

            return {
                "success": True,
                "result": result
            }

        except Exception as exc:
            _LOGGER.error("翻译服务错误: %s", exc)
            return {
                "success": False,
                "error": f"翻译服务错误: {exc}"
            }

    async def handle_translate_blueprints(call: ServiceCall) -> dict:
        """Handle blueprints translation service call - 使用异步版本."""
        try:
            # Get parameters
            list_blueprints = call.data.get("list_blueprints", False)
            target_blueprint = call.data.get("target_blueprint", "").strip()
            retranslate = call.data.get("retranslate", False)
            # 使用 Home Assistant 配置目录
            blueprints_path = hass.config.path("blueprints")

            # 仅列出模式不需要API密钥
            if not list_blueprints:
                # Check if Zhipu API key is available
                if not has_zhipu_api_key():
                    return {
                        "success": False,
                        "error": "智谱AI API密钥未配置，请先配置AI Hub集成"
                    }

            if list_blueprints:
                _LOGGER.info("列出Blueprint文件...")
            else:
                _LOGGER.info("开始Blueprint翻译（异步）...")

            # 使用异步版本直接调用，不需要 async_add_executor_job
            result = await async_translate_all_blueprints(
                api_key=api_key if not list_blueprints else None,
                retranslate=retranslate,
                target_blueprint=target_blueprint,
                list_blueprints=list_blueprints,
                blueprints_path=blueprints_path
            )

            return {
                "success": True,
                "result": result
            }

        except Exception as exc:
            _LOGGER.error("Blueprint翻译服务错误: %s", exc)
            return {
                "success": False,
                "error": f"Blueprint翻译服务错误: {exc}"
            }

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_ANALYZE_IMAGE,
        handle_analyze_image,
        schema=vol.Schema(IMAGE_ANALYZER_SCHEMA),
        supports_response=True
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_IMAGE,
        handle_generate_image,
        schema=vol.Schema(IMAGE_GENERATOR_SCHEMA),
        supports_response=True
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TTS_SPEECH,
        handle_tts_speech,
        schema=vol.Schema(TTS_SCHEMA),
        supports_response=True
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TTS_STREAM,
        handle_tts_stream,
        schema=vol.Schema(TTS_STREAM_SCHEMA),
        supports_response=True
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STT_TRANSCRIBE,
        handle_stt_transcribe,
        schema=vol.Schema(STT_SCHEMA),
        supports_response=True
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_WECHAT_MESSAGE,
        handle_send_wechat_message,
        schema=vol.Schema(WECHAT_SCHEMA),
        supports_response=True
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TRANSLATE_COMPONENTS,
        handle_translate_components,
        schema=vol.Schema(TRANSLATION_SCHEMA),
        supports_response=True
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TRANSLATE_BLUEPRINTS,
        handle_translate_blueprints,
        schema=vol.Schema(BLUEPRINTS_TRANSLATION_SCHEMA),
        supports_response=True
    )


async def _load_image_from_file(hass: HomeAssistant, image_file: str) -> bytes:
    """Load image from file path."""
    try:
        # Handle relative paths
        if not os.path.isabs(image_file):
            image_file = os.path.join(hass.config.config_dir, image_file)

        if not os.path.exists(image_file):
            raise ServiceValidationError(f"图像文件不存在: {image_file}")

        if os.path.isdir(image_file):
            raise ServiceValidationError(f"提供的路径是一个目录: {image_file}")

        with open(image_file, "rb") as f:
            return f.read()

    except IOError as err:
        raise ServiceValidationError(f"读取图像文件失败: {err}")


async def _load_image_from_camera(hass: HomeAssistant, entity_id: str) -> bytes:
    """Load image from camera entity."""
    try:
        if not entity_id.startswith("camera."):
            raise ServiceValidationError(f"无效的摄像头实体ID: {entity_id}")

        if not hass.states.get(entity_id):
            raise ServiceValidationError(f"摄像头实体不存在: {entity_id}")

        # Get image from camera
        image = await camera.async_get_image(hass, entity_id, timeout=10)

        if not image or not image.content:
            raise ServiceValidationError(f"无法从摄像头获取图像: {entity_id}")

        return image.content

    except (camera.CameraEntityImageError, TimeoutError) as err:
        raise ServiceValidationError(f"获取摄像头图像失败: {err}")


async def _process_image(image_data: bytes, max_size: int = 1024, quality: int = 85) -> bytes:
    """Process image: resize and compress to optimize for API."""
    try:
        # Open image
        from PIL import Image
        img = Image.open(io.BytesIO(image_data))

        # Convert to RGB if necessary (for JPEG compatibility)
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
            else:
                background.paste(img)
            img = background

        # Resize if too large
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Compress to JPEG
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        return buffer.getvalue()

    except Exception as err:
        _LOGGER.warning("Failed to process image: %s, using original", err)
        return image_data


async def _handle_stream_response(hass: HomeAssistant, response: aiohttp.ClientResponse) -> dict:
    """Handle streaming response from API."""
    event_id = f"zhipuai_image_analysis_{int(time.time())}"

    try:
        hass.bus.async_fire(f"{DOMAIN}_image_analysis_start", {"event_id": event_id})

        accumulated_text = ""
        async for line in response.content:
            if line:
                try:
                    line_text = line.decode('utf-8').strip()
                    if line_text.startswith('data: '):
                        line_text = line_text[6:]  # Remove 'data: ' prefix

                    if line_text == '[DONE]':
                        break

                    if line_text:
                        json_data = json.loads(line_text)
                        if 'choices' in json_data and len(json_data['choices']) > 0:
                            content = json_data['choices'][0].get('delta', {}).get('content', '')
                            if content:
                                accumulated_text += content
                                hass.bus.async_fire(
                                    f"{DOMAIN}_image_analysis_token",
                                    {
                                        "event_id": event_id,
                                        "content": content,
                                        "full_content": accumulated_text
                                    }
                                )
                except json.JSONDecodeError:
                    continue

        return {
            "success": True,
            "content": accumulated_text,
            "stream_event_id": event_id,
        }

    except Exception as err:
        _LOGGER.error("Error handling stream response: %s", err)
        return {
            "success": False,
            "error": str(err)
        }


# Translation functionality (adapted from translation_localizer)
def translate_all_components(custom_components_path: str, api_key: str, force_translation: bool = False,
                             target_component: str = "", list_components: bool = False) -> dict:
    """Translate or list components in the custom_components directory."""
    # Find the custom components directory
    base_path = None

    # Try common paths
    paths_to_try = [
        Path(custom_components_path),
        Path("/config") / custom_components_path,
        Path.home() / ".homeassistant" / custom_components_path,
    ]

    for path in paths_to_try:
        if path.exists() and path.is_dir():
            base_path = path
            break

    if not base_path:
        return {
            "translated": 0,
            "skipped": 0,
            "error": f"Custom components directory not found: {custom_components_path}"
        }

    _LOGGER.info(f"Scanning components in: {base_path}")

    # 如果是仅列出模式，扫描所有组件并返回信息
    if list_components:
        all_components = []
        available_translations = []  # 有中文翻译的组件

        for component_dir in base_path.iterdir():
            if not component_dir.is_dir() or component_dir.name in ["ai_hub", "translation_localizer"]:
                continue

            component_info = {
                "name": component_dir.name,
                "has_translation": False,
                "has_english": False
            }

            translations_dir = component_dir / "translations"
            en_file = translations_dir / "en.json"
            zh_file = translations_dir / "zh-Hans.json"

            if en_file.exists():
                component_info["has_english"] = True
                all_components.append(component_dir.name)

                if zh_file.exists():
                    component_info["has_translation"] = True
                    available_translations.append(component_dir.name)
            else:
                # 没有英文文件但也算已安装的组件
                all_components.append(component_dir.name)

        _LOGGER.info(f"Found {len(all_components)} components, {len(available_translations)} have translations")

        return {
            "mode": "list_only",
            "total_components": len(all_components),
            "available_translations": len(available_translations),
            "all_components": sorted(all_components),
            "components_with_translations": sorted(available_translations),
            "target_component": target_component
        }

    # 翻译模式
    translated = 0
    skipped = 0
    translated_components = []  # 记录具体翻译的组件
    skipped_components = []     # 记录跳过的组件

    # 如果指定了目标组件，只处理该组件
    if target_component:
        target_dir = base_path / target_component
        if not target_dir.exists() or not target_dir.is_dir():
            return {
                "translated": 0,
                "skipped": 0,
                "error": f"Target component not found: {target_component}"
            }

        component_dirs = [target_dir]
        _LOGGER.info(f"Processing specific component: {target_component}")
    else:
        # 处理所有组件目录
        component_dirs = [d for d in base_path.iterdir() if d.is_dir() and d.name not in [
            "ai_hub", "translation_localizer"]]
        _LOGGER.info(f"Processing all components ({len(component_dirs)} found)")

    for component_dir in component_dirs:
        try:
            result = translate_component(component_dir, api_key, force_translation)
            if result == "translated":
                translated += 1
                translated_components.append(component_dir.name)
                _LOGGER.info(f"✓ Successfully translated {component_dir.name}")
            else:
                skipped += 1
                skipped_components.append(component_dir.name)
                _LOGGER.info(f"- Skipped {component_dir.name} ({result})")
        except Exception as e:
            _LOGGER.error(f"Error processing {component_dir.name}: {e}")
            skipped += 1
            skipped_components.append(f"{component_dir.name} (error: {str(e)})")

    return {
        "mode": "translate",
        "translated": translated,
        "skipped": skipped,
        "total": translated + skipped,
        "translated_components": translated_components,
        "skipped_components": skipped_components,
        "target_component": target_component
    }


def translate_component(component_dir: Path, api_key: str, force_translation: bool = False) -> str:
    """Translate a single component."""
    translations_dir = component_dir / "translations"
    en_file = translations_dir / "en.json"
    zh_file = translations_dir / "zh-Hans.json"

    # Check if translation is needed
    if not translations_dir.exists() or not en_file.exists():
        return "skipped"

    # Skip if Chinese translation already exists and not in force mode
    if zh_file.exists() and not force_translation:
        return "skipped"

    # If force mode is enabled and Chinese file exists, we'll re-translate
    if force_translation and zh_file.exists():
        _LOGGER.info(f"Force re-translating {component_dir.name} (overwriting existing)")
    else:
        _LOGGER.info(f"Translating {component_dir.name}")

    try:
        # Load English translations
        with open(en_file, 'r', encoding='utf-8') as f:
            en_data = json.load(f)

        # Translate the data
        zh_data = translate_json_values(en_data, api_key)

        # Save Chinese translations
        with open(zh_file, 'w', encoding='utf-8') as f:
            json.dump(zh_data, f, ensure_ascii=False, indent=2)

        _LOGGER.info(f"Successfully translated {component_dir.name}")
        return "translated"

    except Exception as e:
        _LOGGER.error(f"Failed to translate {component_dir.name}: {e}")
        return "error"


def translate_json_values(data: any, api_key: str) -> any:
    """Recursively translate JSON values."""
    if isinstance(data, dict):
        return {key: translate_json_values(value, api_key) for key, value in data.items()}
    elif isinstance(data, list):
        return [translate_json_values(item, api_key) for item in data]
    elif isinstance(data, str) and data.strip():
        # Translate strings
        return translate_text(data, api_key)
    else:
        return data


def translate_text(text: str, api_key: str) -> str:
    """Translate text using Zhipu AI while preserving placeholders."""
    if not text or len(text.strip()) < 2:
        return text

    # Skip placeholders and code - use regex to find placeholder patterns
    # Pattern to match {placeholder}, %placeholder, ${placeholder}, etc.
    placeholder_pattern = r'\{[^}]+\}|%\w+|\$\{[^}]+\}'

    # Check if text is primarily a placeholder
    if re.fullmatch(placeholder_pattern, text.strip()):
        return text

    # Check if text starts with placeholder patterns
    if text.startswith(("{", "%", "${")) or text.isupper():
        return text

    # Find all placeholders in the text
    placeholders = re.findall(placeholder_pattern, text)

    if not placeholders:
        # No placeholders, translate directly
        return _translate_simple_text(text, api_key)

    # Extract placeholders and replace them with temporary markers
    placeholder_map = {}
    temp_text = text
    for i, placeholder in enumerate(placeholders):
        marker = f"__PLACEHOLDER_{i}__"
        placeholder_map[marker] = placeholder
        temp_text = temp_text.replace(placeholder, marker, 1)

    # Translate the text with placeholders removed
    translated_temp = _translate_simple_text(temp_text, api_key)

    # Restore the original placeholders
    translated_text = translated_temp
    for marker, placeholder in placeholder_map.items():
        translated_text = translated_text.replace(marker, placeholder)

    return translated_text


async def async_translate_text(text: str, api_key: str) -> str:
    """异步翻译文本，保留占位符."""
    if not text or len(text.strip()) < 2:
        return text

    # Skip placeholders and code - use regex to find placeholder patterns
    # Pattern to match {placeholder}, %placeholder, ${placeholder}, etc.
    placeholder_pattern = r'\{[^}]+\}|%\w+|\$\{[^}]+\}'

    # Check if text is primarily a placeholder
    if re.fullmatch(placeholder_pattern, text.strip()):
        return text

    # Check if text starts with placeholder patterns
    if text.startswith(("{", "%", "${")) or text.isupper():
        return text

    # Find all placeholders in the text
    placeholders = re.findall(placeholder_pattern, text)

    if not placeholders:
        # No placeholders, translate directly
        return await _async_translate_simple_text(text, api_key)

    # Extract placeholders and replace them with temporary markers
    placeholder_map = {}
    temp_text = text
    for i, placeholder in enumerate(placeholders):
        marker = f"__PLACEHOLDER_{i}__"
        placeholder_map[marker] = placeholder
        temp_text = temp_text.replace(placeholder, marker, 1)

    # Translate the text with placeholders removed
    translated_temp = await _async_translate_simple_text(temp_text, api_key)

    # Restore the original placeholders
    translated_text = translated_temp
    for marker, placeholder in placeholder_map.items():
        translated_text = translated_text.replace(marker, placeholder)

    return translated_text


async def async_translate_json_values(data: any, api_key: str) -> any:
    """异步递归翻译JSON值."""
    if isinstance(data, dict):
        return {key: await async_translate_json_values(value, api_key) for key, value in data.items()}
    elif isinstance(data, list):
        return [await async_translate_json_values(item, api_key) for item in data]
    elif isinstance(data, str) and data.strip():
        # Translate strings
        return await async_translate_text(data, api_key)
    else:
        return data


async def _async_translate_simple_text(text: str, api_key: str) -> str:
    """异步翻译函数，用于不包含占位符的文本."""
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "glm-4-flash-250414",
        "messages": [
            {
                "role": "system",
                "content": "Translate English to Chinese. Return only the translation, no explanation."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "temperature": 0.3,
        "max_tokens": 2048
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response.raise_for_status()
                result = await response.json()
                translated = result["choices"][0]["message"]["content"].strip()

                _LOGGER.debug(f"Translated: {text} -> {translated}")
                return translated

    except aiohttp.ClientError as e:
        _LOGGER.error(f"Translation network error for '{text}': {e}")
        return text  # Return original on failure
    except (KeyError, IndexError, ValueError) as e:
        _LOGGER.error(f"Translation response parsing error for '{text}': {e}")
        return text
    except Exception as e:
        _LOGGER.error(f"Translation failed for '{text}': {e}")
        return text  # Return original on failure


def _translate_simple_text(text: str, api_key: str) -> str:
    """同步翻译函数（保留用于向后兼容，将在未来版本移除）.

    警告：此函数使用同步HTTP调用，建议使用 _async_translate_simple_text 替代。
    此函数仅为向后兼容而保留。
    """
    import asyncio
    try:
        # 尝试获取运行中的事件循环
        loop = asyncio.get_running_loop()
        # 如果在异步上下文中，应该调用异步版本
        _LOGGER.warning("_translate_simple_text called in async context, use _async_translate_simple_text instead")
    except RuntimeError:
        pass  # 没有运行中的事件循环，这是同步上下文

    # 回退到同步实现（仅用于兼容）
    import requests
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "glm-4-flash-250414",
        "messages": [
            {
                "role": "system",
                "content": "Translate English to Chinese. Return only the translation, no explanation."
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "temperature": 0.3,
        "max_tokens": 2048
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        translated = result["choices"][0]["message"]["content"].strip()

        _LOGGER.debug(f"Translated: {text} -> {translated}")
        return translated

    except Exception as e:
        _LOGGER.error(f"Translation failed for '{text}': {e}")
        return text  # Return original on failure


def translate_all_blueprints(api_key: str, retranslate: bool = False,
                             target_blueprint: str = "", list_blueprints: bool = False) -> dict:
    """Translate or list blueprints in the standard Home Assistant blueprints directory."""
    # Use standard Home Assistant blueprints directory
    blueprints_path = "/config/blueprints"
    base_path = Path(blueprints_path)

    if not base_path.exists() or not base_path.is_dir():
        return {
            "translated": 0,
            "skipped": 0,
            "error": f"Blueprints directory not found: {blueprints_path}"
        }

    _LOGGER.info(f"Scanning blueprints in: {base_path}")

    # 如果是仅列出模式，扫描所有blueprints并返回信息
    if list_blueprints:
        all_blueprints = []
        available_translations = []  # 已汉化的blueprints

        # 递归查找所有YAML文件
        for yaml_file in base_path.rglob("*.yaml"):
            blueprint_info = {
                "path": str(yaml_file.relative_to(base_path)),
                "has_translation": False,
                "name": ""
            }

            # 尝试读取blueprint名称并检查是否已汉化
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    blueprint_data = yaml.safe_load(f)
                    if blueprint_data and 'blueprint' in blueprint_data:
                        blueprint_info["name"] = blueprint_data['blueprint'].get('name', '')

                        # 检查是否包含中文字符（简单判断是否已汉化）
                        content_str = str(blueprint_data)
                        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in content_str)
                        if has_chinese:
                            blueprint_info["has_translation"] = True
                            available_translations.append(str(yaml_file.relative_to(base_path)))
            except Exception:
                pass

            all_blueprints.append(blueprint_info)

        _LOGGER.info(f"Found {len(all_blueprints)} blueprints, {len(available_translations)} have translations")

        return {
            "mode": "list_only",
            "total_blueprints": len(all_blueprints),
            "available_translations": len(available_translations),
            "all_blueprints": all_blueprints,
            "blueprints_with_translations": available_translations,
            "target_blueprint": target_blueprint
        }

    # 翻译模式
    translated = 0
    skipped = 0
    translated_blueprints = []  # 记录具体翻译的blueprints
    skipped_blueprints = []     # 记录跳过的blueprints

    # 递归查找所有YAML文件
    yaml_files = list(base_path.rglob("*.yaml"))

    # 如果指定了目标blueprint，只处理该文件
    if target_blueprint:
        target_files = [f for f in yaml_files if f.name == target_blueprint or f.name == f"{target_blueprint}.yaml"]
        if not target_files:
            return {
                "translated": 0,
                "skipped": 0,
                "error": f"Target blueprint not found: {target_blueprint}"
            }
        yaml_files = target_files
        _LOGGER.info(f"Processing specific blueprint: {target_blueprint}")
    else:
        _LOGGER.info(f"Processing all blueprints ({len(yaml_files)} found)")

    for yaml_file in yaml_files:
        try:
            # 检查是否已经汉化（包含中文字符）
            # 蓝图汉化默认跳过已汉化的文件，除非用户选择重新汉化
            if not retranslate:
                try:
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        content_str = f.read()
                        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in content_str)
                        if has_chinese:
                            result = "skipped (already translated)"
                            skipped += 1
                            skipped_blueprints.append(str(yaml_file.relative_to(base_path)))
                            _LOGGER.info(f"- Skipped {yaml_file.relative_to(base_path)} (already translated)")
                            continue
                except Exception:
                    pass

            # 翻译文件（或重新汉化）
            result = translate_blueprint_file(yaml_file, api_key)
            if result == "translated":
                translated += 1
                translated_blueprints.append(str(yaml_file.relative_to(base_path)))
                _LOGGER.info(f"✓ Successfully translated {yaml_file.relative_to(base_path)}")
            else:
                skipped += 1
                skipped_blueprints.append(str(yaml_file.relative_to(base_path)))
                _LOGGER.info(f"- Skipped {yaml_file.relative_to(base_path)} ({result})")
        except Exception as e:
            _LOGGER.error(f"Error processing {yaml_file}: {e}")
            skipped += 1
            skipped_blueprints.append(str(yaml_file.relative_to(base_path)))

    return {
        "mode": "translation",
        "translated": translated,
        "skipped": skipped,
        "translated_blueprints": translated_blueprints,
        "skipped_blueprints": skipped_blueprints,
        "target_blueprint": target_blueprint
    }


def translate_blueprint_file(yaml_file: Path, api_key: str) -> str:
    """Translate a single blueprint YAML file in-place."""
    # Always translate the original file directly
    _LOGGER.info(f"Translating {yaml_file.name}")

    try:
        # Load original YAML with custom constructor for Home Assistant tags
        def home_assistant_constructor(loader, node):
            if node.tag == '!input':
                return f"!{loader.construct_scalar(node)}"
            else:
                return loader.construct_scalar(node)

        yaml.SafeLoader.add_constructor('!input', home_assistant_constructor)
        yaml.SafeLoader.add_constructor('!secret', home_assistant_constructor)
        yaml.SafeLoader.add_constructor('!include', home_assistant_constructor)

        with open(yaml_file, 'r', encoding='utf-8') as f:
            blueprint_data = yaml.safe_load(f)

        if not blueprint_data or 'blueprint' not in blueprint_data:
            return "skipped (not a valid blueprint)"

        # Translate the blueprint metadata in-place
        blueprint_section = blueprint_data.get('blueprint', {})

        # Translate name and description
        if 'name' in blueprint_section and isinstance(blueprint_section['name'], str):
            blueprint_section['name'] = translate_text(blueprint_section['name'], api_key)

        if 'description' in blueprint_section and isinstance(blueprint_section['description'], str):
            blueprint_section['description'] = translate_text(blueprint_section['description'], api_key)

        # Translate input fields
        if 'input' in blueprint_section and isinstance(blueprint_section['input'], dict):
            translate_blueprint_inputs(blueprint_section['input'], api_key)

        # Translate variables fields
        if 'variables' in blueprint_section and isinstance(blueprint_section['variables'], dict):
            translate_blueprint_variables(blueprint_section['variables'], api_key)

        # Update the blueprint section
        blueprint_data['blueprint'] = blueprint_section

        # Translate description fields in action, trigger, and condition sections
        for section in ['action', 'trigger', 'condition']:
            if section in blueprint_data and isinstance(blueprint_data[section], list):
                for item in blueprint_data[section]:
                    if isinstance(item, dict):
                        translate_blueprint_section_descriptions(item, api_key)

        # Translate mode section
        if 'mode' in blueprint_data and isinstance(blueprint_data['mode'], dict):
            translate_blueprint_section_descriptions(blueprint_data['mode'], api_key)

        # Translate trace section
        if 'trace' in blueprint_data and isinstance(blueprint_data['trace'], dict):
            translate_blueprint_section_descriptions(blueprint_data['trace'], api_key)

        # Save back to original file with custom dumper for Home Assistant tags
        class HomeAssistantDumper(yaml.SafeDumper):
            def represent_scalar(self, tag, value, style=None):
                if isinstance(value, str) and value.startswith('!input'):
                    # Handle Home Assistant input tags
                    return super().represent_scalar('tag:yaml.org,2002:str', value, style)
                return super().represent_scalar(tag, value, style)

        # Save the translated content back to the original file
        with open(yaml_file, 'w', encoding='utf-8') as f:
            yaml.dump(
                blueprint_data,
                f,
                Dumper=HomeAssistantDumper,
                default_flow_style=False,
                allow_unicode=True,
                indent=2)

        _LOGGER.info(f"Successfully translated {yaml_file.name}")
        return "translated"

    except Exception as e:
        _LOGGER.error(f"Failed to translate {yaml_file.name}: {e}")
        return "error"


def translate_blueprint_inputs(inputs: dict, api_key: str) -> None:
    """Translate input fields in a blueprint while preserving technical parameters."""
    for input_key, input_config in inputs.items():
        if not isinstance(input_config, dict):
            continue

        # Translate name and description at this level
        if 'name' in input_config and isinstance(input_config['name'], str):
            input_config['name'] = translate_text(input_config['name'], api_key)

        if 'description' in input_config and isinstance(input_config['description'], str):
            input_config['description'] = translate_text(input_config['description'], api_key)

        # Translate selector fields at this level
        if 'selector' in input_config and isinstance(input_config['selector'], dict):
            translate_blueprint_selectors(input_config['selector'], api_key)

        # 递归处理嵌套的input字段（这是关键修复！）
        if 'input' in input_config and isinstance(input_config['input'], dict):
            translate_blueprint_inputs(input_config['input'], api_key)

        # Do not translate default values if they look like technical parameters
        if 'default' in input_config:
            default_val = input_config['default']
            # Only translate if it's a descriptive string and not a technical parameter
            if (isinstance(default_val, str) and
                not default_val.startswith('{{') and
                not default_val.isupper() and
                not any(char in default_val for char in ['.', '_', '-']) and
                    len(default_val.split()) > 1):
                input_config['default'] = translate_text(default_val, api_key)


def translate_blueprint_variables(variables: dict, api_key: str) -> None:
    """Translate variable descriptions in a blueprint while preserving values."""
    for var_key, var_config in variables.items():
        if isinstance(var_config, dict):
            # Translate name and description if present
            if 'name' in var_config and isinstance(var_config['name'], str):
                var_config['name'] = translate_text(var_config['name'], api_key)

            if 'description' in var_config and isinstance(var_config['description'], str):
                var_config['description'] = translate_text(var_config['description'], api_key)

            # Translate selector fields
            if 'selector' in var_config and isinstance(var_config['selector'], dict):
                translate_blueprint_selectors(var_config['selector'], api_key)
        elif isinstance(var_config, str):
            # Simple string variable, only translate if it's descriptive
            if (len(var_config.split()) > 1 and
                not var_config.startswith('{{') and
                not var_config.startswith('!') and
                    not var_config.isupper()):
                variables[var_key] = translate_text(var_config, api_key)


def translate_blueprint_selectors(selector: dict, api_key: str) -> None:
    """Translate selector fields in a blueprint."""
    for selector_type, config in selector.items():
        if isinstance(config, dict):
            # Translate common selector fields
            for field in ['label', 'description']:
                if field in config and isinstance(config[field], str):
                    config[field] = translate_text(config[field], api_key)

            # Translate options if present
            if 'options' in config and isinstance(config['options'], dict):
                for option_key, option_value in config['options'].items():
                    if isinstance(option_value, str) and not option_value.startswith('{{'):
                        config['options'][option_key] = translate_text(option_value, api_key)


def translate_blueprint_section_descriptions(item: dict, api_key: str) -> None:
    """Translate description fields in blueprint sections."""
    # Translate description field if present
    if 'description' in item and isinstance(item['description'], str):
        item['description'] = translate_text(item['description'], api_key)

    # Translate alias if present
    if 'alias' in item and isinstance(item['alias'], str):
        item['alias'] = translate_text(item['alias'], api_key)

    # Translate mode name in mode section
    if 'mode' in item and isinstance(item['mode'], str):
        item['mode'] = translate_text(item['mode'], api_key)

    # Recursively translate nested structures
    for key, value in item.items():
        if isinstance(value, dict):
            translate_blueprint_section_descriptions(value, api_key)
        elif isinstance(value, list):
            for list_item in value:
                if isinstance(list_item, dict):
                    translate_blueprint_section_descriptions(list_item, api_key)


# ==================== 异步翻译函数 ====================
# 以下函数使用异步HTTP客户端，避免阻塞事件循环

async def _async_translate_blueprint_inputs(inputs: dict, api_key: str) -> None:
    """异步递归翻译blueprint的input字段."""
    for key, value in inputs.items():
        if isinstance(value, dict):
            if 'name' in value and isinstance(value['name'], str):
                value['name'] = await async_translate_text(value['name'], api_key)
            if 'description' in value and isinstance(value['description'], str):
                value['description'] = await async_translate_text(value['description'], api_key)
            if 'default' in value and isinstance(value['default'], str) and len(value['default']) > 2:
                value['default'] = await async_translate_text(value['default'], api_key)

            # Translate selector options
            if 'selector' in value and isinstance(value['selector'], dict):
                await _async_translate_blueprint_selectors(value['selector'], api_key)
        elif isinstance(value, str) and len(value) > 2:
            inputs[key] = await async_translate_text(value, api_key)


async def _async_translate_blueprint_variables(variables: dict, api_key: str) -> None:
    """异步递归翻译blueprint的variables字段."""
    for key, value in variables.items():
        if isinstance(value, str) and len(value) > 2:
            variables[key] = await async_translate_text(value, api_key)


async def _async_translate_blueprint_selectors(selector: dict, api_key: str) -> None:
    """异步递归翻译blueprint的selector字段."""
    if 'select' in selector and isinstance(selector['select'], dict):
        options = selector['select'].get('options')
        if isinstance(options, list):
            for i, option in enumerate(options):
                if isinstance(option, str) and len(option) > 2:
                    options[i] = await async_translate_text(option, api_key)
        elif isinstance(options, dict):
            for key, value in options.items():
                if isinstance(value, str) and len(value) > 2:
                    options[key] = await async_translate_text(value, api_key)


async def _async_translate_blueprint_section_descriptions(item: dict, api_key: str) -> None:
    """异步递归翻译blueprint各section中的description字段."""
    # Translate description
    if 'description' in item and isinstance(item['description'], str):
        item['description'] = await async_translate_text(item['description'], api_key)

    # Translate alias in choose
    if 'alias' in item and isinstance(item['alias'], str):
        item['alias'] = await async_translate_text(item['alias'], api_key)

    # Translate mode name in mode section
    if 'mode' in item and isinstance(item['mode'], str):
        item['mode'] = await async_translate_text(item['mode'], api_key)

    # Recursively translate nested structures
    for key, value in item.items():
        if isinstance(value, dict):
            await _async_translate_blueprint_section_descriptions(value, api_key)
        elif isinstance(value, list):
            for list_item in value:
                if isinstance(list_item, dict):
                    await _async_translate_blueprint_section_descriptions(list_item, api_key)


async def async_translate_blueprint_file(yaml_file: Path, api_key: str) -> str:
    """异步翻译单个blueprint YAML文件."""
    _LOGGER.info(f"Translating {yaml_file.name} (async)")

    try:
        # Load original YAML with custom constructor for Home Assistant tags
        def home_assistant_constructor(loader, node):
            if node.tag == '!input':
                return f"!{loader.construct_scalar(node)}"
            else:
                return loader.construct_scalar(node)

        yaml.SafeLoader.add_constructor('!input', home_assistant_constructor)
        yaml.SafeLoader.add_constructor('!secret', home_assistant_constructor)
        yaml.SafeLoader.add_constructor('!include', home_assistant_constructor)

        # 使用 asyncio.to_thread 在单独的线程中读取文件
        import asyncio
        with open(yaml_file, 'r', encoding='utf-8') as f:
            content = await asyncio.to_thread(f.read())
            blueprint_data = yaml.safe_load(content)

        if not blueprint_data or 'blueprint' not in blueprint_data:
            return "skipped (not a valid blueprint)"

        # Translate the blueprint metadata in-place
        blueprint_section = blueprint_data.get('blueprint', {})

        # Translate name and description
        if 'name' in blueprint_section and isinstance(blueprint_section['name'], str):
            blueprint_section['name'] = await async_translate_text(blueprint_section['name'], api_key)

        if 'description' in blueprint_section and isinstance(blueprint_section['description'], str):
            blueprint_section['description'] = await async_translate_text(blueprint_section['description'], api_key)

        # Translate input fields
        if 'input' in blueprint_section and isinstance(blueprint_section['input'], dict):
            await _async_translate_blueprint_inputs(blueprint_section['input'], api_key)

        # Translate variables fields
        if 'variables' in blueprint_section and isinstance(blueprint_section['variables'], dict):
            await _async_translate_blueprint_variables(blueprint_section['variables'], api_key)

        # Update the blueprint section
        blueprint_data['blueprint'] = blueprint_section

        # Translate description fields in action, trigger, and condition sections
        for section in ['action', 'trigger', 'condition']:
            if section in blueprint_data and isinstance(blueprint_data[section], list):
                for item in blueprint_data[section]:
                    if isinstance(item, dict):
                        await _async_translate_blueprint_section_descriptions(item, api_key)

        # Translate mode section
        if 'mode' in blueprint_data and isinstance(blueprint_data['mode'], dict):
            await _async_translate_blueprint_section_descriptions(blueprint_data['mode'], api_key)

        # Translate trace section
        if 'trace' in blueprint_data and isinstance(blueprint_data['trace'], dict):
            await _async_translate_blueprint_section_descriptions(blueprint_data['trace'], api_key)

        # Save back to original file with custom dumper for Home Assistant tags
        class HomeAssistantDumper(yaml.SafeDumper):
            def represent_scalar(self, tag, value, style=None):
                if isinstance(value, str) and value.startswith('!input'):
                    # Handle Home Assistant input tags
                    return self.represent_scalar('tag:yaml.org,2002:str', value, style)
                return super().represent_scalar(tag, value, style)

        # 使用 asyncio.to_thread 在单独的线程中写入文件
        output = yaml.dump(blueprint_data, allow_unicode=True, Dumper=HomeAssistantDumper, sort_keys=False)
        await asyncio.to_thread(yaml_file.write_text, output, encoding='utf-8')

        return "translated"

    except Exception as e:
        _LOGGER.error(f"Error translating blueprint {yaml_file}: {e}")
        return f"skipped (error: {e})"


async def async_translate_all_blueprints(
    api_key: str,
    retranslate: bool = False,
    target_blueprint: str = "",
    list_blueprints: bool = False,
    blueprints_path: str = "/config/blueprints"
) -> dict:
    """异步翻译或列出blueprints目录中的文件."""
    base_path = Path(blueprints_path)

    if not base_path.exists() or not base_path.is_dir():
        return {
            "translated": 0,
            "skipped": 0,
            "error": f"Blueprints directory not found: {blueprints_path}"
        }

    _LOGGER.info(f"Scanning blueprints in: {base_path}")

    # 如果是仅列出模式，扫描所有blueprints并返回信息
    if list_blueprints:
        all_blueprints = []
        available_translations = []

        # 递归查找所有YAML文件
        import asyncio
        for yaml_file in base_path.rglob("*.yaml"):
            blueprint_info = {
                "path": str(yaml_file.relative_to(base_path)),
                "has_translation": False,
                "name": ""
            }

            # 尝试读取blueprint名称并检查是否已汉化
            try:
                content = await asyncio.to_thread(yaml_file.read_text, encoding='utf-8')
                blueprint_data = yaml.safe_load(content)
                if blueprint_data and 'blueprint' in blueprint_data:
                    blueprint_info["name"] = blueprint_data['blueprint'].get('name', '')

                    # 检查是否包含中文字符（简单判断是否已汉化）
                    content_str = str(blueprint_data)
                    has_chinese = any('\u4e00' <= char <= '\u9fff' for char in content_str)
                    if has_chinese:
                        blueprint_info["has_translation"] = True
                        available_translations.append(str(yaml_file.relative_to(base_path)))
            except Exception:
                pass

            all_blueprints.append(blueprint_info)

        _LOGGER.info(f"Found {len(all_blueprints)} blueprints, {len(available_translations)} have translations")

        return {
            "mode": "list_only",
            "total_blueprints": len(all_blueprints),
            "available_translations": len(available_translations),
            "all_blueprints": all_blueprints,
            "blueprints_with_translations": available_translations,
            "target_blueprint": target_blueprint
        }

    # 翻译模式
    translated = 0
    skipped = 0
    translated_blueprints = []
    skipped_blueprints = []

    # 递归查找所有YAML文件
    yaml_files = list(base_path.rglob("*.yaml"))

    # 如果指定了目标blueprint，只处理该文件
    if target_blueprint:
        target_files = [f for f in yaml_files if f.name == target_blueprint or f.name == f"{target_blueprint}.yaml"]
        if not target_files:
            return {
                "translated": 0,
                "skipped": 0,
                "error": f"Target blueprint not found: {target_blueprint}"
            }
        yaml_files = target_files
        _LOGGER.info(f"Processing specific blueprint: {target_blueprint}")
    else:
        _LOGGER.info(f"Processing all blueprints ({len(yaml_files)} found)")

    import asyncio
    for yaml_file in yaml_files:
        try:
            # 检查是否已经汉化（包含中文字符）
            if not retranslate:
                try:
                    content = await asyncio.to_thread(yaml_file.read_text, encoding='utf-8')
                    has_chinese = any('\u4e00' <= char <= '\u9fff' for char in content)
                    if has_chinese:
                        result = "skipped (already translated)"
                        skipped += 1
                        skipped_blueprints.append(str(yaml_file.relative_to(base_path)))
                        _LOGGER.info(f"- Skipped {yaml_file.relative_to(base_path)} (already translated)")
                        continue
                except Exception:
                    pass

            # 翻译文件（或重新汉化）
            result = await async_translate_blueprint_file(yaml_file, api_key)
            if result == "translated":
                translated += 1
                translated_blueprints.append(str(yaml_file.relative_to(base_path)))
                _LOGGER.info(f"✓ Successfully translated {yaml_file.relative_to(base_path)}")
            else:
                skipped += 1
                skipped_blueprints.append(str(yaml_file.relative_to(base_path)))
                _LOGGER.info(f"- Skipped {yaml_file.relative_to(base_path)} ({result})")
        except Exception as e:
            _LOGGER.error(f"Error processing {yaml_file}: {e}")
            skipped += 1
            skipped_blueprints.append(str(yaml_file.relative_to(base_path)))

    return {
        "mode": "translation",
        "translated": translated,
        "skipped": skipped,
        "translated_blueprints": translated_blueprints,
        "skipped_blueprints": skipped_blueprints,
        "target_blueprint": target_blueprint
    }


async def async_translate_component(
    component_dir: Path,
    component_name: str,
    api_key: str,
    force_translation: bool = False
) -> dict:
    """异步翻译单个组件目录中的所有JSON文件."""
    strings_files = {
        "strings.json": component_dir / "strings.json",
    }

    # 检查是否有 translations 子目录
    translations_dir = component_dir / "translations"
    if translations_dir.exists() and translations_dir.is_dir():
        for lang_file in translations_dir.glob("*.json"):
            strings_files[f"translations/{lang_file.name}"] = lang_file

    translated_files = []
    skipped_files = []

    for file_key, file_path in strings_files.items():
        if not file_path.exists():
            continue

        try:
            import asyncio
            content = await asyncio.to_thread(file_path.read_text, encoding='utf-8')
            data = json.loads(content)

            # 检查是否已汉化
            if not force_translation:
                content_str = json.dumps(data, ensure_ascii=False)
                has_chinese = any('\u4e00' <= char <= '\u9fff' for char in content_str)
                if has_chinese:
                    _LOGGER.info(f"  - {file_key}: already translated, skipping")
                    skipped_files.append(file_key)
                    continue

            # 异步翻译JSON值
            translated_data = await async_translate_json_values(data, api_key)

            # 写回文件
            output = json.dumps(translated_data, indent=2, ensure_ascii=False)
            await asyncio.to_thread(file_path.write_text, output, encoding='utf-8')

            _LOGGER.info(f"  ✓ {file_key}: translated")
            translated_files.append(file_key)

        except Exception as e:
            _LOGGER.error(f"  - {file_key}: error - {e}")
            skipped_files.append(file_key)

    return {
        "component": component_name,
        "translated": translated_files,
        "skipped": skipped_files
    }


async def async_translate_all_components(
    custom_components_path: str = "custom_components",
    api_key: str | None = None,
    force_translation: bool = False,
    target_component: str = "",
    list_components: bool = False
) -> dict:
    """异步翻译或列出已安装的集成."""
    base_path = Path(custom_components_path)

    if not base_path.exists() or not base_path.is_dir():
        return {
            "mode": "error",
            "error": f"Custom components directory not found: {custom_components_path}"
        }

    _LOGGER.info(f"Scanning components in: {base_path}")

    # 查找所有包含 strings.json 的组件
    component_dirs = []
    for item in base_path.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            strings_file = item / "strings.json"
            if strings_file.exists():
                component_dirs.append(item)

    if not component_dirs:
        return {
            "mode": "error",
            "error": "No components with strings.json found"
        }

    # 如果指定了目标组件，只处理该组件
    if target_component:
        filtered_dirs = [d for d in component_dirs if d.name == target_component]
        if not filtered_dirs:
            return {
                "mode": "error",
                "error": f"Target component not found: {target_component}"
            }
        component_dirs = filtered_dirs

    _LOGGER.info(f"Found {len(component_dirs)} components to process")

    # 如果是仅列出模式，返回组件列表
    if list_components:
        components_info = []
        for comp_dir in component_dirs:
            try:
                import asyncio
                strings_file = comp_dir / "strings.json"
                content = await asyncio.to_thread(strings_file.read_text, encoding='utf-8')
                data = json.loads(content)

                # 检查是否已汉化
                content_str = json.dumps(data, ensure_ascii=False)
                has_chinese = any('\u4e00' <= char <= '\u9fff' for char in content_str)

                components_info.append({
                    "name": comp_dir.name,
                    "has_translation": has_chinese
                })
            except Exception:
                components_info.append({
                    "name": comp_dir.name,
                    "has_translation": False,
                    "error": "Failed to read strings.json"
                })

        return {
            "mode": "list_only",
            "components": components_info,
            "total": len(components_info)
        }

    # 翻译模式
    results = []
    import asyncio
    for comp_dir in component_dirs:
        _LOGGER.info(f"Processing component: {comp_dir.name}")
        result = await async_translate_component(comp_dir, comp_dir.name, api_key, force_translation)
        results.append(result)

    # 汇总结果
    total_translated = sum(len(r.get("translated", [])) for r in results)
    total_skipped = sum(len(r.get("skipped", [])) for r in results)

    return {
        "mode": "translation",
        "results": results,
        "total_translated": total_translated,
        "total_skipped": total_skipped
    }
