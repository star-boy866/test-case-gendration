"""
Cognos UT Test Case Generation Pipeline — OVERHAULED.

End-to-end orchestration:

    DOCX
     ↓
    cognos_docx_parser (DOCX → parsed sections + tables)
     ↓
    Requirement Extractor (metadata + selection + sort + control breaks)
     ↓
    Column Extractor (Report Body table → ReportField with source columns)
     ↓
    Spec Table Extractor (Report Spec table → section header fields)
     ↓
    Duplicate Detector
     ↓
    Rule Engine (ReportDefinition → detailed test cases)
     ↓
    Test Case Builder (ID assignment + ordering)
     ↓
    Test Case Validator
     ↓
    Coverage Analyzer
     ↓
    Final TestSuite

The rule engine is the core — it generates test cases directly from the
ReportDefinition model, not from individual requirements. This produces
reference-quality detailed test cases with full source traceability.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import RequirementSet
from app.domain.cognos_test_case import TestSuite
from app.domain.reporting_context import FinalReportContext

from app.services.canonical_parser import parse_canonical_docx
from app.cognos.extraction.dsd_interpreter import interpret_dsd
from app.cognos.extraction.xml_parser import parse_cognos_xml
from app.cognos.validation.traceability_engine import TraceabilityEngine
from app.cognos.rules import (
    generate_all_test_cases,
    detect_and_mark_duplicates,
    assign_test_case_ids,
    validate_test_cases,
)
from app.cognos.validation.coverage_analyzer import (
    compute_coverage,
    build_traceability_matrix,
    build_quality_report,
)


class PipelineResult:
    """Complete output of the Cognos UT generation pipeline."""

    def __init__(
        self,
        report_definition: ReportDefinition,
        requirement_set: RequirementSet,
        test_suite: TestSuite,
        final_report_context: FinalReportContext | None = None,
    ):
        self.report_definition = report_definition
        self.requirement_set = requirement_set
        self.test_suite = test_suite
        self.final_report_context = final_report_context

    def to_dict(self) -> dict:
        return {
            "report_definition": self.report_definition.model_dump(),
            "requirement_set": self.requirement_set.model_dump(),
            "test_suite": self.test_suite.model_dump(),
        }


def _build_legacy_report_definition(req_set: RequirementSet, source_document_name: str) -> ReportDefinition:
    report_def = ReportDefinition(source_document=source_document_name)
    report_def.metadata.report_id = req_set.report_id
    
    from app.domain.cognos_requirement import RequirementCategory
    from app.domain.cognos_models import ReportField, SelectionCriterion
    
    for req in req_set.requirements:
        if req.category == RequirementCategory.REPORT_TITLE:
            report_def.metadata.report_title = req.requirement_text
        elif req.category == RequirementCategory.REPORT_DESCRIPTION:
            report_def.metadata.report_description = req.requirement_text
        elif req.category == RequirementCategory.COLUMN:
            f = ReportField(
                field_name=req.field,
                business_label=req.business_label,
                description=req.description or req.requirement_text,
                source_table=req.source_table,
                source_logic_type=req.source_logic_type,
                processing_rule=req.processing_rule,
                formatting_rule=req.formatting_rule
            )
            report_def.report_fields.append(f)
        elif req.category == RequirementCategory.PARAMETER:
            c = SelectionCriterion(
                field=req.field,
                parameter_name=req.business_label,
                description=req.description or req.requirement_text
            )
            report_def.selection_criteria.append(c)

    return report_def

def run_cognos_pipeline(
    docx_path: str | Path,
    xml_path: str | Path | None = None,
    source_document_name: str | None = None,
    target_report_id: str | None = None,
) -> PipelineResult:
    """
    Run the complete Cognos UT test case generation pipeline.

    Args:
        docx_path: Path to the Cognos Report Definition DOCX file.
        source_document_name: Name of the source document for traceability.

    Returns:
        FinalReportContext containing the report definition, requirements,
        generated test suite, and optional traceability result.
    """
    path = Path(docx_path)
    if source_document_name is None:
        source_document_name = path.name

    all_warnings: list[str] = []

    # --- Stage 1: Parse DOCX via Canonical Document Model ---
    canonical_doc = parse_canonical_docx(path)
    
    # --- Stage 2: Schema-driven DSD Interpreter ---
    req_set = interpret_dsd(canonical_doc, source_document_name)
    all_warnings.extend(req_set.warnings)
    
    # --- Stage 2.5: Build backwards-compatible ReportDefinition ---
    report_def = _build_legacy_report_definition(req_set, source_document_name)


    # --- Stage 3: Deduplicate requirements ---
    dedup_messages = detect_and_mark_duplicates(req_set)
    all_warnings.extend(dedup_messages)

    # --- Stage 4: Generate test cases via generic rule engine ---
    test_cases = generate_all_test_cases(report_def, req_set)

    # --- Stage 5: Assign IDs and sort ---
    test_cases = assign_test_case_ids(test_cases, report_def.metadata.report_id)

    # --- Stage 5.5: Back-populate mapped test case IDs onto requirements ---
    req_map = {r.requirement_id: r for r in req_set.requirements}
    for tc in test_cases:
        req_list = tc.requirement_ids if tc.requirement_ids else ([tc.requirement_id] if tc.requirement_id else [])
        for req_id in req_list:
            if req_id in req_map:
                if tc.test_case_id not in req_map[req_id].mapped_test_case_ids:
                    req_map[req_id].mapped_test_case_ids.append(tc.test_case_id)

    # --- Stage 6: Validate test cases ---
    test_cases, validation_warnings = validate_test_cases(test_cases)
    all_warnings.extend(validation_warnings)

    # --- Stage 7: Compute coverage ---
    coverage = compute_coverage(req_set, test_cases, report_def)

    # --- Stage 8: Build traceability matrix ---
    traceability = build_traceability_matrix(req_set, test_cases)

    # --- Stage 9: Build quality report ---
    quality_report = build_quality_report(report_def, req_set)

    # --- Stage 10: Assemble test suite ---
    test_suite = TestSuite(
        report_id=report_def.metadata.report_id,
        report_title=report_def.metadata.report_title,
        test_cases=test_cases,
        coverage=coverage,
        quality_report=quality_report,
        traceability_matrix=traceability,
        generation_warnings=all_warnings,
    )
    test_suite.compute_summary()

    # --- Stage 11: Generate Traceability if XML is provided ---
    traceability_result = None
    if xml_path:
        try:
            xml_model = parse_cognos_xml(xml_path)
            trace_engine = TraceabilityEngine(report_def, req_set, xml_model)
            traceability_result = trace_engine.run()
        except Exception as e:
            all_warnings.append(f"Traceability Engine failed: {str(e)}")

    ctx = FinalReportContext(
        report_definition=report_def,
        requirement_set=req_set,
        test_suite=test_suite,
        traceability_result=traceability_result,
    )

    return PipelineResult(
        report_definition=report_def,
        requirement_set=req_set,
        test_suite=test_suite,
        final_report_context=ctx,
    )
