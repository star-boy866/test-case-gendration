"""
Selection criteria and parameter extractor.

Extracts report selection criteria, parameters, and prompts from the
"Report Selection Criteria" section of a Cognos report definition.
"""

from __future__ import annotations

import re

from app.domain.cognos_models import SelectionCriterion, SourceReference
from app.services.cognos_docx_parser import CognosParsedDocument


def extract_selection_criteria(
    doc: CognosParsedDocument,
    source_document_name: str = "",
    report_id: str = "",
) -> tuple[list[SelectionCriterion], list[str]]:
    """
    Extract selection criteria from the parsed DOCX.
    Uses semantic template form parsing for NH MMIS Report Definition Template.

    Returns (criteria, warnings).
    """
    criteria: list[SelectionCriterion] = []
    warnings: list[str] = []

    # Iterate over all tables in all sections to find the Report Selection Criteria
    for section in doc.sections:
        for table in section.tables:
            if hasattr(table, 'rows'):
                table_data = [[c.text for c in r.cells] for r in table.rows]
            else:
                table_data = table

            if not table_data:
                continue

            header_idx_field = -1
            header_idx_param = -1
            header_idx_prompt = -1
            
            for row in table_data:
                if not row: continue
                c0_text = row[0].lower().strip() if len(row) > 0 else ""
                
                # Identify headers
                if "report selection criteria:" in c0_text:
                    if header_idx_field == -1:
                        for i, cell in enumerate(row):
                            c_lower = cell.lower().strip()
                            if "report field" in c_lower:
                                header_idx_field = i
                            elif "parameters" in c_lower:
                                header_idx_param = i
                            elif "prompt" in c_lower:
                                header_idx_prompt = i
                        continue # Skip header row

                    if header_idx_field == -1:
                        continue # Header not found yet

                    field_name = row[header_idx_field].strip() if header_idx_field < len(row) else ""
                    if not field_name:
                        continue
                        
                    param_text = row[header_idx_param].strip() if header_idx_param != -1 and header_idx_param < len(row) else ""
                    prompt_text = row[header_idx_prompt].strip().lower() if header_idx_prompt != -1 and header_idx_prompt < len(row) else ""
                    
                    # Regex logic for table.column
                    filter_logic = param_text
                    source_table_column = ""
                    col_matches = re.findall(r'(\w+)\.(\w+)', param_text)
                    if col_matches:
                        source_table_column = f"{col_matches[0][0]}.{col_matches[0][1]}"
                        
                    prompt = False
                    if "\uf0fe yes" in prompt_text or "\u2611 yes" in prompt_text or "yes" in prompt_text.split()[-3:]:
                        prompt = True
                        
                    # "If populated, Prompt must = No" validation
                    if filter_logic and prompt:
                        warnings.append(f"Validation Warning: Selection Criteria '{field_name}' has a populated parameter but Prompt is set to Yes.")
                        
                    criterion = SelectionCriterion(
                        field=field_name,
                        filter_logic=filter_logic,
                        source_table_column=source_table_column,
                        prompt=prompt,
                        source=SourceReference(
                            document_name=source_document_name,
                            section=section.name,
                            page=section.estimated_page,
                        ),
                    )
                    
                    if prompt:
                        criterion.parameter_name = f"Select {field_name}"
                        
                    criteria.append(criterion)

    if not criteria:
        warnings.append("No selection criteria found in the document.")

    return criteria, warnings
