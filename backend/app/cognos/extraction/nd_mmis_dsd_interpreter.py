"""
North Dakota MMIS DSD Interpreter.

Extracts structured sections, metadata, Wingdings checkbox selections,
tables, and report fields from North Dakota Medicaid Systems Project MMIS
Report Definition documents.
"""

from pathlib import Path
from typing import List, Optional
import logging
import docx

from app.cognos.extraction.nd_mmis_dsd_models import (
    NdMmisDsd,
    NdMmisReportDefinitionSection,
    NdSelectionCriterionRow,
    NdSortRow,
    NdReportOutputSection,
    NdSectionHeadingRow,
    NdReportBodyRow,
    NdFootnoteRow,
)

logger = logging.getLogger(__name__)


def _is_checked_run(run) -> bool:
    """Checks if a docx Run contains a checked box symbol (Wingdings F0FE/f0fe)."""
    xml = run._r.xml
    if "F0FE" in xml or "f0fe" in xml:
        return True
    if run.text and any(c in run.text for c in ["☒", "☑", "[X]", "[x]"]):
        return True
    return False


def _cell_has_checked(cell) -> bool:
    """Checks if any paragraph run in a cell has a checked box."""
    for p in cell.paragraphs:
        for r in p.runs:
            if _is_checked_run(r):
                return True
    return False


def _get_cell_text(cell) -> str:
    return cell.text.strip().replace("\n", " ")


