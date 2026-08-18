"""
Refinement Row ORM model — Phase 6.

One row per scenario in a session's Interactive Refinement Grid. Rows are
created either by a generation run (source="ai_generated") or manually by
a tester (source="manual"). `original_snapshot_json` captures the field
values at row-creation time and is never modified after that — every
subsequent edit is diffed against this frozen snapshot (not against the
previous edit) so the audit trail always shows "what the AI originally
produced" vs. "what a human changed it to", per the Master System Prompt's
audit requirement: "explicit logs of any human overrides made during the
interactive UI refinement step."
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey

from app.db.session import Base


class RefinementRow(Base):
    __tablename__ = "refinement_rows"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    report_id = Column(String, nullable=False, index=True)
    requirement_text = Column(Text, nullable=True)  # NL requirement that produced this row, if AI-generated

    test_scenario = Column(Text, nullable=False)
    detailed_test_steps = Column(Text, nullable=False)
    expected_results = Column(Text, nullable=False)
    verification_sql = Column(Text, nullable=False)
    category = Column(String, nullable=True)

    source = Column(String, default="ai_generated")  # ai_generated | ai_generated_edited | manual
    original_snapshot_json = Column(Text, nullable=False)  # JSON: the 4 editable fields as first created

    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
