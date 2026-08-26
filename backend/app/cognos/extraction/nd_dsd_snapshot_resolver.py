"""
North Dakota DSD Snapshot Resolver.

Produces SOURCE_DSD_SNAPSHOT evidence references for North Dakota MMIS DSD
test cases, mapping canonical methodology patterns to authoritative ND sections,
pages, scopes, and target fields.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Set

from app.domain.cognos_test_case import EvidenceReference
from app.cognos.extraction.nd_mmis_dsd_models import NdMmisDsd

logger = logging.getLogger(__name__)


class NdDsdSnapshotResolver:
    """
    Resolves SOURCE_DSD_SNAPSHOT evidence references for North Dakota DSDs.
    """

    SUPPORTED = {
        "REPORT_NAME_DESCRIPTION_VALIDATION",
        "REPORT_HEADER_VALIDATION",
        "REPORT_SECTION_HEADING_VALIDATION",
        "SELECTION_CRITERIA_VALIDATION",
        "LABEL_VALIDATION",
        "LAYOUT_VALIDATION",
        "LOOKUP_VALIDATION",
        "OUTPUT_DELIVERY_VALIDATION",
        "SCRIPT_OUTPUT_VALIDATION",
        "SCHEDULED_EXECUTION_VALIDATION",
        "SORT_VALIDATION",
        "DUPLICATE_VALIDATION",
        "DB_REPORT_DATA_VALIDATION",
        "DATE_FORMAT_VALIDATION",
        "CONTROL_BREAK_VALIDATION",
        "DB_COUNT_VALIDATION",
        "NO_DATA_VALIDATION",
    }

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir

    def resolve(
        self,
        dsd: NdMmisDsd,
        methodology: str,
        target_labels: Set[str] | None = None,
        source_column: str | None = None,
        test_case_id: str = "",
    ) -> Optional[EvidenceReference]:
        """
        Produce a SOURCE_DSD_SNAPSHOT EvidenceReference for an ND test case.
        """
        try:
            if methodology not in self.SUPPORTED:
                return None

            doc_name = dsd.definition.report_name or "ND DSD"
            m = methodology

            target_field_val = ""
            if target_labels:
                target_field_val = next(iter(target_labels))
            elif source_column:
                target_field_val = source_column

            section_name = "Report Definition"
            source_page = 1
            source_pages = [1]
            page_display = "1"
            evidence_scope = "Report Specification"

            if m == "REPORT_NAME_DESCRIPTION_VALIDATION":
                section_name = "Report Definition"
                source_page = 1
                source_pages = [1]
                page_display = "1"
                evidence_scope = "REPORT_DEFINITION_METADATA"
                target_field_val = target_field_val or (dsd.definition.report_id or "Report Metadata")

            elif m == "REPORT_HEADER_VALIDATION":
                section_name = "Report Layout"
                source_page = 6
                source_pages = [6]
                page_display = "6"
                evidence_scope = "REPORT_HEADER"
                target_field_val = target_field_val or "Report Header"

            elif m == "REPORT_SECTION_HEADING_VALIDATION":
                section_name = "Report Section Heading"
                source_page = 8
                source_pages = [8]
                page_display = "8"
                evidence_scope = "REPORT_SECTION_HEADING"
                target_field_val = target_field_val or "Line of Business"

            elif m == "SELECTION_CRITERIA_VALIDATION":
                section_name = "Report Selection Criteria"
                source_page = 2
                source_pages = [2]
                page_display = "2"
                evidence_scope = "REPORT_SELECTION_CRITERIA"
                target_field_val = target_field_val or "Selection Criteria"

            elif m == "LAYOUT_VALIDATION":
                section_name = "Report Layout"
                source_page = 6
                source_pages = [6]
                page_display = "6"
                evidence_scope = "FULL_REPORT_LAYOUT"
                target_field_val = "Full Report Layout"

            elif m == "LABEL_VALIDATION":
                section_name = "Report Body"
                evidence_scope = "Column Labels"
                target_field_val = target_field_val or "Report Body Columns"
                col_count = len(dsd.report_body) if dsd.report_body else 30
                if col_count > 15:
                    source_pages = [8, 9]
                    page_display = "8–9"
                    source_page = 8
                else:
                    source_pages = [8]
                    page_display = "8"
                    source_page = 8

            elif m == "SORT_VALIDATION":
                section_name = "Report Control Breaks, Totals, Counts, and Sorts"
                source_page = 2
                source_pages = [2]
                page_display = "2"
                evidence_scope = "Report Control Breaks, Totals, Counts, and Sorts"
                if not target_field_val and dsd.sorts:
                    target_field_val = dsd.sorts[0].field_name

            elif m == "OUTPUT_DELIVERY_VALIDATION":
                section_name = "Report Output"
                source_page = 3
                source_pages = [3]
                page_display = "3"
                evidence_scope = "Distribution & Portal"
                target_field_val = target_field_val or (dsd.output.portal or "EDMS")

            elif m == "SCRIPT_OUTPUT_VALIDATION":
                if "retention" in test_case_id.lower() or "02" in test_case_id:
                    section_name = "Report Retention"
                    source_page = 4
                    source_pages = [4]
                    page_display = "4"
                    evidence_scope = "Report Retention"
                    target_field_val = target_field_val or "7 Years"
                else:
                    section_name = "Report Output"
                    source_page = 3
                    source_pages = [3]
                    page_display = "3"
                    evidence_scope = "Report Output Format"
                    target_field_val = target_field_val or "Excel"

            elif m == "SCHEDULED_EXECUTION_VALIDATION":
                section_name = "Report Generation"
                source_page = 2
                source_pages = [2]
                page_display = "2"
                evidence_scope = "REPORT_FREQUENCY_SCHEDULING"
                target_field_val = target_field_val or (dsd.definition.frequency_type or "Event Driven")

            elif m in ("LOOKUP_VALIDATION", "DB_REPORT_DATA_VALIDATION", "DATE_FORMAT_VALIDATION", "DUPLICATE_VALIDATION"):
                if m == "LOOKUP_VALIDATION" and target_field_val and "business" in target_field_val.lower():
                    section_name = "Report Section Heading"
                    source_page = 8
                    source_pages = [8]
                    page_display = "8"
                    evidence_scope = "REPORT_SECTION_HEADING"
                else:
                    section_name = "Report Body"
                    source_page = 8
                    source_pages = [8]
                    page_display = "8"
                    evidence_scope = target_field_val or "Field Specification"

            else:
                section_name = "Report Definition"
                source_page = 1
                source_pages = [1]
                page_display = "1"
                evidence_scope = "Source Specification"

            page_label = f"Page {page_display}" if page_display else f"Page {source_page}"
            description = f"Source DSD snapshot — {page_label} • {section_name} • {evidence_scope}"
            ev_id = "REPORT_LAYOUT_FULL" if m == "LAYOUT_VALIDATION" else f"{test_case_id}_{m[:6]}"

            return EvidenceReference(
                evidence_id=f"snapshot_{ev_id}",
                evidence_type="SOURCE_DSD_SNAPSHOT",
                section=section_name,
                page_number=source_page,
                source_pages=source_pages,
                page_display=page_display,
                description=description,
                document_name=doc_name,
                source_document_id="",
                source_document_url="",
                snapshot_path="",
                snapshot_url="",
                source_text=f"{section_name} • {evidence_scope}",
                evidence_scope=evidence_scope,
                target_field="" if m == "LAYOUT_VALIDATION" else target_field_val,
                methodology=m,
            )

        except Exception as exc:
            logger.warning(
                "NdDsdSnapshotResolver: failed for tc=%s method=%s: %s",
                test_case_id, methodology, exc,
            )
            return None
