"""Shared helpers for batch translation-style service workflows."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, TypeVar

ItemT = TypeVar("ItemT")


def select_named_items(
    items: Iterable[ItemT],
    target_name: str,
    *,
    matcher: Callable[[ItemT, str], bool],
    not_found_error: str,
) -> tuple[list[ItemT] | None, dict[str, Any] | None]:
    """Filter items by target name, returning a service-style error payload if missing."""
    if not target_name:
        return list(items), None

    selected = [item for item in items if matcher(item, target_name)]
    if selected:
        return selected, None

    return None, {"error": not_found_error}


def build_list_result(
    *,
    mode: str,
    total_key: str,
    all_items_key: str,
    all_items: list[Any],
    translated_key: str,
    translated_items: list[Any],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized list-mode result payload."""
    result = {
        "mode": mode,
        total_key: len(all_items),
        all_items_key: all_items,
        translated_key: translated_items,
    }
    if extra:
        result.update(extra)
    return result


def build_batch_result(
    *,
    mode: str,
    translated_items: list[str],
    skipped_items: list[str],
    translated_key: str,
    skipped_key: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized batch processing result payload."""
    result = {
        "mode": mode,
        "translated": len(translated_items),
        "skipped": len(skipped_items),
        translated_key: translated_items,
        skipped_key: skipped_items,
    }
    if extra:
        result.update(extra)
    return result
