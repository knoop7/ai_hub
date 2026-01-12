"""Blueprint translation services for AI Hub - 蓝图翻译功能.

本模块提供 Home Assistant 蓝图 (Blueprint) 的翻译服务。

主要函数:
- async_translate_blueprint_file: 异步翻译单个蓝图文件
- async_translate_all_blueprints: 异步翻译所有蓝图

翻译特性:
- 保护 Home Assistant 特殊语法 (!input, !secret, !include)
- 智能翻译 name, description 等用户界面文本
- 支持嵌套结构和复杂蓝图
- 原位翻译，不产生额外文件
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import yaml

from .translation import async_translate_text

_LOGGER = logging.getLogger(__name__)


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
            if 'selector' in value and isinstance(value['selector'], dict):
                await _async_translate_blueprint_selectors(value['selector'], api_key)
            if 'input' in value and isinstance(value['input'], dict):
                await _async_translate_blueprint_inputs(value['input'], api_key)
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
    if 'description' in item and isinstance(item['description'], str):
        item['description'] = await async_translate_text(item['description'], api_key)
    if 'alias' in item and isinstance(item['alias'], str):
        item['alias'] = await async_translate_text(item['alias'], api_key)
    if 'mode' in item and isinstance(item['mode'], str):
        item['mode'] = await async_translate_text(item['mode'], api_key)

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
        def home_assistant_constructor(loader, node):
            if node.tag == '!input':
                return f"!{loader.construct_scalar(node)}"
            return loader.construct_scalar(node)

        yaml.SafeLoader.add_constructor('!input', home_assistant_constructor)
        yaml.SafeLoader.add_constructor('!secret', home_assistant_constructor)
        yaml.SafeLoader.add_constructor('!include', home_assistant_constructor)

        content = await asyncio.to_thread(yaml_file.read_text, encoding='utf-8')
        blueprint_data = yaml.safe_load(content)

        if not blueprint_data or 'blueprint' not in blueprint_data:
            return "skipped (not a valid blueprint)"

        blueprint_section = blueprint_data.get('blueprint', {})

        if 'name' in blueprint_section and isinstance(blueprint_section['name'], str):
            blueprint_section['name'] = await async_translate_text(blueprint_section['name'], api_key)
        if 'description' in blueprint_section and isinstance(blueprint_section['description'], str):
            blueprint_section['description'] = await async_translate_text(blueprint_section['description'], api_key)
        if 'input' in blueprint_section and isinstance(blueprint_section['input'], dict):
            await _async_translate_blueprint_inputs(blueprint_section['input'], api_key)
        if 'variables' in blueprint_section and isinstance(blueprint_section['variables'], dict):
            await _async_translate_blueprint_variables(blueprint_section['variables'], api_key)

        blueprint_data['blueprint'] = blueprint_section

        for section in ['action', 'trigger', 'condition']:
            if section in blueprint_data and isinstance(blueprint_data[section], list):
                for item in blueprint_data[section]:
                    if isinstance(item, dict):
                        await _async_translate_blueprint_section_descriptions(item, api_key)

        if 'mode' in blueprint_data and isinstance(blueprint_data['mode'], dict):
            await _async_translate_blueprint_section_descriptions(blueprint_data['mode'], api_key)
        if 'trace' in blueprint_data and isinstance(blueprint_data['trace'], dict):
            await _async_translate_blueprint_section_descriptions(blueprint_data['trace'], api_key)

        class HomeAssistantDumper(yaml.SafeDumper):
            def represent_scalar(self, tag, value, style=None):
                if isinstance(value, str) and value.startswith('!input'):
                    return self.represent_scalar('tag:yaml.org,2002:str', value, style)
                return super().represent_scalar(tag, value, style)

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
        return {"translated": 0, "skipped": 0, "error": f"Blueprints directory not found: {blueprints_path}"}

    _LOGGER.info(f"Scanning blueprints in: {base_path}")

    if list_blueprints:
        all_blueprints = []
        available_translations = []

        for yaml_file in base_path.rglob("*.yaml"):
            blueprint_info = {"path": str(yaml_file.relative_to(base_path)), "has_translation": False, "name": ""}

            try:
                content = await asyncio.to_thread(yaml_file.read_text, encoding='utf-8')
                blueprint_data = yaml.safe_load(content)
                if blueprint_data and 'blueprint' in blueprint_data:
                    blueprint_info["name"] = blueprint_data['blueprint'].get('name', '')
                    has_chinese = any('\u4e00' <= char <= '\u9fff' for char in str(blueprint_data))
                    if has_chinese:
                        blueprint_info["has_translation"] = True
                        available_translations.append(str(yaml_file.relative_to(base_path)))
            except Exception:
                pass

            all_blueprints.append(blueprint_info)

        return {
            "mode": "list_only",
            "total_blueprints": len(all_blueprints),
            "available_translations": len(available_translations),
            "all_blueprints": all_blueprints,
            "blueprints_with_translations": available_translations,
            "target_blueprint": target_blueprint
        }

    translated = 0
    skipped = 0
    translated_blueprints = []
    skipped_blueprints = []

    yaml_files = list(base_path.rglob("*.yaml"))

    if target_blueprint:
        target_files = [f for f in yaml_files if f.name == target_blueprint or f.name == f"{target_blueprint}.yaml"]
        if not target_files:
            return {"translated": 0, "skipped": 0, "error": f"Target blueprint not found: {target_blueprint}"}
        yaml_files = target_files

    for yaml_file in yaml_files:
        try:
            if not retranslate:
                try:
                    content = await asyncio.to_thread(yaml_file.read_text, encoding='utf-8')
                    if any('\u4e00' <= char <= '\u9fff' for char in content):
                        skipped += 1
                        skipped_blueprints.append(str(yaml_file.relative_to(base_path)))
                        continue
                except Exception:
                    pass

            result = await async_translate_blueprint_file(yaml_file, api_key)
            if result == "translated":
                translated += 1
                translated_blueprints.append(str(yaml_file.relative_to(base_path)))
            else:
                skipped += 1
                skipped_blueprints.append(str(yaml_file.relative_to(base_path)))
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
