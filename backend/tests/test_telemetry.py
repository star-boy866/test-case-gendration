"""
Tests for app.core.telemetry.

Captures real log output via a StringIO handler attached to the
"healthcare_nl_testgen" logger and parses it as JSON — this proves the
actual emitted log lines are valid, correctly-shaped JSON, not just that
the functions ran without raising.
"""

import io
import json
import logging

import pytest

from app.core.telemetry import get_logger, log_stage, log_cache_decision, PipelineTimer, _JsonFormatter


@pytest.fixture()
def captured_logs():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger("healthcare_nl_testgen")
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    yield stream
    root.removeHandler(handler)


def _lines(stream: io.StringIO) -> list[dict]:
    return [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]


def test_log_stage_emits_valid_json_with_expected_fields(captured_logs):
    log_stage("context_minimizer", report_id="RPT-1", tables_selected=3)
    entries = _lines(captured_logs)
    assert len(entries) == 1
    assert entries[0]["event"] == "pipeline_stage"
    assert entries[0]["stage"] == "context_minimizer"
    assert entries[0]["report_id"] == "RPT-1"
    assert entries[0]["tables_selected"] == 3
    assert "timestamp" in entries[0]
    assert entries[0]["level"] == "info"


def test_log_cache_decision_emits_distance_and_bm25_fields(captured_logs):
    log_cache_decision("RPT-1", status="partial_hit", distance=0.22, bm25_score=4.5, bm25_rescued=True)
    entries = _lines(captured_logs)
    assert entries[0]["event"] == "semantic_cache_decision"
    assert entries[0]["distance"] == 0.22
    assert entries[0]["bm25_score"] == 4.5
    assert entries[0]["bm25_rescued"] is True


def test_pipeline_timer_logs_duration_and_success_on_normal_exit(captured_logs):
    with PipelineTimer("generator_agent", report_id="RPT-1", scenario_count=2):
        pass
    entries = _lines(captured_logs)
    assert entries[0]["event"] == "pipeline_latency"
    assert entries[0]["stage"] == "generator_agent"
    assert entries[0]["succeeded"] is True
    assert isinstance(entries[0]["duration_ms"], (int, float))
    assert entries[0]["scenario_count"] == 2


def test_pipeline_timer_logs_succeeded_false_when_block_raises(captured_logs):
    with pytest.raises(ValueError):
        with PipelineTimer("generator_agent", report_id="RPT-1"):
            raise ValueError("simulated failure")
    entries = _lines(captured_logs)
    assert entries[0]["succeeded"] is False


def test_get_logger_returns_something_with_info_method():
    logger = get_logger("some.module")
    assert hasattr(logger, "info")
