"""
North Dakota MMIS DSD Interpreter.

Extracts structured sections, metadata, Wingdings checkbox selections,
tables, and report fields from North Dakota Medicaid Systems Project MMIS
Report Definition documents.
"""

from pathlib import Path
from typing import List, Optional
import logging
import re
import docx

from app.cognos.extraction.nd_mmis_dsd_models import (
    NdMmisDsd,
    NdMmisReportDefinitionSection,
    NdSelectionCriterionRow,
    NdSortRow,
    NdControlBreakRow,
    NdTotalCountRow,
    NdSpecialProcessingRow,
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


def _is_db_identifier(val: str) -> bool:
    """Checks if a string looks like a database table or column name (e.g., C_HDR_PARENT_TB, B_SYS_ID)."""
    clean = val.strip()
    if not clean or len(clean) < 2:
        return False
    # Must be all uppercase, underscores, digits, hyphens, dots — no spaces or long prose
    if " " in clean and len(clean) > 40:
        return False
    # Check for prose indicators
    prose_indicators = [
        "if ", "use ", "where ", "refer ", "from the ", "look up ", "format",
        "make sure", "join ", "between ", "see report", "use the ", "pull ",
        "or if", "else ", "when ",
    ]
    lower = clean.lower()
    if any(p in lower for p in prose_indicators):
        return False
    return True


def _extract_multi_source(cell_text: str) -> List[str]:
    """Extracts multiple source table/column names from a cell that may contain
    newline-separated or space-separated values with blanks in between."""
    parts = cell_text.replace("\n", " ").replace("\xa0", " ").split()
    results = []
    for p in parts:
        p = p.strip().strip("|").strip()
        if p and p not in ("", "|") and _is_db_identifier(p):
            if p not in results:
                results.append(p)
    return results


def _extract_primary_source(cell_text: str) -> str:
    """Returns the first valid DB identifier from a multi-value cell, or empty string."""
    sources = _extract_multi_source(cell_text)
    return sources[0] if sources else ""


class NdMmisDsdInterpreter:
    """
    Parses an ND MMIS DOCX into a structured NdMmisDsd AST.
    """

    def __init__(self, doc_path: Path):
        self.doc_path = Path(doc_path)
        self.doc = docx.Document(str(self.doc_path))

    def interpret(self) -> NdMmisDsd:
        dsd = NdMmisDsd()

        # Estimate total pages from docProps/app.xml
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(str(self.doc_path)) as z:
                if 'docProps/app.xml' in z.namelist():
                    app_xml = z.read('docProps/app.xml')
                    root_app = ET.fromstring(app_xml)
                    for elem in root_app:
                        if 'Pages' in elem.tag and elem.text and elem.text.strip().isdigit():
                            dsd.total_pages_estimated = int(elem.text.strip())
                            break
        except Exception:
            pass

        # Table 0: Report Definition
        if len(self.doc.tables) > 0:
            self._parse_report_definition_table(self.doc.tables[0], dsd)

        # Parse all subsequent tables (Report Specification, Calculations, Totals)
        for t in self.doc.tables[1:]:
            full_text = " ".join(c.text for r in t.rows[:5] for c in r.cells)
            if (
                "Report Specification" in full_text
                or "Report Body" in full_text
                or "Field Label" in full_text
                or "TOTAL OF FINANCIAL TRANSACTIONS" in full_text
                or "DENIED CLAIMS" in full_text
                or "Grand Total" in full_text
            ):
                self._parse_report_specification_table(t, dsd)

        # Deduplicate totals if detailed totals are present
        has_detailed_totals = any(
            any(k in " ".join(t.field_names).lower() for k in ["total for", "total of", "balance due", "processing fees"])
            for t in dsd.totals_and_counts
        )
        if has_detailed_totals:
            dsd.totals_and_counts = [
                t for t in dsd.totals_and_counts
                if not (len(t.field_names) > 1 and all(f in ["TCN", "Billed Amount", "Paid Amount"] for f in t.field_names))
            ]

        return dsd

    def _parse_report_definition_table(self, table, dsd: NdMmisDsd):
        """Parses Table 0 containing Report Definition metadata, Generation, Criteria, Sorts, Output, Retention."""
        current_section = "HEADER"

        for r_idx, r in enumerate(table.rows):
            row_texts = [_get_cell_text(c) for c in r.cells]
            joined_row = " ".join(row_texts).strip()
            first_cell = row_texts[0] if row_texts else ""

            # Check section transitions
            if "Report Generation" in first_cell:
                current_section = "GENERATION"
                continue
            elif "Report Selection Criteria" in first_cell or "Report Selection Criteria" in joined_row:
                current_section = "SELECTION_CRITERIA"
                if "Report Selection Criteria:" in joined_row and "Report Field" not in joined_row and "Change Control:" not in joined_row:
                    pass
                else:
                    continue
            elif "Report Control Breaks" in first_cell or "Sorts" in first_cell or "Control Breaks" in joined_row:
                current_section = "SORTS"
                continue
            elif first_cell.strip() == "Report Output" or "Report Output Format:" in joined_row:
                current_section = "OUTPUT"
                continue
            elif "Security Requirement" in first_cell or "Report Accessed By:" in joined_row:
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
                if "Report Generated From:" in first_cell or "Report Generated From:" in joined_row:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            dsd.definition.generated_from = _get_cell_text(cell)
                elif "Report Calendar Type:" in first_cell or "Report Calendar Type:" in joined_row:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            dsd.definition.calendar_type = _get_cell_text(cell)
                elif "Report Frequency Type:" in first_cell or "Report Frequency Type:" in joined_row:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            txt = _get_cell_text(cell)
                            dsd.definition.frequency_type = txt
                            if "Event Driven" in txt or "UC-" in txt or "Please explain:" in txt:
                                dsd.definition.frequency_explanation = txt

            elif current_section == "SELECTION_CRITERIA":
                unique_cells = []
                for c in r.cells:
                    txt = _get_cell_text(c)
                    if txt and (not unique_cells or unique_cells[-1] != txt):
                        unique_cells.append(txt)

                cleaned = [u for u in unique_cells if u not in (
                    "Report Selection Criteria:", "Report Field", "Report Parameters (Optional)",
                    "Prompt", "Default Prompt Value (Optional)", "Default Prompt Value", "N/A", ""
                )]

                if cleaned:
                    if "Change Control:" in cleaned[0]:
                        continue
                    field_name = cleaned[0]
                    params = None
                    prompt = None
                    default_val = None

                    for item in cleaned[1:]:
                        if item in ("Yes", "No"):
                            prompt = item
                        elif any(k in item for k in ["Where", "IF", "Join", "User enters", "between"]):
                            if params is None:
                                params = item
                            else:
                                default_val = item
                        elif default_val is None and params is not None:
                            default_val = item
                        elif params is None:
                            params = item

                    if field_name and field_name not in ("Report Selection Criteria", "Report Field", "N/A"):
                        dsd.selection_criteria.append(NdSelectionCriterionRow(
                            field_name=field_name,
                            parameters=params,
                            prompt=prompt,
                            default_value=default_val
                        ))

            elif current_section == "SORTS":
                unique_cells = []
                for c in r.cells:
                    txt = _get_cell_text(c)
                    if txt and (not unique_cells or unique_cells[-1] != txt):
                        unique_cells.append(txt)

                if "Sort By:" in joined_row:
                    field_candidates = [t for t in unique_cells if t and t not in ("Ascending", "Descending", "Sort By:", "Change Control:", "")]
                    field_name = field_candidates[0] if field_candidates else ""
                    if field_name and field_name.upper() not in ("N/A", "NONE"):
                        direction = "Ascending"
                        for cell in r.cells:
                            txt = _get_cell_text(cell)
                            if "Descending" in txt and _cell_has_checked(cell):
                                direction = "Descending"
                                break
                            elif "Ascending" in txt and _cell_has_checked(cell):
                                direction = "Ascending"
                        dsd.sorts.append(NdSortRow(field_name=field_name, direction=direction))

                elif "Control Break:" in joined_row:
                    break_type = "Page" if "Page:" in joined_row or "Page" in unique_cells else "Section"
                    field_candidates = [t for t in unique_cells if t and t not in ("Control Break:", "Page:", "Page", "Section:", "Section", "Change Control:", "")]
                    if field_candidates and not all(f.upper() in ("N/A", "NONE") for f in field_candidates):
                        dsd.control_breaks.append(NdControlBreakRow(break_type=break_type, field_names=field_candidates))

                elif "Total:" in joined_row:
                    scope = "Grand" if "Grand:" in joined_row or "Grand" in unique_cells else ("Section" if "Section:" in joined_row or "Section" in unique_cells else "Running")
                    field_candidates = [t for t in unique_cells if t and t not in ("Total:", "Grand:", "Grand", "Section:", "Section", "Running:", "Running", "Change Control:", "")]
                    if field_candidates and not all(f.upper() in ("N/A", "NONE") for f in field_candidates):
                        dsd.totals_and_counts.append(NdTotalCountRow(total_type="Total", scope=scope, field_names=field_candidates))

                elif "Counts:" in joined_row:
                    scope = "Grand" if "Grand:" in joined_row or "Grand" in unique_cells else ("Section" if "Section:" in joined_row or "Section" in unique_cells else "Running")
                    field_candidates = [t for t in unique_cells if t and t not in ("Counts:", "Grand:", "Grand", "Section:", "Section", "Running:", "Running", "Change Control:", "")]
                    if field_candidates and not all(f.upper() in ("N/A", "NONE") for f in field_candidates):
                        dsd.totals_and_counts.append(NdTotalCountRow(total_type="Count", scope=scope, field_names=field_candidates))

            elif current_section == "OUTPUT":
                if "Report Output Format:" in first_cell or "Report Output Format:" in joined_row:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            fmt = _get_cell_text(cell)
                            if fmt and fmt not in dsd.output.output_formats:
                                dsd.output.output_formats.append(fmt)
                elif "Reporting Portal:" in first_cell or "Reporting Portal:" in joined_row:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            dsd.output.portal = _get_cell_text(cell)

            elif current_section == "RETENTION":
                if "Report Retention Type:" in first_cell or "Report Retention Type:" in joined_row:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            dsd.output.retention_type = _get_cell_text(cell)
                elif "Report Output Versions:" in first_cell or "Report Output Versions:" in joined_row:
                    for cell in r.cells[1:]:
                        if _cell_has_checked(cell):
                            txt = _get_cell_text(cell)
                            if "Duration" in txt or any(unit in txt for unit in ["Days", "Months", "Years"]):
                                dsd.output.retention_duration = "7 Years" if "Years" in txt or "7" in txt else txt

        if not dsd.output.output_formats:
            dsd.output.output_formats = ["Excel"]

    def _parse_report_specification_table(self, table, dsd: NdMmisDsd):
        """Parses Specification table containing Presentation Type, Section Headings, Report Body, Totals, Calculations, Footnotes."""
        current_sub = "PRESENTATION"
        current_total_scope = "Section"

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
                current_total_scope = "Section"
                continue
            elif joined_row.strip().lower() == "grand total" or joined_row.startswith("Grand Total"):
                current_total_scope = "Grand"
                continue
            elif "Drill" in joined_row:
                current_sub = "DRILL_THROUGH"
                continue
            elif "Indexing" in joined_row or "Logging" in joined_row or "Index Key" in joined_row:
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

            elif current_sub in ("BODY", "PRESENTATION"):
                if "Field Label" in joined_row or "Change Control" in joined_row or "Report Specification" in joined_row or "Index Key" in joined_row or "Drill" in joined_row:
                    continue

                # Use raw cell positions for structured DSD tables:
                # Cell layout: [CC_flag, FieldType, FieldLabel, Description/SourceTable, SourceTable/SourceColumn, SourceColumn/ProcessingRules, ProcessingRules]
                # The exact slot mapping depends on the number of unique cells.
                raw_cell_texts = [c.text.strip() for c in r.cells]
                unique_cells = []
                for c in r.cells:
                    txt = _get_cell_text(c)
                    if txt and (not unique_cells or unique_cells[-1] != txt):
                        unique_cells.append(txt)

                cleaned = [u for u in unique_cells if u not in ("CC", "Field Type", "Field Label", "Report Specification")]
                if cleaned and (len(cleaned[0]) <= 2 or "FNLDSD" in cleaned[0] or cleaned[0] in ("CC", "N", "M", "U", "D")):
                    cleaned = cleaned[1:]

                if len(cleaned) >= 2:
                    field_type = "Column"
                    field_label = ""
                    field_desc = ""
                    raw_src_table = ""
                    raw_src_col = ""
                    proc_rules = ""

                    if "column" in cleaned[0].lower() or "row" in cleaned[0].lower() or "total" in cleaned[0].lower():
                        field_type = "Total" if "total" in cleaned[0].lower() else ("Row" if "row" in cleaned[0].lower() else "Column")
                        field_label = cleaned[1] if len(cleaned) > 1 else ""

                        slot2 = cleaned[2] if len(cleaned) > 2 else ""
                        slot2_has_db = bool(_extract_multi_source(slot2))
                        slot2_is_table = slot2_has_db and any(
                            t.endswith("_TB") or t.endswith("_TR") or t.endswith("_VW")
                            for t in _extract_multi_source(slot2)
                        )
                        if not slot2_is_table and slot2_has_db and len(_extract_multi_source(slot2)) > 1:
                            if any("_" in t for t in _extract_multi_source(slot2)):
                                slot2_is_table = True

                        if slot2_is_table:
                            field_desc = ""
                            raw_src_table = slot2
                            raw_src_col = cleaned[3] if len(cleaned) > 3 else ""
                            if len(cleaned) > 4:
                                proc_rules = cleaned[4]
                        else:
                            field_desc = slot2
                            raw_src_table = cleaned[3] if len(cleaned) > 3 else ""
                            raw_src_col = cleaned[4] if len(cleaned) > 4 else ""
                            if len(cleaned) > 5:
                                proc_rules = cleaned[5]
                    else:
                        field_label = cleaned[0]
                        slot1 = cleaned[1] if len(cleaned) > 1 else ""
                        slot1_has_db = bool(_extract_multi_source(slot1))
                        slot1_is_table = slot1_has_db and any(
                            t.endswith("_TB") or t.endswith("_TR") or t.endswith("_VW")
                            for t in _extract_multi_source(slot1)
                        )
                        if slot1_is_table:
                            field_desc = ""
                            raw_src_table = slot1
                            raw_src_col = cleaned[2] if len(cleaned) > 2 else ""
                            if len(cleaned) > 3:
                                proc_rules = cleaned[3]
                        else:
                            field_desc = slot1
                            raw_src_table = cleaned[2] if len(cleaned) > 2 else ""
                            raw_src_col = cleaned[3] if len(cleaned) > 3 else ""
                            if len(cleaned) > 4:
                                proc_rules = cleaned[4]

                    # Extract primary and multi-source tables/columns using DB identifier detection
                    all_src_tables = _extract_multi_source(raw_src_table)
                    all_src_cols = _extract_multi_source(raw_src_col)

                    # If source_column looks like a processing rule, move it to proc_rules
                    if raw_src_col and not _is_db_identifier(raw_src_col) and not all_src_cols:
                        if not proc_rules:
                            proc_rules = raw_src_col
                        elif raw_src_col not in proc_rules:
                            proc_rules = raw_src_col + " " + proc_rules
                        raw_src_col = ""

                    # If source_table looks like a processing rule, try to extract DB names from it
                    if raw_src_table and not _is_db_identifier(raw_src_table) and not all_src_tables:
                        if not proc_rules:
                            proc_rules = raw_src_table
                        raw_src_table = ""

                    primary_table = all_src_tables[0] if all_src_tables else _extract_primary_source(raw_src_table)
                    primary_col = all_src_cols[0] if all_src_cols else _extract_primary_source(raw_src_col)

                    if field_label and field_label not in ("Field Label", "Report Body", "N/A", "Grand Total", "Total", "Index Key", "Field Name"):
                        is_total_row = (
                            field_type.lower() == "total"
                            or field_label.lower().startswith("total for ")
                            or field_label.lower().startswith("total of ")
                            or field_label.lower().startswith("grand total")
                            or "balance due" in field_label.lower()
                            or "processing fees" in field_label.lower()
                        )

                        if is_total_row:
                            scope = "Grand" if (current_total_scope == "Grand" or "grand" in field_label.lower()) else "Section"
                            tot_type = "Count" if ("count" in field_label.lower() or "fees" in field_label.lower()) else "Total"
                            clean_lbl = re.sub(r'\s+', ' ', field_label).strip()

                            # Avoid duplicate total entries within the same scope
                            existing = [
                                (t.scope, t.total_type, t.field_names[0] if t.field_names else "")
                                for t in dsd.totals_and_counts
                            ]
                            if (scope, tot_type, clean_lbl) not in existing:
                                dsd.totals_and_counts.append(NdTotalCountRow(
                                    total_type=tot_type,
                                    scope=scope,
                                    field_names=[clean_lbl],
                                    description=field_desc,
                                    processing_rules=proc_rules
                                ))
                        else:
                            dsd.report_body.append(NdReportBodyRow(
                                field_type=field_type,
                                field_label=field_label,
                                field_description=field_desc,
                                source_table=primary_table,
                                source_column=primary_col,
                                source_tables=all_src_tables,
                                source_columns=all_src_cols,
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
