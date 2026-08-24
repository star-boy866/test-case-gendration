import pytest
from pathlib import Path
from app.services.dsd_snapshot_resolver import DSDSnapshotResolver
from app.cognos.schema.nh_mmis_dsd_models import (
    NhMmisDsd,
    ReportDefinition,
    Layout,
    ReportSpecificationRow,
)


def test_dsd_snapshot_resolver_layout_validation_full_page():
    """Verify DSDSnapshotResolver resolves FULL_REPORT_LAYOUT scope and description for LAYOUT_VALIDATION."""
    dsd = NhMmisDsd(
        report_definition=ReportDefinition(
            client_report_id="PRV-INT-027",
            report_title="Provider Terminations",
            source_page=1,
            source_document="PRV-INT-027.docx",
        ),
        layout=Layout(
            file_name="PRV_INT_027",
            source_page=2,
            source_document="PRV-INT-027.docx",
        ),
        report_specification=[
            ReportSpecificationRow(
                business_label="Prov ID",
                source_table="P_RPT_CLDI_TERM_TB",
                source_column="P_CURR_ALT_ID",
                source_page=2,
                source_document="PRV-INT-027.docx",
            ),
            ReportSpecificationRow(
                business_label="MMIS Lic Cert End Date",
                source_table="P_RPT_CLDI_TERM_TB",
                source_column="P_LIC_CERT_END_DT",
                source_page=2,
                source_document="PRV-INT-027.docx",
            ),
        ],
    )
    resolver = DSDSnapshotResolver(Path("."))
    
    # Even when target_labels or source_column is passed, LAYOUT_VALIDATION must remain FULL_REPORT_LAYOUT
    ev = resolver.resolve(
        dsd,
        "LAYOUT_VALIDATION",
        target_labels={"mmis lic cert end date"},
        source_column="P_LIC_CERT_END_DT",
        test_case_id="PRV-INT-027-LAY-01",
    )
    
    assert ev is not None
    assert ev.section == "Report Layout"
    assert ev.evidence_scope == "FULL_REPORT_LAYOUT"
    assert ev.evidence_id == "snapshot_REPORT_LAYOUT_FULL"
    assert ev.target_field == ""
    assert ev.source_text == "Report Layout • Full Page"
    assert ev.page_number == 2
    assert "Report Layout • Full Page" in ev.description
    assert ev.description == "Source DSD snapshot — Page 2 • Report Layout • Full Page"
