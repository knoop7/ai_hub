"""Tests for diagnostics helpers."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.ai_hub.consts import DOMAIN
from custom_components.ai_hub.diagnostics import _get_statistics_diagnostics


class TestStatisticsDiagnostics:
    """Tests for runtime statistics diagnostics."""

    def test_returns_minimal_runtime_info_without_entry_data(self):
        hass = SimpleNamespace(data={DOMAIN: {"other": {}}})
        entry = SimpleNamespace(entry_id="entry-1")

        stats = _get_statistics_diagnostics(hass, entry)

        assert stats == {
            "integration_data_available": True,
            "entry_has_runtime_data": False,
        }

    def test_includes_cached_stats_when_available(self):
        hass = SimpleNamespace(
            data={
                DOMAIN: {
                    "entry-1": {
                        "stats": {"total_calls": 3},
                    }
                }
            }
        )
        entry = SimpleNamespace(entry_id="entry-1")

        stats = _get_statistics_diagnostics(hass, entry)

        assert stats["integration_data_available"] is True
        assert stats["entry_has_runtime_data"] is True
        assert stats["cached_stats"] == {"total_calls": 3}

    def test_handles_missing_domain_data(self):
        hass = SimpleNamespace(data={})
        entry = SimpleNamespace(entry_id="entry-1")

        stats = _get_statistics_diagnostics(hass, entry)

        assert stats == {
            "integration_data_available": False,
            "entry_has_runtime_data": False,
        }
