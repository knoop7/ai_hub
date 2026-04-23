"""Markdown filter for cleaning AI-generated content.

This module provides functions to remove markdown formatting from AI responses
while preserving the actual content.
"""

import re


# Patterns that should preserve content (capture groups)
_CAPTURE_PATTERNS = [
    re.compile(r'\*\*([^*\n]*)\*\*'),      # Bold: keep content
    re.compile(r'\*([^*\n]*)\*'),          # Italic: keep content
    re.compile(r'__([^_\n]*)__'),          # Bold: keep content
    re.compile(r'_([^_\n]*)_'),            # Italic: keep content
    re.compile(r'~~([^~\n]*)~~'),          # Strikethrough: keep content
    re.compile(r'`([^`\n]*)`'),            # Inline code: keep content
]

# Patterns that should be completely removed
_REMOVE_PATTERNS = [
    re.compile(r'^#{1,6}\s+', re.MULTILINE),         # Headers: strip marks, keep text
    # List removal disabled - preserves AI-generated lists
    re.compile(r'^\s*>\s+', re.MULTILINE),           # Blockquotes: strip >, keep text
    re.compile(r'```[a-zA-Z0-9_-]*', re.MULTILINE),  # Code blocks start
    re.compile(r'```\s*$', re.MULTILINE),            # Code blocks end
    re.compile(r'^\|[^\n]*\|$', re.MULTILINE),       # Tables
    re.compile(r'^\|[\s-]*\|[\s-]*\|$', re.MULTILINE),  # Table separators
    re.compile(r'^-{3,}$|^_{3,}$|^\*{3,}$', re.MULTILINE),  # Horizontal rules
    re.compile(r'\[\^[^\]]*\]'),                     # Footnotes
    re.compile(r'^\[\^[^\]]*\]:.*$', re.MULTILINE),  # Footnote definitions
    # HTML tags removal disabled - breaks claw_assistant content
    re.compile(r'^\s*$\n^\s*$', re.MULTILINE),       # Empty lines
    re.compile(r'^`[a-zA-Z0-9_-]*$', re.MULTILINE)   # Language identifiers
]


def _apply_markdown_filters(content: str) -> str:
    """Apply all markdown filter patterns to content.

    Args:
        content: The content to filter

    Returns:
        Filtered content with markdown removed but content preserved
    """
    # Apply patterns that preserve content (capture groups)
    for pattern in _CAPTURE_PATTERNS:
        content = pattern.sub(r'\1', content)

    # Apply patterns that remove entirely
    for pattern in _REMOVE_PATTERNS:
        content = pattern.sub('', content)

    # Normalize line breaks
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content


def filter_markdown_content(content: str) -> str:
    """Filter markdown formatting from content, strip whitespace.

    This is the standard filter for complete responses.

    Args:
        content: The content to filter

    Returns:
        Filtered content with markdown removed and whitespace stripped
    """
    if not content:
        return ""

    # Apply markdown filters (preserve emojis for claw_assistant display)
    content = _apply_markdown_filters(content)

    # Remove leading/trailing whitespace per line
    content = re.sub(r'^\s+$', '', content, flags=re.MULTILINE)

    return content.strip()


def filter_markdown_streaming(content: str) -> str:
    """Filter markdown formatting for streaming responses.

    This version preserves all spaces for chunk-by-chunk streaming.

    Args:
        content: The content to filter

    Returns:
        Filtered content with markdown removed, spaces preserved
    """
    if not content:
        return ""

    # Apply markdown filters (preserve emojis for claw_assistant display)
    content = _apply_markdown_filters(content)

    # Don't strip to preserve chunk spacing

    return content
