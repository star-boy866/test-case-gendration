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
        self._interpret_paragraphs()
        self._interpret_tables()
        self._apply_reasoning_engine()
        self.req_set.compute_summary()
        return self.req_set

    def _interpret_metadata(self):
        # Scan paragraphs and first table for basic report ID
        for p in self.doc.paragraphs:
            if "PRV-INT" in p or "OPR-" in p:
                match = re.search(r"((?:PRV-INT|OPR-TPL|OPR-SRA)-\d{3})", p)
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

    def _interpret_paragraphs(self):
        # Parse paragraphs for Unit Test Scenarios (e.g. PRV-INT-027)
        for i, p in enumerate(self.doc.paragraphs):
            text = _extract_text(p)
            
            # Extract metadata from paragraphs (e.g., in PRV-INT-027)
            lower_text = text.lower()
            if lower_text.startswith("report name:"):
                self._add_req(
                    RequirementCategory.REPORT_TITLE,
                    "Report Name",
                    text.split(":", 1)[1].strip(),
                    status="EXTRACTED",
                    source_section="Report Details"
                )
            elif lower_text.startswith("report description:"):
                self._add_req(
                    RequirementCategory.REPORT_DESCRIPTION,
                    "Report Description",
                    text.split(":", 1)[1].strip(),
                    status="EXTRACTED",
                    source_section="Report Details"
                )
            elif lower_text.startswith("output format:"):
                self._add_req(
                    RequirementCategory.OUTPUT_FORMAT,
                    "Output Format",
                    text.split(":", 1)[1].strip(),
                    status="EXTRACTED",
                    source_section="Report Details"
                )
            elif lower_text.startswith("table used"):
                self._add_req(
                    RequirementCategory.REPORT_METADATA,
                    "Source Tables",
                    text.split("-", 1)[1].strip() if "-" in text else text,
                    status="EXTRACTED",
                    source_section="Report Details"
                )
            
            if text.startswith("Scenario "):
                self._add_req(
                    RequirementCategory.BUSINESS_RULE,
                    "Unit Test Scenario",
                    text,
                    status="EXTRACTED",
                    origin=TestOrigin.DEV_UT_METHODOLOGY,
                    confidence=RequirementConfidence.HIGH,
                    source_section="UT Document Scenarios"
                )

    def _interpret_tables(self):
        # A simple schema-driven interpretation for deterministic facts.
        for t in self.doc.tables:
            # We look for typical patterns
            if not t.rows:
                continue
            
            # Look at the first 4 rows to find headers
            all_headers = set()
            for row in t.rows[:4]:
                all_headers.update([c.text.lower().strip() for c in row.cells])
            
            # Check if this is the Report Body mappings table
            # Expanded to match synonyms like "field name", "data element", "report column"
            is_report_body = any(
                k in h for h in all_headers 
                for k in ["field type", "business label", "column", "report body", "field name", "data element", "data type"]
            )
            
            if is_report_body:
                self._parse_report_body(t)
            
            # Check for general Report Definition (key/value pairs)
            else:
                is_key_value = False
                for row in t.rows[:4]:
                    row_text = row.cells[0].text.lower() if len(row.cells) > 0 else ""
                    if "report type" in row_text or "report title" in row_text or "client report id" in row_text:
                        is_key_value = True
                        break
                        
                if is_key_value:
                    self._parse_key_value_table(t)

    def _parse_report_body(self, table: CanonicalTable):
        # Find the actual header row and dynamically assign column indices
        start_idx = 1
        type_col_idx = 0
        label_col_idx = 1
        source_table_col_idx = 4
        
        for i, row in enumerate(table.rows[:5]):
            row_texts = [c.text.lower().strip() for c in row.cells]
            if any(k in h for h in row_texts for k in ["field type", "business label", "field name", "column", "data element"]):
                start_idx = i + 1
                # Try to map columns dynamically based on this header row
                for col_i, cell_text in enumerate(row_texts):
                    if "type" in cell_text or "format" in cell_text:
                        type_col_idx = col_i
                    elif "label" in cell_text or "name" in cell_text or "column" in cell_text or "element" in cell_text:
                        # Prioritize finding the business label/field name
                        label_col_idx = col_i
                    elif "table" in cell_text and "source" in cell_text:
                        source_table_col_idx = col_i
                break

        for row in table.rows[start_idx:]:
            cells = row.cells
            
            # We need at least the label column to extract something
            if len(cells) <= label_col_idx:
                continue
                
            field_type = _extract_text(cells[type_col_idx].text) if len(cells) > type_col_idx else ""
            business_label = _extract_text(cells[label_col_idx].text)
            
            # Fallback if label is empty but there's a type (maybe they are swapped in weird templates)
            if not business_label and field_type and len(field_type) > 3 and " " not in field_type:
                 # It's possible the columns are just off
                 field_type, business_label = business_label, field_type
            
            # Gaps detection / Template boilerplate filtering
            lower_label = business_label.lower()
            lower_type = field_type.lower()
            
            if not business_label or "n/a" in lower_label:
                continue # Skip empty placeholders entirely
                
            if "summary" in lower_type or "daily total" in lower_type or "row" in lower_type:
                continue # Skip structural template boilerplate

            # Valid field
            source_table = _extract_text(cells[source_table_col_idx].text) if len(cells) > source_table_col_idx else ""
            req = self._add_req(
                RequirementCategory.COLUMN,
                business_label,
                f"Report must display {business_label}" + (f" as {field_type}" if field_type else ""),
                status="EXTRACTED",
                source_section="Report Body Mappings"
            )
            req.source_table = source_table

    def _parse_key_value_table(self, table: CanonicalTable):
        for row in table.rows:
            if len(row.cells) >= 2:
                key = _extract_text(row.cells[0].text)
                val = _extract_text(row.cells[1].text)
                if key and val:
                    # Generic metadata mapping
                    cat = RequirementCategory.REPORT_METADATA
                    lower_key = key.lower()
                    if "title" in lower_key: cat = RequirementCategory.REPORT_TITLE
                    elif "description" in lower_key: cat = RequirementCategory.REPORT_DESCRIPTION
                    elif "output" in lower_key: cat = RequirementCategory.OUTPUT_FORMAT
                    elif "selection criteria" in lower_key or "parameter" in lower_key: cat = RequirementCategory.PARAMETER
                    elif "sort by" in lower_key: cat = RequirementCategory.SORT
                    elif "control break" in lower_key: cat = RequirementCategory.CONTROL_BREAK
                    elif "total" in lower_key: cat = RequirementCategory.TOTAL
                    elif "count" in lower_key: cat = RequirementCategory.COUNT
                    
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
