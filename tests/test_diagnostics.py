"""Tests for the diagnostics module."""

from __future__ import annotations

from datetime import datetime

import pytest

from custom_components.ai_hub.diagnostics import (
    DiagnosticsCollector,
    get_diagnostics_collector,
)


class TestDiagnosticsCollector:
    """Tests for DiagnosticsCollector class."""

    def test_init(self):
        """Test collector initialization."""
        collector = DiagnosticsCollector()

        assert collector._api_calls == {}
        assert collector._errors == []
        assert isinstance(collector._start_time, datetime)

    def test_record_api_call(self):
        """Test recording API calls."""
        collector = DiagnosticsCollector()

        collector.record_api_call("chat", success=True, latency_ms=150)
        collector.record_api_call("chat", success=False, latency_ms=5000)

        assert len(collector._api_calls["chat"]) == 2
        assert collector._api_calls["chat"][0]["success"] is True
        assert collector._api_calls["chat"][1]["success"] is False

    def test_record_api_call_with_extra_data(self):
        """Test recording API calls with extra data."""
        collector = DiagnosticsCollector()

        collector.record_api_call(
            "stt",
            success=True,
            latency_ms=200,
            model="SenseVoice",
            file_size=1024,
        )

        record = collector._api_calls["stt"][0]
        assert record["model"] == "SenseVoice"
        assert record["file_size"] == 1024

    def test_record_api_call_limit(self):
        """Test that API call records are limited to 100."""
        collector = DiagnosticsCollector()

        for i in range(150):
            collector.record_api_call("test", success=True, latency_ms=i)

        assert len(collector._api_calls["test"]) == 100
        # Should keep the most recent 100
        assert collector._api_calls["test"][0]["latency_ms"] == 50

    def test_record_error(self):
        """Test recording errors."""
        collector = DiagnosticsCollector()

        collector.record_error("chat", "Timeout error")
        collector.record_error("stt", "API key invalid", status_code=401)

        assert len(collector._errors) == 2
        assert collector._errors[0]["context"] == "chat"
        assert collector._errors[1]["status_code"] == 401

    def test_record_error_limit(self):
        """Test that error records are limited to 50."""
        collector = DiagnosticsCollector()

        for i in range(75):
            collector.record_error("test", f"Error {i}")

        assert len(collector._errors) == 50
        # Should keep the most recent 50
        assert "Error 25" in collector._errors[0]["error"]

    def test_get_summary(self):
        """Test getting summary statistics."""
        collector = DiagnosticsCollector()

        # Record some data
        collector.record_api_call("chat", success=True, latency_ms=100)
        collector.record_api_call("chat", success=True, latency_ms=200)
        collector.record_api_call("chat", success=False, latency_ms=300)
        collector.record_error("chat", "Test error")

        summary = collector.get_summary()

        assert "uptime_seconds" in summary
        assert summary["uptime_seconds"] >= 0

        chat_stats = summary["api_summary"]["chat"]
        assert chat_stats["total_calls"] == 3
        assert chat_stats["successful_calls"] == 2
        assert chat_stats["success_rate"] == pytest.approx(66.67, abs=0.1)
        assert chat_stats["avg_latency_ms"] == 200.0
        assert chat_stats["min_latency_ms"] == 100.0
        assert chat_stats["max_latency_ms"] == 300.0

        assert summary["total_errors"] == 1
        assert len(summary["recent_errors"]) == 1

    def test_get_summary_empty(self):
        """Test getting summary with no data."""
        collector = DiagnosticsCollector()
        summary = collector.get_summary()

        assert summary["api_summary"] == {}
        assert summary["total_errors"] == 0
        assert summary["recent_errors"] == []

    def test_clear(self):
        """Test clearing collected data."""
        collector = DiagnosticsCollector()

        collector.record_api_call("chat", success=True, latency_ms=100)
        collector.record_error("chat", "Test error")

        collector.clear()

        assert collector._api_calls == {}
        assert collector._errors == []


class TestGetDiagnosticsCollector:
    """Tests for get_diagnostics_collector function."""

    def test_returns_singleton(self):
        """Test that the function returns a singleton instance."""
        collector1 = get_diagnostics_collector()
        collector2 = get_diagnostics_collector()

        assert collector1 is collector2

    def test_returns_collector_instance(self):
        """Test that the function returns a DiagnosticsCollector."""
        collector = get_diagnostics_collector()
        assert isinstance(collector, DiagnosticsCollector)
