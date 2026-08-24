import pytest
from pathlib import Path
from app.domain.cognos_models import (
    ReportDefinition,
    ReportMetadata,
    SpecialProcessingItem,
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
from app.cognos.rules.sql_generator import DeterministicSqlGenerator
from app.services.dsd_snapshot_resolver import DSDSnapshotResolver
from app.cognos.schema.nh_mmis_dsd_models import (
    NhMmisDsd,
    ReportDefinition as DsdReportDefinition,
    ReportSpecialProcessingRow,
)


def test_feature_detection_special_processing():
    """Verify has_special_processing is extracted when special processing items exist."""
    rd = ReportDefinition(
        special_processing=[
            SpecialProcessingItem(
                use_case="Special Processing",
                source_table="P_RPT_CLDI_TERM_TB",
                source_column="P_REVLDTN_STAT_CD",
                lookup_table="R_VV_TB",
                lookup_code_column="R_VV_CD",
                lookup_description_column="R_VV_SHORT_DESC",
                lookup_domain="P_REVLDTN_STAT_CD",
                raw_rule_text="If a column in P_RPT_CLDI_TERM_TB contains a code value, for example columns ending with _CD such as P_REVLDTN_STAT_CD, the corresponding description can be retrieved from R_VV_TB."
            )
        ]
    )
    reqs = [
        CognosRequirement(
            requirement_id="REQ-PRV027-SPEC-001",
            category=RequirementCategory.SPECIAL_PROCESSING,
            field="P_REVLDTN_STAT_CD",
            requirement_text="Special processing: Translate code column 'P_REVLDTN_STAT_CD' to description via R_VV_TB.R_VV_SHORT_DESC",
        )
    ]
    features = ReportFeatures.extract(reqs, rd)
    assert features.has_special_processing is not None
    assert features.has_special_processing.feature_name == "has_special_processing"
    assert features.has_special_processing.source_section == "Report Special Processing"
    assert "P_REVLDTN_STAT_CD" in str(features.has_special_processing.semantic_evidence)


def test_empty_special_processing_not_detected():
    """Verify has_special_processing is None when section is empty."""
    rd = ReportDefinition(special_processing=[])
    reqs = []
    features = ReportFeatures.extract(reqs, rd)
    assert features.has_special_processing is None


def test_pattern_discovery_special_processing():
    """Verify SPECIAL_PROCESSING_VALIDATION pattern is discovered."""
    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="PRV-INT-027", report_title="Provider Terminations"),
        special_processing=[
            SpecialProcessingItem(
                source_table="P_RPT_CLDI_TERM_TB",
                source_column="P_REVLDTN_STAT_CD",
                lookup_table="R_VV_TB",
                lookup_code_column="R_VV_CD",
                lookup_description_column="R_VV_SHORT_DESC",
                lookup_domain="P_REVLDTN_STAT_CD",
            )
        ]
    )
    reqs = [
        CognosRequirement(
            requirement_id="REQ-001",
            category=RequirementCategory.SPECIAL_PROCESSING,
            field="P_REVLDTN_STAT_CD",
            requirement_text="Special processing code lookup",
        )
    ]
    report = discover_applicable_patterns(reqs, rd)
    pattern_names = [p.pattern for p in report.generated]
    assert MethodologyPattern.SPECIAL_PROCESSING_VALIDATION in pattern_names


def test_scenario_expander_special_processing():
    """Verify ScenarioExpander produces detailed test case for SPECIAL_PROCESSING_VALIDATION."""
    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="PRV-INT-027", report_title="Provider Terminations"),
        special_processing=[
            SpecialProcessingItem(
                source_table="P_RPT_CLDI_TERM_TB",
                source_column="P_REVLDTN_STAT_CD",
                lookup_table="R_VV_TB",
                lookup_code_column="R_VV_CD",
                lookup_description_column="R_VV_SHORT_DESC",
                lookup_domain="P_REVLDTN_STAT_CD",
            )
        ],
        report_fields=[
            ReportField(
                business_label="Reval Stat Cd",
                source_table="P_RPT_CLDI_TERM_TB",
                source_column="P_REVLDTN_STAT_CD",
            )
        ]
    )
    req_set = RequirementSet(
        report_id="PRV-INT-027",
        requirements=[
            CognosRequirement(
                requirement_id="REQ-PRV027-SPEC-001",
                category=RequirementCategory.SPECIAL_PROCESSING,
                field="P_REVLDTN_STAT_CD",
                requirement_text="Code-to-description lookup for P_REVLDTN_STAT_CD via R_VV_TB",
            )
        ],
    )
    expander = ScenarioExpander(rd, req_set)
    patterns = discover_applicable_patterns(req_set.requirements, rd)
    sp_pattern = next(p for p in patterns.generated if p.pattern == MethodologyPattern.SPECIAL_PROCESSING_VALIDATION)
    
    cases = expander._expand_special_processing(sp_pattern)
    assert len(cases) == 1
    tc = cases[0]
    assert tc.category == "Special Processing Validation"
    assert "P_REVLDTN_STAT_CD" in tc.test_case_title
    assert "PRV-INT-027" in tc.test_case_title
    assert "R_VV_TB" in tc.objective
    assert "P_REVLDTN_STAT_CD" in tc.test_steps
    assert "R_VV_SHORT_DESC" in tc.test_steps
    assert "R_VV_DOMAIN_NAME = 'P_REVLDTN_STAT_CD'" in tc.test_steps
    assert tc.source_section == "Report Special Processing"
    assert tc.lookup_table == "R_VV_TB"
    assert tc.lookup_code_column == "R_VV_CD"
    assert tc.lookup_description_column == "R_VV_SHORT_DESC"
    assert tc.lookup_domain == "P_REVLDTN_STAT_CD"


