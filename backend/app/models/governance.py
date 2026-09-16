"""
Governance, Audit, Provenance, and Scenario Learning Models.

Phase 12 upgrade for Cognos Test Case Studio:
- SOURCE: source_documents, source_document_versions, source_sections, source_snapshots
- STUDIO: generated_scenarios, scenario_versions, scenario_feedback, scenario_reviews,
          scenario_evidence, scenario_execution_results
- AI / LEARNING: generation_metadata, retrieval_events, model_evaluations, prompt_versions, learning_candidates
- AUDIT: audit_events, login_events, security_events, password_history
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float,
    DateTime, ForeignKey, JSON, Index
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.session import Base


# ═══════════════════════════════════════════════════════════════════════════════
# 1. AUTH & SECURITY SUPPORT
# ═══════════════════════════════════════════════════════════════════════════════

class PasswordHistory(Base):
    """Tracks historical password hashes to prevent immediate reuse."""
    __tablename__ = "password_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SOURCE DOCUMENT & EVIDENCE PROVENANCE
# ═══════════════════════════════════════════════════════════════════════════════

from app.models.knowledge_base import SourceDocument


class SourceDocumentVersion(Base):
    """Version history of an uploaded document if re-uploaded or modified."""
    __tablename__ = "source_document_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_document_id: Mapped[int] = mapped_column(Integer, ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    file_hash: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)

    document = relationship("SourceDocument")



class SourceSection(Base):
    """Parsed section within a source document for fine-grained section tracking."""
    __tablename__ = "source_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_document_id: Mapped[int] = mapped_column(Integer, ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    section_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    heading_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SourceSnapshot(Base):
    """
    Direct provenance record linking a visual evidence crop to the exact source document,
    generation run, scenario, and rendering coordinates.
    """
    __tablename__ = "source_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_document_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    scenario_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    evidence_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    semantic_target: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    crop_box = Column(JSON, nullable=True)  # [x0, top, x1, bottom] or dict
    renderer: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    crop_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    snapshot_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_semantic_crop: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    document = relationship("SourceDocument")



# ═══════════════════════════════════════════════════════════════════════════════
# 3. TEST CASE STUDIO & SCENARIO LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════════

class GeneratedScenario(Base):
    """
    Persistent scenario record mapping the lifecycle of a test case,
    maintaining the original baseline while versioning changes.
    """
    __tablename__ = "generated_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    test_case_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    scenario_name: Mapped[str] = mapped_column(String, nullable=False)
    methodology: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    section: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    target_field: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    evidence_scope: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="GENERATED", nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    versions = relationship("ScenarioVersion", back_populates="scenario", cascade="all, delete-orphan")
    feedback = relationship("ScenarioFeedback", back_populates="scenario", cascade="all, delete-orphan")


class ScenarioVersion(Base):
    """
    Immutable version snapshot for a test scenario.
    Every human correction, admin edit, or AI regeneration produces a new version row.
    """
    __tablename__ = "scenario_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("generated_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    test_case_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content_json = Column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)  # AI_GENERATED, TESTER_EDIT, TESTER_CORRECTION, ADMIN_EDIT, SYSTEM_REGENERATION
    changed_by: Mapped[str] = mapped_column(String, nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    scenario = relationship("GeneratedScenario", back_populates="versions")


class ScenarioFeedback(Base):
    """
    Human-in-the-Loop review and governance feedback.
    """
    __tablename__ = "scenario_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("generated_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    feedback_type: Mapped[str] = mapped_column(String, nullable=False, index=True)  # ACCEPTED, CORRECTED, REJECTED, REGENERATED, APPROVED
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_fields = Column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    scenario = relationship("GeneratedScenario", back_populates="feedback")


class ScenarioReview(Base):
    """Formal scenario review decisions by SIT/QA testers or Admins."""
    __tablename__ = "scenario_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scenario_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("generated_scenarios.id", ondelete="CASCADE"), nullable=True, index=True)
    test_case_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    run_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    reviewer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reviewer_username: Mapped[str] = mapped_column(String, nullable=False)
    review_status: Mapped[str] = mapped_column(String, nullable=False)  # APPROVED, REJECTED, NEEDS_REVIEW, CORRECTED
    review_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issue_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    issue_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ScenarioEvidence(Base):
    """Authoritative association between a scenario and its visual evidence."""
    __tablename__ = "scenario_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scenario_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("generated_scenarios.id", ondelete="CASCADE"), nullable=True, index=True)
    test_case_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    evidence_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    snapshot_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("source_snapshots.id", ondelete="SET NULL"), nullable=True)
    reference_data = Column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ScenarioExecutionResult(Base):
    """Results from executing test scenarios in target environments."""
    __tablename__ = "scenario_execution_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scenario_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("generated_scenarios.id", ondelete="CASCADE"), nullable=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String, default="NOT_RUN", nullable=False)  # PASSED, FAILED, BLOCKED, NOT_RUN
    execution_method: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    execution_tool: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    executed_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. AI & SCENARIO LEARNING
# ═══════════════════════════════════════════════════════════════════════════════

class GenerationMetadata(Base):
    """Metadata detailing the AI inference run (provider, duration, parameters)."""
    __tablename__ = "generation_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    scenario_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    template_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    generation_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retrieval_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    retrieved_example_ids = Column(JSON, nullable=True)
    input_metadata = Column(JSON, nullable=True)
    output_metadata = Column(JSON, nullable=True)
    validation_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class RetrievalEvent(Base):
    """Details few-shot and pattern retrieval events during generation."""
    __tablename__ = "retrieval_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    query_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    top_k: Mapped[int] = mapped_column(Integer, default=3)
    retrieved_ids = Column(JSON, nullable=True)
    scores = Column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ModelEvaluation(Base):
    """Quality and compliance evaluations for generated test cases."""
    __tablename__ = "model_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scenario_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    evaluator: Mapped[str] = mapped_column(String, nullable=False)  # LLM_JUDGE, RULE_ENGINE, HUMAN_AUDITOR
    score: Mapped[float] = mapped_column(Float, nullable=False)
    criteria_scores = Column(JSON, nullable=True)
    evaluation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class PromptVersion(Base):
    """Authoritative system prompts used for test generation."""
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prompt_name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class LearningCandidate(Base):
    """
    Curated dataset of high-quality, human-approved or human-corrected scenarios
    selected for future model evaluation and fine-tuning.
    """
    __tablename__ = "learning_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scenario_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("generated_scenarios.id", ondelete="CASCADE"), nullable=True, index=True)
    test_case_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source_version_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quality_status: Mapped[str] = mapped_column(String, default="QUALIFIED", nullable=False)  # QUALIFIED, PENDING_REVIEW, EXCLUDED
    approval_status: Mapped[str] = mapped_column(String, default="APPROVED", nullable=False)
    evaluation_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    selected_for_learning: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    selected_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    selected_by: Mapped[str] = mapped_column(String, nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. AUDIT TRAIL & SECURITY EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

class AuditEvent(Base):
    """
    Comprehensive, immutable audit trail for all user and admin actions.
    Guaranteed to never contain credentials, passwords, or secrets.
    """
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    actor_username: Mapped[str] = mapped_column(String, nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String, nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    scenario_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    details = Column(JSON, nullable=True)


class LoginEvent(Base):
    """Dedicated authentication access log."""
    __tablename__ = "login_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class SecurityEvent(Base):
    """High-priority security alerts (e.g. rate-limiting, lockout, tampering)."""
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String, default="MEDIUM", nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    actor_username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    details = Column(JSON, nullable=True)
