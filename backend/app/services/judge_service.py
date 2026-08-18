"""
LLM-Judge persistence — Phase 10.

Thin wrapper: run the (non-gating) LLM judge and persist the result if it
produced one. Designed to be handed to FastAPI's BackgroundTasks so it
runs after the HTTP response has already been sent — see api/generation.py.

Takes its OWN DB session rather than reusing the request's, since a
background task runs after the request-scoped session (from `get_db`'s
dependency, which closes when the request finishes) may already be closed.
"""

from __future__ import annotations

import json
from typing import Callable

from app.db.session import SessionLocal
from app.models.evaluation import LLMJudgeEvaluation
from app.agents.llm_judge import run_llm_judge
from app.core.telemetry import get_logger

_logger = get_logger(__name__)




def evaluate_and_store(
    *,
    session_id: int,
    report_id: str,
    scenarios: list,
    context_slice: dict,
    requirement: str,
    llm_call: Callable[[str], str],
) -> None:
    # This is kept for backward compatibility or direct calls
    score = run_llm_judge(scenarios, context_slice, requirement, llm_call)
    if score is None:
        return

    db = SessionLocal()
    try:
        db.add(LLMJudgeEvaluation(
            session_id=session_id,
            report_id=report_id,
            completeness=score.completeness,
            hallucination_prevention=score.hallucination_prevention,
            schema_adherence=score.schema_adherence,
            overall=score.overall,
            rationale=score.rationale,
            warnings=json.dumps(score.warnings),
        ))
        db.commit()
    finally:
        db.close()


def get_latest_evaluation(db, session_id: int):
    return (
        db.query(LLMJudgeEvaluation)
        .filter(LLMJudgeEvaluation.session_id == session_id)
        .order_by(LLMJudgeEvaluation.id.desc())
        .first()
    )