def test_sql_generation_special_processing():
    """Verify DeterministicSqlGenerator builds exact code-to-description query."""
    rd = ReportDefinition(
        metadata=ReportMetadata(report_id="PRV-INT-027"),
        special_processing=[
            SpecialProcessingItem(
                source_table="P_RPT_CLDI_TERM_TB",
                source_column="P_REVLDTN_STAT_CD",
                lookup_table="R_VV_TB",
                lookup_code_column="R_VV_CD",
                lookup_description_column="R_VV_SHORT_DESC",
                lookup_domain="P_REVLDTN_STAT_CD",
            )
        ]
    )
    req_set = RequirementSet(
        report_id="PRV-INT-027",
        requirements=[
            CognosRequirement(
                requirement_id="REQ-PRV027-SPEC-001",
                category=RequirementCategory.SPECIAL_PROCESSING,
                field="P_REVLDTN_STAT_CD",
                requirement_text="Code lookup",
            )
        ]
    )
    expander = ScenarioExpander(rd, req_set)
    patterns = discover_applicable_patterns(req_set.requirements, rd)
    cases = expander.expand(patterns)
    sp_tc = next(tc for tc in cases if tc.category == "Special Processing Validation")
    
    assert sp_tc.sql_status == "AVAILABLE"
    assert "SELECT" in sp_tc.validation_sql
    assert "p.P_REVLDTN_STAT_CD" in sp_tc.validation_sql
    assert "r.R_VV_SHORT_DESC" in sp_tc.validation_sql
    assert "FROM P_RPT_CLDI_TERM_TB p" in sp_tc.validation_sql
    assert "LEFT JOIN R_VV_TB r" in sp_tc.validation_sql
    assert "ON p.P_REVLDTN_STAT_CD = r.R_VV_CD" in sp_tc.validation_sql
    assert "r.R_VV_DOMAIN_NAME = 'P_REVLDTN_STAT_CD'" in sp_tc.validation_sql
    assert "match R_VV_SHORT_DESC from R_VV_TB" in sp_tc.expected_validation


def test_dsd_snapshot_resolver_special_processing():
    """Verify DSDSnapshotResolver resolves targeted metadata for SPECIAL_PROCESSING_VALIDATION."""
    dsd = NhMmisDsd(
        report_definition=DsdReportDefinition(
            client_report_id="PRV-INT-027",
            report_title="Provider Terminations",
            source_page=1,
            source_document="PRV-INT-027.docx",
        ),
        special_processing=[
            ReportSpecialProcessingRow(
                source_table="P_RPT_CLDI_TERM_TB",
                source_column="P_REVLDTN_STAT_CD",
                lookup_table="R_VV_TB",
                lookup_code_column="R_VV_CD",
                lookup_description_column="R_VV_SHORT_DESC",
                lookup_domain="P_REVLDTN_STAT_CD",
                raw_rule_text="Code lookup via R_VV_TB",
                source_page=1,
                source_document="PRV-INT-027.docx",
            )
        ],
    )
    resolver = DSDSnapshotResolver(Path("."))
    ev = resolver.resolve(dsd, "SPECIAL_PROCESSING_VALIDATION", test_case_id="PRV-INT-027-SPEC-01")
    assert ev is not None
    assert ev.section == "Report Special Processing"
    assert ev.evidence_scope == "REPORT_SPECIAL_PROCESSING"
    assert "Report Special Processing • Special Processing" in ev.description
