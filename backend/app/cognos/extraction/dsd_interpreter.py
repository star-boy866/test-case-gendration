from __future__ import annotations

import re
from typing import Any, List

from app.domain.cognos_requirement import (
    CognosRequirement,
    RequirementCategory,
    RequirementConfidence,
    RequirementSet,
    TestOrigin
)
from app.services.canonical_parser import CanonicalDocumentModel, CanonicalTable

def _extract_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())

class DsdInterpreter:
    """
    Schema-driven DSD Interpreter.
    Converts a CanonicalDocumentModel into a populated RequirementSet.
    Applies deterministic reasoning to find gaps, conflicts, and assumptions
    using checkboxes, comments, and table structure.
    """
    def __init__(self, doc: CanonicalDocumentModel, source_document_name: str = "Unknown"):
        self.doc = doc
        self.source_document_name = source_document_name
        self.req_set = RequirementSet(source_document=source_document_name)
        self.seq_counters: dict[RequirementCategory, int] = {}
        self.report_id_prefix = "UNK"

    def _next_seq(self, cat: RequirementCategory) -> int:
        self.seq_counters[cat] = self.seq_counters.get(cat, 0) + 1
        return self.seq_counters[cat]

    def _add_req(
        self,
        category: RequirementCategory,
        field: str,
        text: str,
        status: str = "EXTRACTED",
        origin: TestOrigin = TestOrigin.DIRECT_SPECIFICATION,
        confidence: RequirementConfidence = RequirementConfidence.HIGH,
        is_ambiguous: bool = False,
        source_section: str = "Report Specification"
    ) -> CognosRequirement:
        seq = self._next_seq(category)
        
        req = CognosRequirement(
            requirement_id=f"REQ-{self.report_id_prefix}-{category.name[:4]}-{seq:03d}",
            category=category,
            field=field,
            requirement_text=text,
            source_document=self.source_document_name,
            source_section=source_section,
            status=status,
            origin=origin,
            confidence=confidence,
            is_ambiguous=is_ambiguous,
            report_id=self.req_set.report_id
        )
        self.req_set.requirements.append(req)
        return req

    def process(self) -> RequirementSet:
        self._interpret_metadata()
        self._interpret_tables()
        self._apply_reasoning_engine()
        self.req_set.compute_summary()
        return self.req_set

    def _interpret_metadata(self):
        # Scan paragraphs and first table for basic report ID
        for p in self.doc.paragraphs:
            if "PRV-INT" in p or "OPR-" in p:
                match = re.search(r"((?:PRV-INT|OPR-TPL)-\d{3})", p)
                if match:
                    self.req_set.report_id = match.group(1)
                    self.report_id_prefix = self.req_set.report_id.split('-')[-1]
                    break
                    
        if not self.req_set.report_id and self.doc.tables:
            for row in self.doc.tables[0].rows:
                if len(row.cells) >= 2 and "Report ID" in row.cells[0].text:
                    self.req_set.report_id = _extract_text(row.cells[1].text)
                    self.report_id_prefix = self.req_set.report_id.split('-')[-1]
                    break

    def _interpret_tables(self):
        # A simple schema-driven interpretation for deterministic facts.
        for t in self.doc.tables:
            # We look for typical patterns
            if not t.rows:
                continue
            
            headers = [c.text.lower().strip() for c in t.rows[0].cells]
            
            # Check if this is the Report Body mappings table
            if "field type" in headers or "business label" in headers or "column" in headers:
                self._parse_report_body(t)
            
            # Check for general Report Definition (key/value pairs)
            elif len(t.rows[0].cells) >= 2 and ("report type" in t.rows[0].cells[0].text.lower() or "report title" in t.rows[0].cells[0].text.lower()):
                self._parse_key_value_table(t)

    def _parse_report_body(self, table: CanonicalTable):
        for row in table.rows[1:]:
            cells = row.cells
            if len(cells) < 2:
                continue
                
            field_type = _extract_text(cells[0].text)
            business_label = _extract_text(cells[1].text)
            
            # Gaps detection: Blank placeholder row in template
            if not business_label or "N/A" in business_label or not field_type:
                req = self._add_req(
                    RequirementCategory.COLUMN, 
                    "Unknown", 
                    "Blank placeholder row in template.",
                    status="GAP",
                    origin=TestOrigin.DSD_DERIVED,
                    confidence=RequirementConfidence.LOW,
                    source_section="Report Body Mappings"
                )
                self.req_set.warnings.append(f"GAP: Empty row mapped in table {table.index}")
                continue

            # Valid field
            req = self._add_req(
                RequirementCategory.COLUMN,
                business_label,
                f"Report must display {business_label} as {field_type}",
                status="EXTRACTED",
                source_section="Report Body Mappings"
            )

    def _parse_key_value_table(self, table: CanonicalTable):
        for row in table.rows:
            if len(row.cells) >= 2:
                key = _extract_text(row.cells[0].text)
                val = _extract_text(row.cells[1].text)
                if key and val:
                    # Generic metadata mapping
                    cat = RequirementCategory.REPORT_METADATA
                    if "title" in key.lower(): cat = RequirementCategory.REPORT_TITLE
                    if "description" in key.lower(): cat = RequirementCategory.REPORT_DESCRIPTION
                    if "output" in key.lower(): cat = RequirementCategory.OUTPUT_FORMAT
                    
                    self._add_req(
                        cat, key, f"{key}: {val}",
                        status="EXTRACTED",
                        source_section="Report Definition"
                    )

    def _apply_reasoning_engine(self):
        """
        Reasoning engine step: Evaluates the parsed Canonical Document Model against comments and checkboxes.
        Finds conflicts, flags assumptions.
        """
        # 1. Unresolved Reviewer Comments -> Conflict or Ambiguity
        for comment in self.doc.comments:
            text = comment.get('text', '').lower()
            if not text:
                continue
            
            # If a comment is asking a question or disputing something, flag it
            if "?" in text or "sure" in text or "update" in text or "wrong" in text:
                # We attribute this conflict globally or find the closest requirement
                req = self._add_req(
                    RequirementCategory.SPECIAL_PROCESSING,
                    "Reviewer Comment",
                    f"Unresolved Comment ({comment.get('author')}): {comment.get('text')}",
                    status="CONFLICT",
                    origin=TestOrigin.COMMENT_DERIVED,
                    confidence=RequirementConfidence.LOW,
                    is_ambiguous=True,
                    source_section="Reviewer Comments"
                )
                self.req_set.warnings.append(f"CONFLICT: Unresolved reviewer comment found: '{comment.get('text')}'")

        # 2. Checkboxes overriding text
        for cb in self.doc.checkboxes:
            if cb.get('checked'):
                # In a full schema interpreter, we'd map this to a specific layout field (like output format).
                # For this implementation plan, we just register it deterministically.
                self._add_req(
                    RequirementCategory.OUTPUT_FORMAT,
                    cb.get('name', 'Unknown'),
                    f"Checkbox Selected: {cb.get('name')}",
                    status="EXTRACTED",
                    origin=TestOrigin.DSD_DERIVED,
                    source_section="Checkboxes"
                )

def interpret_dsd(doc: CanonicalDocumentModel, source_name: str) -> RequirementSet:
    interpreter = DsdInterpreter(doc, source_name)
    return interpreter.process()
