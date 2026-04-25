"""Strict local sentence matching helpers."""

from __future__ import annotations

import re
from typing import Any


def matches_sentence_template(handler: Any, text: str) -> bool:
    """Return whether text matches any configured local sentence template."""
    patterns = get_local_sentence_patterns(handler)
    if not patterns:
        return False

    normalized_text = re.sub(r'\s+', ' ', text.lower().strip()).strip()
    return any(pattern.fullmatch(normalized_text) for pattern in patterns)


def get_local_sentence_patterns(handler: Any) -> list[re.Pattern[str]]:
    """Compile local sentence templates into strict regex patterns once."""
    if handler._local_sentence_patterns is not None:
        return handler._local_sentence_patterns

    config = handler.config or {}
    templates = config.get('local_sentence_templates', [])
    if not isinstance(templates, list):
        handler._local_sentence_patterns = []
        return handler._local_sentence_patterns

    patterns: list[re.Pattern[str]] = []
    for template in templates:
        if not isinstance(template, str) or not template.strip():
            continue
        try:
            regex = template_to_regex(handler, template, config)
            patterns.append(re.compile(regex))
        except (ValueError, re.error):
            continue

    handler._local_sentence_patterns = patterns
    return handler._local_sentence_patterns


def template_to_regex(
    handler: Any,
    template: str,
    config: dict[str, Any],
    seen_tokens: set[str] | None = None,
) -> str:
    """Convert a sentence template into an anchored strict regex."""
    seen_tokens = set() if seen_tokens is None else set(seen_tokens)

    def _convert(fragment: str) -> str:
        parts: list[str] = []
        i = 0
        while i < len(fragment):
            char = fragment[i]
            if char == '[':
                end = find_matching(fragment, i, '[', ']')
                inner = _convert(fragment[i + 1:end])
                parts.append(f'(?:{inner})?')
                i = end + 1
                continue
            if char == '<':
                end = find_matching(fragment, i, '<', '>')
                token = fragment[i + 1:end].strip()
                parts.append(expand_template_token(handler, token, config, seen_tokens=seen_tokens))
                i = end + 1
                continue
            if char == '{':
                end = find_matching(fragment, i, '{', '}')
                token = fragment[i + 1:end].split(':', 1)[0].strip()
                parts.append(
                    expand_template_token(
                        handler,
                        token,
                        config,
                        fallback='.+?',
                        seen_tokens=seen_tokens,
                    )
                )
                i = end + 1
                continue
            if char.isspace():
                parts.append(r'\s*')
            elif char in '()|':
                parts.append(char)
            else:
                parts.append(re.escape(char))
            i += 1
        return ''.join(parts)

    body = _convert(template.strip())
    return rf'^\s*{body}[\s。！？?!.，,:：]*$'


def expand_template_token(
    handler: Any,
    token: str,
    config: dict[str, Any],
    fallback: str = '.+?',
    seen_tokens: set[str] | None = None,
) -> str:
    """Expand a rule/list token into regex."""
    seen_tokens = set() if seen_tokens is None else set(seen_tokens)
    normalized_token = token.strip()
    strict_slot_regex = resolve_strict_slot_regex(handler, normalized_token, config)
    if strict_slot_regex is not None:
        return strict_slot_regex

    expansion_rules = config.get('expansion_rules', {}) if isinstance(config, dict) else {}
    if normalized_token in expansion_rules and isinstance(expansion_rules[normalized_token], str):
        if normalized_token in seen_tokens:
            return fallback

        next_seen = set(seen_tokens)
        next_seen.add(normalized_token)
        return f'(?:{template_to_regex_fragment(handler, expansion_rules[normalized_token], config, next_seen)})'

    lists_config = config.get('lists', {}) if isinstance(config, dict) else {}
    list_config = lists_config.get(normalized_token)
    if isinstance(list_config, dict):
        values = list_config.get('values')
        if isinstance(values, list):
            options: list[str] = []
            for value in values:
                if isinstance(value, str):
                    options.append(re.escape(value.strip()))
                elif isinstance(value, dict) and isinstance(value.get('in'), str):
                    options.append(re.escape(value['in'].strip()))
            if options:
                return f'(?:{"|".join(options)})'

    return fallback


def resolve_strict_slot_regex(handler: Any, token: str, config: dict[str, Any]) -> str | None:
    """Resolve template slots to strict value lists instead of arbitrary text."""
    if not token:
        return None

    value_options = get_slot_values(handler, token, config)
    if not value_options:
        return None

    escaped = [re.escape(value) for value in sorted(value_options, key=len, reverse=True)]
    return f'(?:{"|".join(escaped)})'


def get_slot_values(handler: Any, token: str, config: dict[str, Any]) -> list[str]:
    """Return allowed concrete values for a template slot."""
    lists_config = config.get('lists', {}) if isinstance(config, dict) else {}
    values: list[str] = []
    seen: set[str] = set()

    def _append(value: str | None) -> None:
        if not isinstance(value, str):
            return
        normalized = value.strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        values.append(normalized)

    list_config = lists_config.get(token)
    if isinstance(list_config, dict):
        raw_values = list_config.get('values', [])
        if isinstance(raw_values, list):
            for item in raw_values:
                if isinstance(item, str):
                    _append(item)
                elif isinstance(item, dict):
                    _append(item.get('in'))

    if not values and looks_like_entity_name_slot(token):
        for list_name, list_config in lists_config.items():
            if not isinstance(list_name, str) or not list_name.endswith('_names'):
                continue
            if not isinstance(list_config, dict):
                continue
            raw_values = list_config.get('values', [])
            if not isinstance(raw_values, list):
                continue
            for item in raw_values:
                if isinstance(item, str):
                    _append(item)
                elif isinstance(item, dict):
                    _append(item.get('in'))

        try:
            for entity_id in handler.hass.states.async_entity_ids():
                state = handler.hass.states.get(entity_id)
                if state is None:
                    continue
                _append(getattr(state, 'name', None))
                attributes = getattr(state, 'attributes', {}) or {}
                _append(attributes.get('friendly_name'))
        except Exception:
            pass

    return values


def looks_like_entity_name_slot(token: str) -> bool:
    """Return whether a slot token is intended to capture an entity name."""
    normalized = token.strip().lower()
    return normalized == 'name' or normalized.endswith('_name')


def template_to_regex_fragment(
    handler: Any,
    fragment: str,
    config: dict[str, Any],
    seen_tokens: set[str] | None = None,
) -> str:
    """Convert a template fragment into a non-anchored regex."""
    regex = template_to_regex(handler, fragment, config, seen_tokens)
    prefix = '^\\s*'
    suffix = '[\\s。！？?!.，,:：]*$'
    if regex.startswith(prefix):
        regex = regex[len(prefix):]
    if regex.endswith(suffix):
        regex = regex[:-len(suffix)]
    return regex


def find_matching(text: str, start: int, opener: str, closer: str) -> int:
    """Find the matching closing delimiter."""
    depth = 0
    for index in range(start, len(text)):
        if text[index] == opener:
            depth += 1
        elif text[index] == closer:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f'Unmatched template delimiter: {opener}')
