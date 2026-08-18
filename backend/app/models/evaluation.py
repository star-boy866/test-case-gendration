"""
LLM-as-Judge evaluation record — Phase 10.

Purely for audit/reporting. Nothing in the pipeline reads this table to
make a decision — see app/agents/llm_judge.py's docstring for why that's
deliberate. A missing row for a session just means the background
evaluation hasn't completed (or the LLM backend was unavailable when it
ran), not that anything failed.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey

from app.db.session import Base


class LLMJudgeEvaluation(Base):
    __tablename__ = "llm_judge_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    report_id = Column(String, nullable=False, index=True)
    completeness = Column(Float, nullable=False)
    hallucination_prevention = Column(Float, nullable=False)
    schema_adherence = Column(Float, nullable=False)
    overall = Column(Float, nullable=False)
    rationale = Column(Text, nullable=True)
    warnings = Column(Text, nullable=True)  # JSON-encoded list[str]
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
