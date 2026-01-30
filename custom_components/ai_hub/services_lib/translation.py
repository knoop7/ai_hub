"""Translation services for AI Hub - 组件翻译功能.

本模块提供 Home Assistant 自定义组件的翻译服务，使用 SiliconFlow AI 进行翻译。

主要函数:
- async_translate_text: 异步翻译单个文本
- async_translate_json_values: 异步递归翻译 JSON 值
- async_translate_component: 异步翻译单个组件
- async_translate_all_components: 异步翻译所有组件

翻译特性:
- 自动保留占位符 ({}, %s, ${} 等)
- 智能跳过纯占位符文本
- 支持批量处理和强制重新翻译
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import aiohttp

from ..const import AI_HUB_CHAT_URL, RECOMMENDED_CHAT_MODEL

_LOGGER = logging.getLogger(__name__)


async def async_translate_text(
    text: str,
    api_key: str,
    api_url: str | None = None,
    model: str | None = None
) -> str:
    """异步翻译文本，保留占位符."""
    if not text or len(text.strip()) < 2:
        return text

    placeholder_pattern = r'\{[^}]+\}|%\w+|\$\{[^}]+\}'

    if re.fullmatch(placeholder_pattern, text.strip()):
        return text

    if text.startswith(("{", "%", "${")) or text.isupper():
        return text

    placeholders = re.findall(placeholder_pattern, text)

    if not placeholders:
        return await _async_translate_simple_text(text, api_key, api_url, model)

    placeholder_map = {}
    temp_text = text
    for i, placeholder in enumerate(placeholders):
        marker = f"__PLACEHOLDER_{i}__"
        placeholder_map[marker] = placeholder
        temp_text = temp_text.replace(placeholder, marker, 1)

    translated_temp = await _async_translate_simple_text(temp_text, api_key, api_url, model)

    translated_text = translated_temp
    for marker, placeholder in placeholder_map.items():
        translated_text = translated_text.replace(marker, placeholder)

    return translated_text


async def async_translate_json_values(
    data,
    api_key: str,
    api_url: str | None = None,
    model: str | None = None
):
    """异步递归翻译JSON值."""
    if isinstance(data, dict):
        return {key: await async_translate_json_values(value, api_key, api_url, model) for key, value in data.items()}
    elif isinstance(data, list):
        return [await async_translate_json_values(item, api_key, api_url, model) for item in data]
    elif isinstance(data, str) and data.strip():
        return await async_translate_text(data, api_key, api_url, model)
    else:
        return data


async def _async_translate_simple_text(
    text: str,
    api_key: str,
    api_url: str | None = None,
    model: str | None = None
) -> str:
    """异步翻译函数."""
    # Use provided values or defaults
    url = api_url or AI_HUB_CHAT_URL
    chat_model = model or RECOMMENDED_CHAT_MODEL

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": chat_model,
        "messages": [
            {"role": "system", "content": "Translate English to Chinese. Return only the translation."},
            {"role": "user", "content": text}
        ],
        "temperature": 0.3,
        "max_tokens": 2048
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()
                result = await response.json()
                return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        _LOGGER.error(f"Translation failed for '{text}': {e}")
        return text


async def async_translate_component(
    component_dir: Path,
    component_name: str,
    api_key: str,
    force_translation: bool = False,
    api_url: str | None = None,
    model: str | None = None
) -> str:
    """异步翻译单个组件."""
    translations_dir = component_dir / "translations"
    en_file = translations_dir / "en.json"
    zh_file = translations_dir / "zh-Hans.json"

    if not translations_dir.exists() or not en_file.exists():
        return "skipped"

    if zh_file.exists() and not force_translation:
        return "skipped"

    try:
        with open(en_file, 'r', encoding='utf-8') as f:
            en_data = json.load(f)

        zh_data = await async_translate_json_values(en_data, api_key, api_url, model)

        with open(zh_file, 'w', encoding='utf-8') as f:
            json.dump(zh_data, f, ensure_ascii=False, indent=2)

        _LOGGER.info(f"Successfully translated {component_name}")
        return "translated"
    except Exception as e:
        _LOGGER.error(f"Failed to translate {component_name}: {e}")
        return "error"


async def async_translate_all_components(
    custom_components_path: str = "custom_components",
    api_key: str | None = None,
    force_translation: bool = False,
    target_component: str = "",
    list_components: bool = False,
    api_url: str | None = None,
    model: str | None = None
) -> dict:
    """异步翻译所有组件."""
    base_path = None
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
        return {"error": f"Custom components directory not found: {custom_components_path}"}

    if list_components:
        all_components = []
        available_translations = []

        for component_dir in base_path.iterdir():
            if not component_dir.is_dir() or component_dir.name in ["ai_hub", "translation_localizer"]:
                continue

            all_components.append(component_dir.name)
            zh_file = component_dir / "translations" / "zh-Hans.json"
            if zh_file.exists():
                available_translations.append(component_dir.name)

        return {
            "mode": "list_only",
            "total_components": len(all_components),
            "all_components": sorted(all_components),
            "components_with_translations": sorted(available_translations),
        }

    translated = 0
    skipped = 0
    translated_components = []
    skipped_components = []

    if target_component:
        target_dir = base_path / target_component
        if not target_dir.exists():
            return {"error": f"Target component not found: {target_component}"}
        component_dirs = [target_dir]
    else:
        component_dirs = [
            d for d in base_path.iterdir()
            if d.is_dir() and d.name not in ["ai_hub", "translation_localizer"]
        ]

    for component_dir in component_dirs:
        result = await async_translate_component(
            component_dir, component_dir.name, api_key, force_translation, api_url, model
        )
        if result == "translated":
            translated += 1
            translated_components.append(component_dir.name)
        else:
            skipped += 1
            skipped_components.append(component_dir.name)

    return {
        "mode": "translate",
        "translated": translated,
        "skipped": skipped,
        "translated_components": translated_components,
        "skipped_components": skipped_components,
    }
