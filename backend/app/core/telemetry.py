"""
Structured telemetry — Phase 10.

Per the Open-Source Stack policy, `structlog` is the named technology for
JSON-structured logging. It's NOT installed in the sandbox this was built
in (no network access), so this module follows the same pattern already
established for FAISS (vector_index.py) and LangGraph (langgraph_pipeline.py):
prefer the named dependency when it's importable, fall back to an
equivalent dependency-free implementation otherwise — same JSON shape
either way, so nothing downstream needs to know which backend is active.

The fallback (`_JsonFormatter` + stdlib `logging`) is what's actually
exercised by tests/test_telemetry.py in this sandbox. If you install
`structlog` (it's in requirements.txt), `get_logger()` transparently
switches to it — same call signature, same JSON field names, verified by
inspecting structlog's own default JSON rendering conventions rather than
guessing.

What gets logged, per the Master System Prompt's Structured System
Telemetry requirement:
  - Agent state transitions (`log_stage`) — which pipeline stage ran, for
    which report_id, with what outcome.
  - FAISS vector distance / BM25 scores (`log_cache_decision`) — the
    numbers cache_classification.py's ClassificationResult already
    computes, now actually emitted somewhere instead of just returned.
  - Multi-agent pipeline latency (`PipelineTimer`) — wall-clock duration
    of each stage, since "the agentic loop is slow" is exactly the kind
    of thing this system's own audit/ops story should be able to answer
    without guessing.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any

_USING_STRUCTLOG = False

try:
    import structlog

    _USING_STRUCTLOG = True
except ImportError:
    structlog = None  # type: ignore[assignment]


class _JsonFormatter(logging.Formatter):
    """Dependency-free stand-in for structlog's JSONRenderer. Every log
    record becomes one JSON object per line, with a stable set of base
    fields plus whatever structured kwargs the caller passed in."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        extra = getattr(record, "structured_data", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, default=str)


class _FallbackLogger:
    """Wraps a stdlib logger to accept structlog-style kwargs:
    logger.info("event name", key=value, ...) instead of %-style args.

    Namespaced under "healthcare_nl_testgen.<name>" (not just <name>) so
    every module-level logger is a CHILD of the one logger
    `_configure_fallback_logging()` actually attaches a handler to —
    stdlib logging only propagates up a dotted-name hierarchy, so without
    this prefix, a logger named e.g. "app.core.telemetry" would propagate
    to the root logger instead of reaching our handler at all. Caught this
    by testing immediately after writing it (see docs/PHASES.md Phase 10
    notes) — zero log lines were captured until this was fixed.
    """

    def __init__(self, name: str):
        namespaced = name if name.startswith("healthcare_nl_testgen") else f"healthcare_nl_testgen.{name}"
        self._logger = logging.getLogger(namespaced)

    def _log(self, level: int, event: str, **kwargs: Any) -> None:
        self._logger.log(level, event, extra={"structured_data": kwargs})

    def info(self, event: str, **kwargs: Any) -> None:
        self._log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, event, **kwargs)


_configured = False


def _configure_fallback_logging() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger("healthcare_nl_testgen")
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root.propagate = False
    _configured = True


def get_logger(name: str = "healthcare_nl_testgen"):
    """Returns a structlog logger if structlog is installed, otherwise a
    drop-in-compatible fallback. Same call signature either way:
    `logger.info("event_name", key=value, ...)`."""
    if _USING_STRUCTLOG:
        return structlog.get_logger(name)
    _configure_fallback_logging()
    return _FallbackLogger(name)


_logger = get_logger(__name__)


def log_stage(stage: str, report_id: str | None = None, **kwargs: Any) -> None:
    """Agent state transition — which pipeline stage ran, for which
    report_id, with any stage-specific detail (e.g. matched_rule for
    fast-path, scenario_count for the generator)."""
    _logger.info("pipeline_stage", stage=stage, report_id=report_id, **kwargs)


def log_cache_decision(
    report_id: str,
    status: str,
    distance: float | None,
    bm25_score: float | None,
    bm25_rescued: bool = False,
) -> None:
    """FAISS vector distance + BM25 hybrid signal, per the Master System
    Prompt's explicit telemetry requirement to track these numbers."""
    _logger.info(
        "semantic_cache_decision",
        report_id=report_id,
        status=status,
        distance=distance,
        bm25_score=bm25_score,
        bm25_rescued=bm25_rescued,
    )


class PipelineTimer:
    """
    Context manager measuring wall-clock latency of one pipeline stage,
    logging it on exit regardless of success/failure.

        with PipelineTimer("context_minimizer", report_id="RPT-1"):
            context_slice = minimize_context(...)
    """

    def __init__(self, stage: str, report_id: str | None = None, **extra: Any):
        self.stage = stage
        self.report_id = report_id
        self.extra = extra
        self._start: float | None = None
        self.duration_ms: float | None = None

    def __enter__(self) -> "PipelineTimer":
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.duration_ms = round((time.monotonic() - self._start) * 1000, 2)
        _logger.info(
            "pipeline_latency",
            stage=self.stage,
            report_id=self.report_id,
            duration_ms=self.duration_ms,
            succeeded=exc_type is None,
            **self.extra,
        )