class NdMmisDsdInterpreter:
    """
    Parses an ND MMIS DOCX into a structured NdMmisDsd AST.
    """

    def __init__(self, doc_path: Path):
        self.doc_path = Path(doc_path)
        self.doc = docx.Document(str(self.doc_path))

    def interpret(self) -> NdMmisDsd:
        dsd = NdMmisDsd()

        # Table 0: Report Definition
        if len(self.doc.tables) > 0:
            self._parse_report_definition_table(self.doc.tables[0], dsd)

        # Look for Specification Table (typically Table 3 or table with 'Report Body')
        spec_table = None
        for t in self.doc.tables[1:]:
            full_text = " ".join(c.text for r in t.rows[:5] for c in r.cells)
            if "Report Specification" in full_text or "Report Body" in full_text or "Field Label" in full_text:
                spec_table = t
                break

        if spec_table is not None:
            self._parse_report_specification_table(spec_table, dsd)

        return dsd

    def _parse_report_definition_table(self, table, dsd: NdMmisDsd):
        """Parses Table 0 containing Report Definition metadata, Generation, Criteria, Sorts, Output, Retention."""
        current_section = "HEADER"

        for r_idx, r in enumerate(table.rows):
            row_texts = [_get_cell_text(c) for c in r.cells]
            first_cell = row_texts[0] if row_texts else ""

            # Check section transitions
            if "Report Generation" in first_cell:
                current_section = "GENERATION"
                continue
            elif "Report Selection Criteria" in first_cell:
                current_section = "SELECTION_CRITERIA"
                continue
            elif "Report Control Breaks" in first_cell or "Sorts" in first_cell:
                current_section = "SORTS"
                continue
            elif first_cell.strip() == "Report Output":
                current_section = "OUTPUT"
                continue
            elif "Security Requirement" in first_cell:
                current_section = "SECURITY"
                continue
            elif "Report Retention" in first_cell and "Type" not in first_cell:
                current_section = "RETENTION"
                continue

            # Process row based on current section
            if current_section == "HEADER":
                for c_idx, cell in enumerate(r.cells):
                    txt = _get_cell_text(cell)
                    if "Report Name:" in txt:
                        val = self._extract_value_after_label(row_texts, "Report Name:")
                        if val:
                            dsd.definition.report_name = val
                    elif "Report ID:" in txt:
                        val = self._extract_value_after_label(row_texts, "Report ID:")
                        if val:
                            dsd.definition.report_id = val
                    elif "Report Description:" in txt:
                        val = self._extract_value_after_label(row_texts, "Report Description:")
                        if val:
                            dsd.definition.report_description = val
                    elif "State Line of Business:" in txt:
                        val = self._extract_value_after_label(row_texts, "State Line of Business:")
                        if val:
                            dsd.definition.state_lob = val

                # Check MITA Process & Report Status checkboxes
                if "MITA Business Process:" in first_cell:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            dsd.definition.mita_process = _get_cell_text(cell).replace("MITA Business Process:", "").strip()
                elif "Report Status:" in first_cell:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            status_val = _get_cell_text(cell)
                            if "Standard" in status_val:
                                dsd.definition.report_status = "Standard"
                            elif "Customized" in status_val:
                                dsd.definition.report_status = "Customized"
                            elif "New" in status_val:
                                dsd.definition.report_status = "New"

            elif current_section == "GENERATION":
                if "Report Generated From:" in first_cell:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            dsd.definition.generated_from = _get_cell_text(cell)
                elif "Report Calendar Type:" in first_cell:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            dsd.definition.calendar_type = _get_cell_text(cell)
                elif "Report Frequency Type:" in first_cell:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            txt = _get_cell_text(cell)
                            dsd.definition.frequency_type = txt
                            if "Event Driven" in txt or "UC-" in txt or "Please explain:" in txt:
                                dsd.definition.frequency_explanation = txt

            elif current_section == "SELECTION_CRITERIA":
                # Header row: Report Field | Report Parameters | Prompt | Default Prompt Value
                if "Report Field" in row_texts or "Default Prompt Value" in row_texts:
                    continue
                # If cells contain actual criterion
                if len(r.cells) >= 3:
                    field_val = _get_cell_text(r.cells[1] if len(r.cells) > 1 else r.cells[0])
                    if field_val and field_val != "N/A" and "Report Selection Criteria" not in field_val:
                        dsd.selection_criteria.append(NdSelectionCriterionRow(
                            field_name=field_val,
                            prompt=_get_cell_text(r.cells[2]) if len(r.cells) > 2 else None
                        ))

            elif current_section == "SORTS":
                if "Sort By:" in first_cell:
                    field_candidates = [t for t in row_texts[1:] if t and t not in ("Ascending", "Descending", "Sort By:")]
                    field_name = field_candidates[0] if field_candidates else ""
                    if field_name:
                        direction = "Ascending"
                        for cell in r.cells:
                            txt = _get_cell_text(cell)
                            if "Descending" in txt and _cell_has_checked(cell):
                                direction = "Descending"
                                break
                            elif "Ascending" in txt and _cell_has_checked(cell):
                                direction = "Ascending"
                        dsd.sorts.append(NdSortRow(field_name=field_name, direction=direction))

            elif current_section == "OUTPUT":
                if "Report Output Format:" in first_cell:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            fmt = _get_cell_text(cell)
                            if fmt and fmt not in dsd.output.output_formats:
                                dsd.output.output_formats.append(fmt)
                elif "Reporting Portal:" in first_cell:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            dsd.output.portal = _get_cell_text(cell)

            elif current_section == "RETENTION":
                if "Report Retention Type:" in first_cell:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            dsd.output.retention_type = _get_cell_text(cell)
                elif "Report Output Versions:" in first_cell:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            txt = _get_cell_text(cell)
                            if "Duration" in txt or any(unit in txt for unit in ["Days", "Months", "Years"]):
                                dsd.output.retention_duration = "7 Years" if "Years" in txt or "7" in txt else txt

        if not dsd.output.output_formats:
            dsd.output.output_formats = ["Excel"]

    def _parse_report_specification_table(self, table, dsd: NdMmisDsd):
        """Parses Table 3 containing Presentation Type, Section Headings, Report Body, Footnotes."""
        current_sub = "PRESENTATION"

        for r in table.rows:
            row_texts = [_get_cell_text(c) for c in r.cells]
            joined_row = " ".join(row_texts).strip()
            if not joined_row:
                continue

            first_cell = row_texts[0] if row_texts else ""

            # Check sub-section transitions
            if "Report Title" in joined_row or "Section Heading" in joined_row:
                current_sub = "SECTION_HEADINGS"
                continue
            elif "Chart Heading" in joined_row:
                current_sub = "CHART"
                continue
            elif "Report Body" in joined_row:
                current_sub = "BODY"
                continue
            elif "Report Drill Through" in joined_row:
                current_sub = "DRILL_THROUGH"
                continue
            elif "EDMS File Indexing" in joined_row or "Logging Special" in joined_row:
                current_sub = "OTHER"
                continue
            elif "Report Footnote" in joined_row:
                current_sub = "FOOTNOTES"
                continue

            if current_sub == "PRESENTATION":
                if "Presentation Type:" in joined_row:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            txt = _get_cell_text(cell)
                            if "List" in txt:
                                dsd.presentation_type = "List Object"
                            elif "Crosstab" in txt:
                                dsd.presentation_type = "Crosstab Object"

            elif current_sub == "SECTION_HEADINGS":
                if "Report Section Label" in joined_row or "Change Control" in joined_row:
                    continue
                unique_cells = []
                for c in r.cells:
                    txt = _get_cell_text(c)
                    if txt and (not unique_cells or unique_cells[-1] != txt):
                        unique_cells.append(txt)

                if len(unique_cells) >= 1 and unique_cells[0] not in ("N/A", ""):
                    lbl = unique_cells[0]
                    desc = unique_cells[1] if len(unique_cells) > 1 else None
                    proc = unique_cells[2] if len(unique_cells) > 2 else None
                    dsd.section_headings.append(NdSectionHeadingRow(
                        label=lbl,
                        description=desc,
                        processing_rules=proc
                    ))

            elif current_sub == "BODY":
                if "Field Label" in joined_row or "Change Control" in joined_row or "Report Specification" in joined_row:
                    continue

                unique_cells = []
                for c in r.cells:
                    txt = _get_cell_text(c)
                    if txt and (not unique_cells or unique_cells[-1] != txt):
                        unique_cells.append(txt)

                cleaned = [u for u in unique_cells if u not in ("CC", "Field Type", "Field Label")]
                if len(cleaned) >= 4:
                    field_type = "Column"
                    field_label = ""
                    field_desc = ""
                    src_table = ""
                    src_col = ""
                    proc_rules = ""

                    if "column" in cleaned[0].lower():
                        field_type = cleaned[0]
                        field_label = cleaned[1] if len(cleaned) > 1 else ""
                        field_desc = cleaned[2] if len(cleaned) > 2 else ""
                        src_table = cleaned[3] if len(cleaned) > 3 else ""
                        src_col = cleaned[4] if len(cleaned) > 4 else ""
                        if len(cleaned) > 5:
                            proc_rules = cleaned[5]
                    else:
                        field_label = cleaned[0]
                        field_desc = cleaned[1] if len(cleaned) > 1 else ""
                        src_table = cleaned[2] if len(cleaned) > 2 else ""
                        src_col = cleaned[3] if len(cleaned) > 3 else ""
                        if len(cleaned) > 4:
                            proc_rules = cleaned[4]

                    if field_label and field_label not in ("Field Label", "Report Body", "N/A"):
                        dsd.report_body.append(NdReportBodyRow(
                            field_type=field_type,
                            field_label=field_label,
                            field_description=field_desc,
                            source_table=src_table,
                            source_column=src_col,
                            source_column_processing_rules=proc_rules
                        ))

            elif current_sub == "FOOTNOTES":
                if "Report Footnote Label" in joined_row or "Change Control" in joined_row:
                    continue
                unique_cells = []
                for c in r.cells:
                    txt = _get_cell_text(c)
                    if txt and (not unique_cells or unique_cells[-1] != txt):
                        unique_cells.append(txt)

                if len(unique_cells) >= 2:
                    lbl = unique_cells[0]
                    desc = unique_cells[1] if len(unique_cells) > 1 else None
                    proc = unique_cells[2] if len(unique_cells) > 2 else None
                    dsd.footnotes.append(NdFootnoteRow(
                        label=lbl,
                        description=desc,
                        processing_rules=proc
                    ))

    def _extract_value_after_label(self, row_texts: List[str], label: str) -> Optional[str]:
        for i, text in enumerate(row_texts):
            if label in text:
                clean = text.replace(label, "").strip()
                if clean:
                    return clean
                if i + 1 < len(row_texts):
                    val = row_texts[i + 1].strip()
                    if val and val != label:
                        return val
        return None
