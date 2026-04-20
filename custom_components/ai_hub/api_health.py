"""Shared API health probing helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import aiohttp


async def async_probe_url(
    session: aiohttp.ClientSession,
    url: str,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Probe a URL and return normalized latency/error metadata."""
    checked_at = datetime.now().isoformat()
    try:
        start_time = datetime.now()
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=timeout_seconds),
        ) as response:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "reachable": True,
                "http_status": response.status,
                "latency_ms": round(latency, 2),
                "checked_at": checked_at,
            }
    except aiohttp.ClientError as err:
        return {
            "reachable": False,
            "error_type": "client",
            "error": str(err),
            "checked_at": checked_at,
        }
    except asyncio.TimeoutError:
        return {
            "reachable": False,
            "error_type": "timeout",
            "error": f"Timeout after {timeout_seconds}s",
            "checked_at": checked_at,
        }
    except Exception as err:
        return {
            "reachable": False,
            "error_type": "error",
            "error": str(err),
            "checked_at": checked_at,
        }
