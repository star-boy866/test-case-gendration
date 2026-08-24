import pytest
from pathlib import Path
from app.domain.cognos_models import (
    ReportDefinition,
    ReportMetadata,
    LayoutDefinition,
    LayoutElement,
    SectionHeadingDefinition,
    ReportField,
    SourceReference,
)
from app.domain.cognos_requirement import (
    CognosRequirement,
    RequirementSet,
    RequirementCategory,
    RequirementConfidence,
    ReportFeatures,
)
from app.cognos.rules.scenario_patterns import (
    MethodologyPattern,
    discover_applicable_patterns,
)
from app.cognos.rules.scenario_expander import ScenarioExpander
from app.cognos.rules.scenario_composer import ScenarioComposer
from app.services.dsd_snapshot_resolver import DSDSnapshotResolver
from app.cognos.schema.nh_mmis_dsd_models import (
    NhMmisDsd,
    ReportDefinition as DsdReportDefinition,
    Layout as DsdLayout,
    ReportSectionHeadingRow,
)


def test_feature_detection_report_header():
    """Verify has_report_header is extracted when header elements/metadata exist."""
    meta = ReportMetadata(
        report_id="PRV-INT-027",
        report_title="Provider License Terminations",
        division_department="Department of Health and Human Services",
    )
    layout = LayoutDefinition(
        header_elements=[
            LayoutElement(element_name="Report ID: PRV-INT-027"),
            LayoutElement(element_name="File Name: PRV_INT_027.csv"),
            LayoutElement(element_name="Department of Health and Human Services"),
        ]
    )
    rd = ReportDefinition(metadata=meta, layout=layout)
    reqs = [
        CognosRequirement(
            requirement_id="REQ-PRV027-HDR-001",
            category=RequirementCategory.HEADER,
            requirement_text="Report header must show Report ID PRV-INT-027 and Department DHHS",
        )
    ]
    features = ReportFeatures.extract(reqs, rd)
    assert features.has_report_header is not None
    assert features.has_report_header.feature_name == "has_report_header"
    assert features.has_report_header.source_section == "Report Layout"
    assert "PRV-INT-027" in str(features.has_report_header.semantic_evidence)


def test_feature_detection_section_headings():
    """Verify has_report_section_headings is extracted when section headings exist."""
    rd = ReportDefinition(
        section_headings=[
            SectionHeadingDefinition(
                section_label="File Name",
                section_description="The input file name.",
                section_processing_rules="P_RPT_CLDI_TERM_TB.G_FILE_NAM",
            ),
            SectionHeadingDefinition(
                section_label="Total",
                section_description="Total records processed.",
                section_processing_rules="Count records",
            ),
        ]
    )
    reqs = [
        CognosRequirement(
            requirement_id="REQ-PRV027-SEC-001",
            category=RequirementCategory.SECTION_HEADING,
            field="File Name",
            requirement_text="Report section heading 'File Name': The input file name.",
        )
    ]
    features = ReportFeatures.extract(reqs, rd)
    assert features.has_report_section_headings is not None
    assert features.has_report_section_headings.feature_name == "has_report_section_headings"
    assert features.has_report_section_headings.source_section == "Report Section Heading"


def test_empty_section_headings_not_detected():
    """Verify has_report_section_headings is None when no section headings exist."""
    rd = ReportDefinition(section_headings=[])
    reqs = []
    features = ReportFeatures.extract(reqs, rd)
    assert features.has_report_section_headings is None


def test_pattern_discovery():
    """Verify REPORT_HEADER_VALIDATION and REPORT_SECTION_HEADING_VALIDATION patterns apply."""
    meta = ReportMetadata(report_id="PRV-INT-027", report_title="Provider Terminations")
    rd = ReportDefinition(
        metadata=meta,
        layout=LayoutDefinition(header_elements=[LayoutElement(element_name="Report ID: PRV-INT-027")]),
        section_headings=[SectionHeadingDefinition(section_label="File Name", section_description="Input file")],
    )
    reqs = [
        CognosRequirement(requirement_id="REQ-001", category=RequirementCategory.HEADER, requirement_text="Header ID"),
        CognosRequirement(requirement_id="REQ-002", category=RequirementCategory.SECTION_HEADING, field="File Name", requirement_text="Section heading File Name"),
    ]
    report = discover_applicable_patterns(reqs, rd)
    pattern_names = [p.pattern for p in report.generated]
    assert MethodologyPattern.REPORT_HEADER_VALIDATION in pattern_names
    assert MethodologyPattern.REPORT_SECTION_HEADING_VALIDATION in pattern_names


