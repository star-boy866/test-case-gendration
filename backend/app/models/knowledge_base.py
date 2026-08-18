"""
Knowledge Base ORM models.

These tables hold ONLY metadata extracted from uploaded RDDs/LDMs —
table names, column names, data types, PK/FK flags, join mappings, valid
values, and explicitly-structured business rules. Per the Zero-Trust
Database Policy and Hallucination Prevention rules:

- Nothing here is ever invented. Every row traces back to a
  `source_document_id` and, transitively, to a SHA-256-hashed uploaded file.
- Free-form/unstructured document text is NEVER auto-classified as a
  business rule — it is stored separately in `UnstructuredNote` and flagged
  for human review.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base


def _now():
    return datetime.now(timezone.utc)


class SourceDocument(Base):
    """One row per uploaded file. Enables cache-busting and full traceability."""

    __tablename__ = "source_documents"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String, nullable=False, index=True)
    cr_id = Column(String, nullable=True, index=True)
    filename = Column(String, nullable=False)
    file_sha256 = Column(String, nullable=False, index=True)
    file_type = Column(String, nullable=False)  # xlsx | csv | docx | pdf
    uploaded_at = Column(DateTime, default=_now)
    uploaded_by = Column(String, nullable=True)
    parse_status = Column(String, default="parsed")  # parsed | insufficient_metadata | error
    parse_summary = Column(Text, nullable=True)  # JSON blob: counts + warnings

    tables = relationship("KBTable", back_populates="source_document", cascade="all, delete-orphan")
    columns = relationship("KBColumn", back_populates="source_document", cascade="all, delete-orphan")
    joins = relationship("KBJoin", back_populates="source_document", cascade="all, delete-orphan")
    valid_values = relationship("KBValidValue", back_populates="source_document", cascade="all, delete-orphan")
    business_rules = relationship("KBBusinessRule", back_populates="source_document", cascade="all, delete-orphan")
    unstructured_notes = relationship("UnstructuredNote", back_populates="source_document", cascade="all, delete-orphan")


class KBTable(Base):
    """A distinct table name observed in an LDM/RDD."""

    __tablename__ = "kb_tables"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String, nullable=False, index=True)
    table_name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    source_document_id = Column(Integer, ForeignKey("source_documents.id"), nullable=False)

    source_document = relationship("SourceDocument", back_populates="tables")


class KBColumn(Base):
    """A column observed for a given table, with data type and key role."""

    __tablename__ = "kb_columns"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String, nullable=False, index=True)
    table_name = Column(String, nullable=False, index=True)
    column_name = Column(String, nullable=False, index=True)
    data_type = Column(String, nullable=True)
    key_type = Column(String, nullable=True)  # PK | FK | None
    description = Column(Text, nullable=True)
    source_document_id = Column(Integer, ForeignKey("source_documents.id"), nullable=False)

    source_document = relationship("SourceDocument", back_populates="columns")


class KBJoin(Base):
    """An explicit join mapping between two table.column pairs."""

    __tablename__ = "kb_joins"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String, nullable=False, index=True)
    from_table = Column(String, nullable=False)
    from_column = Column(String, nullable=False)
    to_table = Column(String, nullable=False)
    to_column = Column(String, nullable=False)
    join_type = Column(String, nullable=True)  # INNER | LEFT | etc., if specified
    source_document_id = Column(Integer, ForeignKey("source_documents.id"), nullable=False)

    source_document = relationship("SourceDocument", back_populates="joins")


class KBValidValue(Base):
    """A permitted value (and optional meaning) for a table.column."""

    __tablename__ = "kb_valid_values"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String, nullable=False, index=True)
    table_name = Column(String, nullable=False)
    column_name = Column(String, nullable=False)
    valid_value = Column(String, nullable=False)
    meaning = Column(Text, nullable=True)
    source_document_id = Column(Integer, ForeignKey("source_documents.id"), nullable=False)

    source_document = relationship("SourceDocument", back_populates="valid_values")


class KBBusinessRule(Base):
    """A business rule EXPLICITLY provided in a structured rule column/table."""

    __tablename__ = "kb_business_rules"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String, nullable=False, index=True)
    rule_text = Column(Text, nullable=False)
    related_table = Column(String, nullable=True)
    related_column = Column(String, nullable=True)
    source_document_id = Column(Integer, ForeignKey("source_documents.id"), nullable=False)

    source_document = relationship("SourceDocument", back_populates="business_rules")


class UnstructuredNote(Base):
    """
    Free-text content (docx paragraphs, PDF text without table structure)
    that could NOT be confidently parsed into structured KB rows.

    This is surfaced to the human reviewer in the UI — it is never fed into
    generation as if it were a verified business rule.
    """

    __tablename__ = "unstructured_notes"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    reason = Column(String, nullable=True)  # why it wasn't auto-structured
    source_document_id = Column(Integer, ForeignKey("source_documents.id"), nullable=False)

    source_document = relationship("SourceDocument", back_populates="unstructured_notes")
