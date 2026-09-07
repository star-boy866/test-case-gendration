"""
Cognos-specific SQLAlchemy ORM models.

These models persist the intermediate and final outputs of the Cognos
UT test case generation pipeline:
- Parsed metadata and requirements (traceability)
- Generated test cases
- Coverage and quality metrics
- Pipeline execution history
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float,
    DateTime, ForeignKey, JSON, Table
)
from sqlalchemy.orm import relationship

from app.db.session import Base

cognos_test_case_requirements = Table(
    "cognos_test_case_requirements", Base.metadata,
    Column("test_case_id", Integer, ForeignKey("cognos_test_cases.id", ondelete="CASCADE"), primary_key=True),
    Column("requirement_id", Integer, ForeignKey("cognos_requirements.id", ondelete="CASCADE"), primary_key=True)
)

class CognosGenerationRun(Base):
    """
    Audit record for a pipeline execution run.
    """
    __tablename__ = "cognos_generation_runs"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String, index=True, nullable=False)
    report_title = Column(String, nullable=True)
    source_document = Column(String, nullable=False)
    source_document_path = Column(String, nullable=True)
    source_document_sha256 = Column(String, nullable=True)
    job_id = Column(String, nullable=True)
    
    # LLM configuration used
    llm_provider = Column(String, nullable=True)
    llm_model = Column(String, nullable=True)
    
    # Store the complete parsed report definition (P1.9 fix)
    report_definition_json = Column(JSON, nullable=True)
    
    # Stats
    requirements_extracted = Column(Integer, default=0)
    test_cases_generated = Column(Integer, default=0)
    coverage_percentage = Column(Float, default=0.0)
    
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="running")  # running, completed, failed
    error_message = Column(Text, nullable=True)
    
    requested_by = Column(String, nullable=False)

    # Project Context (Optional CR / Defect metadata)
    work_type = Column(String, nullable=True)
    work_item_id = Column(String, nullable=True)
    work_item_title = Column(String, nullable=True)

    requirements = relationship("CognosRequirementModel", back_populates="run", cascade="all, delete-orphan")
    test_cases = relationship("CognosTestCaseModel", back_populates="run", cascade="all, delete-orphan")


class CognosRequirementModel(Base):
    """
    Persisted Cognos Requirement.
    """
    __tablename__ = "cognos_requirements"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("cognos_generation_runs.id"), nullable=False)
    
    requirement_id = Column(String, index=True, nullable=False)
    report_id = Column(String, index=True, nullable=False)
    category = Column(String, nullable=False)
    
    field_name = Column(String, nullable=False)
    requirement_text = Column(Text, nullable=False)
    
    source_section = Column(String, nullable=False)
    source_page = Column(Integer, nullable=True)
    
    # JSON-encoded lists/dicts
    source_columns = Column(JSON, nullable=True)  
    processing_rule = Column(Text, nullable=True)
    formatting_rule = Column(Text, nullable=True)
    
    confidence = Column(String, nullable=False)
    is_ambiguous = Column(Boolean, default=False)
    open_questions = Column(JSON, nullable=True)
    is_duplicate_of = Column(String, nullable=True)

    run = relationship("CognosGenerationRun", back_populates="requirements")
    test_cases = relationship(
        "CognosTestCaseModel",
        secondary=cognos_test_case_requirements,
        back_populates="requirements"
    )


class CognosTestCaseModel(Base):
    """
    Persisted Cognos UT Test Case.
    """
    __tablename__ = "cognos_test_cases"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("cognos_generation_runs.id"), nullable=False)
    
    test_case_id = Column(String, index=True, nullable=False)
    report_id = Column(String, index=True, nullable=False)
    category = Column(String, nullable=False)
    
    test_case_title = Column(String, nullable=False)
    requirement_id = Column(String, nullable=True)
    
    objective = Column(Text, nullable=False)
    preconditions = Column(Text, nullable=True)
    test_data = Column(Text, nullable=True)
    test_steps = Column(Text, nullable=False)
    expected_result = Column(Text, nullable=False)
    validation_logic = Column(Text, nullable=True)
    validation_sql = Column(Text, nullable=True)
    
    source_section = Column(String, nullable=False)
    source_page = Column(Integer, nullable=True)
    
    # Traced mapping
    source_table = Column(String, nullable=True)
    source_column = Column(String, nullable=True)
    processing_rule = Column(Text, nullable=True)
    formatting_rule = Column(Text, nullable=True)
    
    priority = Column(String, nullable=False)
    status = Column(String, default="Generated")
    origin = Column(String, nullable=False)
    version = Column(Integer, default=1)
    
    notes = Column(Text, nullable=True)
    open_questions = Column(Text, nullable=True)
    evidence_references = Column(JSON, nullable=True)
    # Phase 12Q Authoritative scenario execution order
    scenario_order = Column(Integer, nullable=True, default=0)
    
    # HITL Review fields
    review_status = Column(String, default="GENERATED", nullable=True)  # GENERATED, NEEDS_REVIEW, CORRECTED, APPROVED, REJECTED
    review_comments = Column(Text, nullable=True)
    reviewer = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    issue_type = Column(String, nullable=True)
    issue_comment = Column(Text, nullable=True)
    duplicate_of_id = Column(String, nullable=True)
    execution_method = Column(String, nullable=True)
    execution_tool = Column(String, nullable=True)

    # Store history of human edits (HITL revision history with diffs)
    edit_history = Column(JSON, nullable=True)

    run = relationship("CognosGenerationRun", back_populates="test_cases")
    requirements = relationship(
        "CognosRequirementModel",
        secondary=cognos_test_case_requirements,
        back_populates="test_cases"
    )


def ensure_cognos_columns():
    """Ensure newly added HITL and project context columns exist in existing database tables."""
    try:
        from app.db.session import engine
        from sqlalchemy import text, inspect
        with engine.connect() as conn:
            insp = inspect(conn)
            table_names = insp.get_table_names()

            if "cognos_generation_runs" in table_names:
                run_cols = [c["name"] for c in insp.get_columns("cognos_generation_runs")]
                for col, col_type in [("work_type", "VARCHAR"), ("work_item_id", "VARCHAR"), ("work_item_title", "VARCHAR")]:
                    if col not in run_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE cognos_generation_runs ADD COLUMN {col} {col_type}"))
                            conn.commit()
                        except Exception:
                            pass

            if "cognos_test_cases" in table_names:
                tc_cols = [c["name"] for c in insp.get_columns("cognos_test_cases")]
                new_cols = [
                    ("review_status", "VARCHAR DEFAULT 'GENERATED'"),
                    ("review_comments", "TEXT"),
                    ("reviewer", "VARCHAR"),
                    ("reviewed_at", "DATETIME"),
                    ("issue_type", "VARCHAR"),
                    ("issue_comment", "TEXT"),
                    ("duplicate_of_id", "VARCHAR"),
                    ("execution_method", "VARCHAR"),
                    ("execution_tool", "VARCHAR"),
                    ("validation_sql", "TEXT"),
                ]
                for col, col_type in new_cols:
                    if col not in tc_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE cognos_test_cases ADD COLUMN {col} {col_type}"))
                            conn.commit()
                        except Exception:
                            pass
    except Exception:
        pass


ensure_cognos_columns()