def test_scenario_expander_report_header():
    """Verify ScenarioExpander produces detailed test case for REPORT_HEADER_VALIDATION."""
    meta = ReportMetadata(
        report_id="PRV-INT-027",
        report_title="Provider Terminations",
        division_department="DHHS",
    )
    layout = LayoutDefinition(
        header_elements=[
            LayoutElement(element_name="Report ID: PRV-INT-027"),
            LayoutElement(element_name="File Name: PRV_INT_027.csv"),
        ]
    )
    rd = ReportDefinition(metadata=meta, layout=layout)
    req_set = RequirementSet(
        report_id="PRV-INT-027",
        requirements=[
            CognosRequirement(
                requirement_id="REQ-PRV027-HDR-001",
                category=RequirementCategory.HEADER,
                requirement_text="Report header displays Report ID and Title",
            )
        ],
    )
    expander = ScenarioExpander(rd, req_set)
    patterns = discover_applicable_patterns(req_set.requirements, rd)
    header_pattern = next(p for p in patterns.generated if p.pattern == MethodologyPattern.REPORT_HEADER_VALIDATION)
    
    cases = expander._expand_report_header(header_pattern)
    assert len(cases) == 1
    tc = cases[0]
    assert tc.category == "Report Header Validation"
    assert "PRV-INT-027" in tc.test_case_title
    assert "DSD-defined report header fields" in tc.expected_result
    assert "Report ID: PRV-INT-027" in tc.test_steps
    assert tc.source_section == "Report Layout"
    assert len(tc.evidence_requirements) >= 1
    assert tc.evidence_requirements[0].evidence_type == "REPORT"


def test_scenario_expander_section_heading():
    """Verify ScenarioExpander produces detailed test case for REPORT_SECTION_HEADING_VALIDATION."""
    meta = ReportMetadata(report_id="PRV-INT-027", report_title="Provider Terminations")
    rd = ReportDefinition(
        metadata=meta,
        section_headings=[
            SectionHeadingDefinition(
                section_label="File Name",
                section_description="The input file name.",
                section_processing_rules="P_RPT_CLDI_TERM_TB.G_FILE_NAM",
            ),
            SectionHeadingDefinition(
                section_label="MM/DD/CCYY",
                section_description="Process date.",
                section_processing_rules="P_RPT_CLDI_TERM_TB.G_RPT_PRCS_DT",
            ),
        ],
    )
    req_set = RequirementSet(
        report_id="PRV-INT-027",
        requirements=[
            CognosRequirement(
                requirement_id="REQ-PRV027-SEC-001",
                category=RequirementCategory.SECTION_HEADING,
                field="File Name",
                requirement_text="Report section heading 'File Name'",
            )
        ],
    )
    expander = ScenarioExpander(rd, req_set)
    patterns = discover_applicable_patterns(req_set.requirements, rd)
    sect_pattern = next(p for p in patterns.generated if p.pattern == MethodologyPattern.REPORT_SECTION_HEADING_VALIDATION)
    
    cases = expander._expand_report_section_heading(sect_pattern)
    assert len(cases) == 1
    tc = cases[0]
    assert tc.category == "Report Section Heading Validation"
    assert "File Name" in tc.test_steps
    assert "P_RPT_CLDI_TERM_TB.G_FILE_NAM" in tc.test_steps
    assert "MM/DD/CCYY" in tc.test_steps
    assert tc.source_section == "Report Section Heading"


def test_dsd_snapshot_resolver_header_and_section():
    """Verify DSDSnapshotResolver resolves targeted metadata for REPORT_HEADER and REPORT_SECTION_HEADING."""
    dsd = NhMmisDsd(
        report_definition=DsdReportDefinition(
            client_report_id="PRV-INT-027",
            report_title="Provider Terminations",
            client_division_department="DHHS",
            source_page=2,
            source_document="PRV-INT-027.docx",
        ),
        layout=DsdLayout(
            report_id="PRV-INT-027",
            file_name="PRV_INT_027.csv",
            source_page=2,
        ),
        report_section_headings=[
            ReportSectionHeadingRow(
                section_label="File Name",
                section_description="Input file name",
                section_processing_rules="P_RPT_CLDI_TERM_TB.G_FILE_NAM",
                source_page=3,
                source_document="PRV-INT-027.docx",
            )
        ],
    )
    resolver = DSDSnapshotResolver(Path("."))
    
    # 1. Header resolution
    ev_header = resolver.resolve(dsd, "REPORT_HEADER_VALIDATION", test_case_id="PRV-INT-027-HDR-01")
    assert ev_header is not None
    assert ev_header.section == "Report Layout"
    assert ev_header.evidence_scope == "REPORT_HEADER"
    assert ev_header.target_field == "Report Header"
    assert "Report Layout • Report Header" in ev_header.description

    # 2. Section heading resolution
    ev_sect = resolver.resolve(dsd, "REPORT_SECTION_HEADING_VALIDATION", test_case_id="PRV-INT-027-SEC-01")
    assert ev_sect is not None
    assert ev_sect.section == "Report Section Heading"
    assert ev_sect.evidence_scope == "REPORT_SECTION_HEADING"
    assert ev_sect.target_field == "Report Section Heading"
    assert "Report Section Heading • Section Headings" in ev_sect.description
