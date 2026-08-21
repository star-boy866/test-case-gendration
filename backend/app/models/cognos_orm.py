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
    
    # Store history of human edits (if applicable in HITL phase)
    edit_history = Column(JSON, nullable=True)

    run = relationship("CognosGenerationRun", back_populates="test_cases")
    requirements = relationship(
        "CognosRequirementModel",
        secondary=cognos_test_case_requirements,
        back_populates="test_cases"
    )
