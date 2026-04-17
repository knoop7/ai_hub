"""Serialization helpers shared across AI Hub."""

from __future__ import annotations

import json
from typing import Any


def ensure_string(value: Any) -> str:
    """Ensure a value is safe to send as text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
