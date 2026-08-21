import re
from typing import Optional, List, Dict, Any

from app.services.cognos_docx_parser import CognosParsedDocument, DocumentSection, ParsedTable, CheckboxState
from app.cognos.schema.nh_mmis_dsd_models import (
    NhMmisDsd,
    ReportDefinition,
    ReportGeneration,
    SelectionCriteria,
    Parameter,
    Sort,
    ControlBreak,
    Total,
    Count,
    Output,
    Retention,
    Layout,
    ReportSpecificationRow
)

def _clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())

class NhMmisDsdInterpreter:
    """
    Deterministically interprets a CognosParsedDocument into the NH MMIS DSD Semantic Contract.
    Extracts the 12 sections as defined in the glossary without relying on LLM logic.
    """
    
    def __init__(self, doc: CognosParsedDocument):
        self.doc = doc
        self.dsd = NhMmisDsd()

    def interpret(self) -> NhMmisDsd:
        self._parse_report_definition()
        self._parse_report_generation()
        self._parse_selection_criteria()
        self._parse_parameters()
        self._parse_sorts_breaks_totals_counts()
        self._parse_output()
        self._parse_retention()
        self._parse_layout()
        self._parse_report_specification()
        return self.dsd

    def _find_table_by_keyword(self, keywords: List[str]) -> Optional[ParsedTable]:
        for table in self.doc.all_parsed_tables:
            text_in_table = " ".join(_clean_text(c.text).lower() for r in table.rows for c in r.cells)
            if all(k in text_in_table for k in keywords):
                return table
        return None

    def _extract_kv_from_table(self, table: ParsedTable, key_mappings: Dict[str, str]) -> Dict[str, Any]:
        """Extract exact key-value pairs based on mappings, along with provenance."""
        result = {}
        for row in table.rows:
            if len(row.cells) >= 2:
                key_text = _clean_text(row.cells[0].text).lower()
                
                def get_cell_value(cell) -> str:
                    c_text = _clean_text(cell.text)
                    c_checkboxes = cell.checkbox_labels
                    
                    has_cbs = len(c_checkboxes) > 0
                    if not has_cbs:
                        return c_text
                        
                    checked_labels = []
                    for cb in c_checkboxes:
                        if cb.get('checked'):
                            checked_labels.append(cb['label'])
                            
                    if not checked_labels:
                        return ""
                    else:
                        if any("other" in L.lower() for L in checked_labels):
                            import re
                            m = re.search(r'Other:\s*([A-Za-z0-9_\-\s]+)', cell.text, re.IGNORECASE)
                            other_text = m.group(1).strip() if m else ""
                            checked_labels = [(L if "other" not in L.lower() else (L + (": " + other_text if other_text else ""))) for L in checked_labels]
                        return " ".join(checked_labels).strip()

                for mapped_key, attribute_name in key_mappings.items():
                    # Handle when key_text starts with the mapped_key, or matches it exactly
                    is_match = (
                        mapped_key == key_text.replace(":", "").strip() or 
                        key_text.startswith(mapped_key + ":") or 
                        key_text.startswith(mapped_key + " :") or 
                        key_text == mapped_key
                    )
                    
                    if is_match:
                        val_text = get_cell_value(row.cells[1])
                        
                        # Prevent falling back to the label itself if it was parsed as the value
                        val_cleaned = val_text.replace(":", "").strip().lower()
                        if val_cleaned == mapped_key.lower():
                            val_text = ""
                            
                        # If cell 1 was empty/label, check subsequent cells in the row
                        if not val_text:
                            for c_idx in range(2, len(row.cells)):
                                candidate_val = get_cell_value(row.cells[c_idx])
                                candidate_cleaned = candidate_val.replace(":", "").strip().lower()
                                if candidate_val and candidate_cleaned != mapped_key.lower():
                                    val_text = candidate_val
                                    break
                                    
                        # If val_text is still empty, perhaps the value was in cell 0 after a colon?
                        if not val_text and ":" in row.cells[0].text:
                            parts = _clean_text(row.cells[0].text).split(":", 1)
                            if len(parts) > 1 and parts[1].strip():
                                val_text = parts[1].strip()

                        # Ensure it's never the literal label again
                        if val_text.lower().replace(":", "").strip() == mapped_key.lower():
                            val_text = ""
                            
                        result[attribute_name] = {
                            "value": val_text,
                            "prov": {
                                "source_document": self.doc.filename,
                                "source_page": table.source_page,
                                "source_section": table.section_name,
                                "table_index": table.table_index,
                                "row_index": row.row_index,
                                "cell_index": 1
                            }
                        }
        return result

    def _parse_report_definition(self):
        table = self._find_table_by_keyword(["report type", "client report id"])
        if not table:
            return

        mappings = {
            "report type": "report_type",
            "client name": "client_name",
            "client report id": "client_report_id",
            "client line of business": "client_lob",
            "client division/department": "client_division_department",
            "report title": "report_title",
            "report description": "report_description",
            "report source type": "report_source_type",
            "report source type component": "report_source_type_component"
        }
        
        extracted = self._extract_kv_from_table(table, mappings)
        if extracted:
            rd = ReportDefinition()
            # Set the first found provenance as the block provenance
            first_prov = list(extracted.values())[0]["prov"]
            rd.source_document = first_prov["source_document"]
            rd.source_page = first_prov["source_page"]
            rd.source_section = first_prov["source_section"]
            rd.table_index = first_prov["table_index"]
            
            for attr, data in extracted.items():
                setattr(rd, attr, data["value"])
            self.dsd.report_definition = rd

    def _parse_report_generation(self):
        table = self._find_table_by_keyword(["report generated by", "report frequency type"])
        if not table:
            return

        mappings = {
            "report generated by": "report_generated_by",
            "report screen tip": "report_screen_tip",
            "report calendar type": "report_calendar_type",
            "report frequency type": "report_frequency_type",
            "if scheduled, select timeframe below": "scheduled_timeframe",
            "other": "other_explain",
            "report data accumulation type": "report_data_accumulation_type",
            "triggered by": "triggered_by"
        }
        
        extracted = self._extract_kv_from_table(table, mappings)
        if extracted:
            rg = ReportGeneration()
            first_prov = list(extracted.values())[0]["prov"]
            rg.source_document = first_prov["source_document"]
            rg.source_page = first_prov["source_page"]
            rg.source_section = first_prov["source_section"]
            rg.table_index = first_prov["table_index"]
            
            for attr, data in extracted.items():
                setattr(rg, attr, data["value"])
            self.dsd.report_generation = rg

    def _parse_selection_criteria(self):
        table = self._find_table_by_keyword(["report selection criteria", "report field"])
        if not table:
            return
        
        # Look for selection criteria rows (ignoring header)
        for row in table.rows:
            if len(row.cells) >= 2:
                col0 = _clean_text(row.cells[0].text).lower()
                if "report selection criteria" in col0 and not "criteria" == col0:
                    # Sometimes the key is in col0 and value in col1
                    val = _clean_text(row.cells[1].text)
                    if val and "report selection criteria" not in val.lower():
                        sc = SelectionCriteria(
                            report_selection_criteria=val,
                            source_document=self.doc.filename,
                            source_page=table.source_page,
                            source_section=table.section_name,
                            table_index=table.table_index,
                            row_index=row.row_index
                        )
                        self.dsd.selection_criteria.append(sc)
                elif "report field" in col0:
                    val = _clean_text(row.cells[1].text)
                    if val and "report field" not in val.lower():
                        # Just attach to the last selection criteria if available
                        if self.dsd.selection_criteria:
                            self.dsd.selection_criteria[-1].report_field = val

    def _parse_parameters(self):
        table = self._find_table_by_keyword(["report parameters"])
        if not table:
            return
            
        for row in table.rows:
            if len(row.cells) >= 2:
                col0 = _clean_text(row.cells[0].text).lower()
                if "report parameters" in col0 or "parameter" in col0:
                    val = _clean_text(row.cells[1].text)
                    if val and "report parameter" not in val.lower():
                        p = Parameter(
                            parameter_description=val,
                            source_document=self.doc.filename,
                            source_page=table.source_page,
                            source_section=table.section_name,
                            table_index=table.table_index,
                            row_index=row.row_index
                        )
                        self.dsd.parameters.append(p)
                elif "prompt" in col0:
                    val = _clean_text(row.cells[1].text).lower()
                    if self.dsd.parameters:
                        self.dsd.parameters[-1].prompt = "yes" in val

    def _parse_sorts_breaks_totals_counts(self):
        table = self._find_table_by_keyword(["sort by", "control break", "total", "count"])
        if not table:
            return

        _NOISE = frozenset([
            "sort by:", "sort by", "control break", "total", "count", "page:", "page",
            "section:", "section", "grand:", "grand", "totals", "counts",
            "report control breaks, totals, counts, and sorts", "ascending", "descending",
            "ascending descending", "ascending\t descending", "ascending  descending",
        ])

        def _first_real_value(cells, start: int = 1) -> str:
            """Find the first non-label, non-noise cell value after 'start'."""
            for cell in cells[start:]:
                txt = _clean_text(cell.text)
                if txt and txt.lower().strip().rstrip(":") not in _NOISE:
                    return txt
            return ""

        def _direction_value(cells) -> str:
            """Extract direction from checkbox labels or text in the rightmost cells."""
            # Look for checkbox labels first
            for cell in cells:
                checked = [cb['label'] for cb in cell.checkbox_labels if cb.get('checked')]
                if checked:
                    return " ".join(checked)
            # Fallback: look for Ascending/Descending text
            for cell in reversed(cells):
                txt = _clean_text(cell.text)
                if "ascending" in txt.lower():
                    return "Ascending"
                if "descending" in txt.lower():
                    return "Descending"
            return ""

        def _level_value(cells) -> str:
            """Extract level/break type from col1 (Page: / Section:)."""
            if len(cells) >= 2:
                txt = _clean_text(cells[1].text).strip().rstrip(":")
                if txt.lower() in ("page", "section", "grand"):
                    return txt.title()
            return ""

        prov_kwargs_base = {
            "source_document": self.doc.filename,
            "source_page": table.source_page,
            "source_section": table.section_name,
            "table_index": table.table_index,
        }

        for row in table.rows:
            if not row.cells:
                continue
            col0 = _clean_text(row.cells[0].text).lower().strip().rstrip(":")
            prov_kwargs = {**prov_kwargs_base, "row_index": row.row_index}

            if col0 in ("sort by",):
                # Multi-col: col0='Sort By:', col1='Sort By:' or blank, col2=field, col4=direction
                val = _first_real_value(row.cells, start=1)
                direction = _direction_value(row.cells)
                if val:
                    self.dsd.sorts.append(Sort(sort_by=val, direction=direction, **prov_kwargs))

            elif col0 in ("control break",):
                # Multi-col: col0='Control Break', col1='Page:'/'Section:', col2=field
                val = _first_real_value(row.cells, start=2)
                level = _level_value(row.cells)
                if not val:
                    # Fallback: try col1 as value (for simple 2-col tables)
                    val = _first_real_value(row.cells, start=1)
                if val:
                    self.dsd.control_breaks.append(ControlBreak(
                        control_break=val, level=level, **prov_kwargs
                    ))

            elif col0 in ("total",):
                val = _first_real_value(row.cells, start=1)
                level = _level_value(row.cells)
                if val:
                    self.dsd.totals.append(Total(total=val, level=level, **prov_kwargs))

            elif col0 in ("count", "counts"):
                val = _first_real_value(row.cells, start=1)
                level = _level_value(row.cells)
                if val:
                    self.dsd.counts.append(Count(count=val, level=level, **prov_kwargs))


    def _parse_output(self):
        table = self._find_table_by_keyword(["report output format"])
        if not table:
            return
            
        mappings = {
            "report output format": "report_output_format",
            "reporting portal": "reporting_portal",
            "report output distribution": "report_output_distribution_groups"
        }
        
        extracted = self._extract_kv_from_table(table, mappings)
        if extracted:
            out = Output()
            first_prov = list(extracted.values())[0]["prov"]
            out.source_document = first_prov["source_document"]
            out.source_page = first_prov["source_page"]
            out.source_section = first_prov["source_section"]
            out.table_index = first_prov["table_index"]
            
            for attr, data in extracted.items():
                setattr(out, attr, data["value"])
            self.dsd.output = out

    def _parse_retention(self):
        table = self._find_table_by_keyword(["report retention type"])
        if not table:
            return
            
        mappings = {
            "report retention type": "report_retention_type",
            "report output versions": "report_output_versions",
            "report run history": "report_run_history_log"
        }
        
        extracted = self._extract_kv_from_table(table, mappings)
        if extracted:
            ret = Retention()
            first_prov = list(extracted.values())[0]["prov"]
            ret.source_document = first_prov["source_document"]
            ret.source_page = first_prov["source_page"]
            ret.source_section = first_prov["source_section"]
            ret.table_index = first_prov["table_index"]
            
            for attr, data in extracted.items():
                setattr(ret, attr, data["value"])
            self.dsd.retention = ret

    def _parse_layout(self):
        table = self._find_table_by_keyword(["enterprise operational reports"])
        if not table:
            return
            
        lay = Layout()
        lay.source_document = self.doc.filename
        lay.source_page = table.source_page
        lay.source_section = table.section_name
        lay.table_index = table.table_index
        
        # Search all cells for layout fields
        full_text = " ".join(_clean_text(c.text) for r in table.rows for c in r.cells)
        
        import re
        id_match = re.search(r"Report ID:\s*([^\n\s]+)", full_text, re.IGNORECASE)
        if id_match:
            lay.report_id = id_match.group(1)
            
        file_match = re.search(r"File Name:\s*([^\n]+)", full_text, re.IGNORECASE)
        if file_match:
            lay.file_name = file_match.group(1).strip()
            
        # The title line is often the second line in the middle cell
        for r in table.rows:
            for c in r.cells:
                lines = [l.strip() for l in c.text.split('\n') if l.strip()]
                if len(lines) >= 3 and "Department of Health" in lines[0]:
                    lay.report_title_line = lines[1]
                    break
                    
        self.dsd.layout = lay

    def _parse_report_specification(self):
        # Look for the Report Body / Report Specification table
        table = self._find_table_by_keyword(["business label", "source table", "processing rules"])
        if not table:
            return
            
        # Find header indices
        header_row = None
        label_idx = -1
        desc_idx = -1
        table_idx = -1
        col_idx = -1
        rules_idx = -1
        
        start_row = 0
        for r_idx, row in enumerate(table.rows):
            texts = [_clean_text(c.text).lower() for c in row.cells]
            if any("business label" in t for t in texts):
                header_row = row
                start_row = r_idx + 1
                for c_idx, text in enumerate(texts):
                    if "business label" in text:
                        label_idx = c_idx
                    elif "field description" in text:
                        desc_idx = c_idx
                    elif "source table" in text:
                        table_idx = c_idx
                    elif "source column" in text and "processing" not in text:
                        col_idx = c_idx
                    elif "processing rules" in text:
                        rules_idx = c_idx
                break
                
        if label_idx == -1:
            return
            
        for row in table.rows[start_row:]:
            cells = row.cells
            if len(cells) <= label_idx:
                continue
                
            label = _clean_text(cells[label_idx].text)
            if not label or label.lower() in ("n/a", "review_required"):
                continue
                
            # Exclude optional empty sections logic per glossary (Chart Footer, etc)
            label_lower = label.lower()
            
            # Filter dummy placeholders that were not filled in
            if "(opt)" in label_lower or "(opt.)" in label_lower:
                table_text = _clean_text(cells[table_idx].text).lower() if len(cells) > table_idx and table_idx != -1 else ""
                col_text = _clean_text(cells[col_idx].text).lower() if len(cells) > col_idx and col_idx != -1 else ""
                if (not table_text or "opt" in table_text or table_text in ("n/a", "none", "blank")) and \
                   (not col_text or "opt" in col_text or col_text in ("n/a", "none", "blank")):
                    continue
            
            if any(x in label_lower for x in ("chart header", "chart footer", "report footnote", "chart footnote")):
                val_text = _clean_text(cells[desc_idx].text) if len(cells) > desc_idx and desc_idx != -1 else ""
                if not val_text or val_text.lower() in ("n/a", "none", "blank"):
                    continue

            rsr = ReportSpecificationRow(
                business_label=label,
                field_description=_clean_text(cells[desc_idx].text) if len(cells) > desc_idx and desc_idx != -1 else "",
                source_table=_clean_text(cells[table_idx].text) if len(cells) > table_idx and table_idx != -1 else "",
                source_column=_clean_text(cells[col_idx].text) if len(cells) > col_idx and col_idx != -1 else "",
                processing_rules=_clean_text(cells[rules_idx].text) if len(cells) > rules_idx and rules_idx != -1 else "",
                source_document=self.doc.filename,
                source_page=table.source_page,
                source_section=table.section_name,
                table_index=table.table_index,
                row_index=row.row_index
            )
            self.dsd.report_specification.append(rsr)
