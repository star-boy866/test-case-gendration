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

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from app.domain.cognos_models import ReportDefinition
from app.domain.cognos_requirement import RequirementSet
from app.domain.cognos_test_case import TestSuite
from app.domain.reporting_context import FinalReportContext

from app.services.cognos_docx_parser import parse_cognos_docx
from app.cognos.extraction.requirement_extractor import extract_requirements
from app.cognos.extraction.xml_parser import parse_cognos_xml
from app.cognos.validation.traceability_engine import TraceabilityEngine
from app.cognos.rules import (
    generate_all_test_cases,
    detect_and_mark_duplicates,
    assign_test_case_ids,
    validate_test_cases,
    order_cognos_test_cases,
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
        job_id: str | None = None,
    ):
        self.report_definition = report_definition
        self.requirement_set = requirement_set
        self.test_suite = test_suite
        self.final_report_context = final_report_context
        self.job_id = job_id

    def to_dict(self) -> dict:
        return {
            "report_definition": self.report_definition.model_dump(),
            "requirement_set": self.requirement_set.model_dump(),
            "test_suite": self.test_suite.model_dump(),
        }


def run_cognos_pipeline(
    docx_path: str | Path,
    xml_path: str | Path | None = None,
    source_document_name: str | None = None,
    target_report_id: str | None = None,
    use_llm_assist: bool = False,
    dsd_profile: str | None = "AUTO",
) -> PipelineResult:
    """
    Run the complete Cognos UT test case generation pipeline.

    Args:
        docx_path: Path to the Cognos Report Definition DOCX file.
        source_document_name: Name of the source document for traceability.
        dsd_profile: Target DSD state profile ('AUTO', 'NH', 'ND', 'AK').

    Returns:
        PipelineResult containing the report definition, requirements,
        generated test suite, and optional traceability result.
    """
    path = Path(docx_path)
    if source_document_name is None:
        source_document_name = path.name

    all_warnings: list[str] = []

    # --- Stage 1 & 2: Schema-driven DSD Interpretation via Profile Dispatcher ---
    from app.cognos.profiles.dsd_profile_dispatcher import dispatch_and_interpret_dsd
    import hashlib

    # Generate a job_id based on filename and contents hash for isolated storage
    job_id = target_report_id or hashlib.md5(str(path.absolute()).encode()).hexdigest()[:8]
    job_dir = Path("jobs") / job_id

    report_def, req_set, dsd = dispatch_and_interpret_dsd(
        docx_path=path,
        source_document_name=source_document_name,
        dsd_profile=dsd_profile,
    )
    all_warnings.extend(req_set.warnings)
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

    # --- Stage 6.1: Semantic Proof Generation (Phase 13D.3: Profile-Aware) ---
    from app.cognos.extraction.nd_mmis_dsd_models import NdMmisDsd
    if isinstance(dsd, NdMmisDsd):
        logger.info("[PIPELINE STAGE 6.1] Semantic DSD Proof skipped for profile ND MMIS (semantic_proof_status = NOT_APPLICABLE_FOR_PROFILE).")
    else:
        from app.services.dsd_semantic_proof_renderer import DSDSemanticProofRenderer, EvidenceTarget
        proof_renderer = DSDSemanticProofRenderer(job_dir / "evidence")
        for tc in test_cases:
            labels = set()
            req_ids = tc.requirement_ids or []
            for rid in req_ids:
                for r in req_set.requirements:
                    if r.requirement_id == rid and r.field:
                        labels.add(r.field.strip().lower())
                        
            target = EvidenceTarget(
                methodology=tc.methodology_pattern or "",
                target_labels=labels,
                source_column=tc.source_column.strip().lower() if tc.source_column else None,
                test_case_id=tc.test_case_id
            )
            proof_ref = proof_renderer.render(dsd, report_def, req_set, target)
            if proof_ref:
                tc.evidence_references = [proof_ref]

    # --- Stage 6.2: Source DSD Snapshot (PHASE 11.3 / PHASE 13C) ---
    # Appends a second evidence reference of type SOURCE_DSD_SNAPSHOT to each
    # test case that already has a semantic proof.  Never replaces the proof.
    # Silently skips when no snapshot data is available.
    from app.cognos.extraction.nd_mmis_dsd_models import NdMmisDsd
    if isinstance(dsd, NdMmisDsd):
        from app.cognos.extraction.nd_dsd_snapshot_resolver import NdDsdSnapshotResolver
        snapshot_resolver = NdDsdSnapshotResolver(job_dir / "evidence")
    else:
        from app.services.dsd_snapshot_resolver import DSDSnapshotResolver
        snapshot_resolver = DSDSnapshotResolver(job_dir / "evidence")
    for tc in test_cases:
        methodology = tc.methodology_pattern or ""
        if not methodology:
            continue

        labels = set()
        req_ids = tc.requirement_ids or []
        for rid in req_ids:
            for r in req_set.requirements:
                if r.requirement_id == rid and r.field:
                    labels.add(r.field.strip().lower())

        snap_ref = snapshot_resolver.resolve(
            dsd=dsd,
            methodology=methodology,
            target_labels=labels,
            source_column=tc.source_column.strip().lower() if tc.source_column else None,
            test_case_id=tc.test_case_id,
        )
        if snap_ref:
            # Guard: ensure both SEMANTIC proof and SOURCE snapshot are retained without duplicate snapshot types
            existing_types = {ev.evidence_type for ev in tc.evidence_references}
            if "SOURCE_DSD_SNAPSHOT" not in existing_types:
                tc.evidence_references.append(snap_ref)

    # --- Stage 6.3: Deterministic SQL Generation & Source Mapping (PHASE 12K) ---
    from app.cognos.rules.sql_generator import DeterministicSqlGenerator
    DeterministicSqlGenerator.enrich_test_cases(test_cases, report_def, req_set)

    # --- Stage 6.5: LLM Assist Layer (Optional) ---
    if use_llm_assist:
        from app.cognos.llm.cognos_llm_service import CognosLLMService
        llm_service = CognosLLMService()
        refined_test_cases = llm_service.refine_test_cases(test_cases, report_def, req_set)
        
        # Deterministic Validation: Ensure LLM did not mutate authoritative facts
        for orig, refined in zip(test_cases, refined_test_cases):
            assert orig.test_case_id == refined.test_case_id, "LLM mutated test_case_id"
            assert orig.requirement_ids == refined.requirement_ids, "LLM mutated requirement_ids"
            assert orig.source_table == refined.source_table, "LLM mutated source_table"
            assert orig.source_column == refined.source_column, "LLM mutated source_column"
            assert orig.evidence_references == refined.evidence_references, "LLM mutated evidence_references"
            
        test_cases = refined_test_cases

    # --- Stage 7: Compute coverage & order test cases ---
    test_cases = order_cognos_test_cases(test_cases)
    
    # Assert unique test case IDs
    tc_ids = [tc.test_case_id for tc in test_cases]
    assert len(tc_ids) == len(set(tc_ids)), f"Duplicate test_case_id found: {[id for id in tc_ids if tc_ids.count(id) > 1]}"

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

    # --- PART 11: HARD ACCEPTANCE ASSERTIONS ---
    active_req_ids = {r.requirement_id for r in req_set.requirements if not r.is_duplicate_of}
    if len(active_req_ids) == 0:
        all_warnings.append("0 requirements found, check your document")
    
    for tc in test_cases:
        req_list = tc.requirement_ids if tc.requirement_ids else ([tc.requirement_id] if tc.requirement_id else [])
        for req_id in req_list:
            if req_id not in active_req_ids:
                raise ValueError(f"Pipeline failed: Test Case {tc.test_case_id} references invalid/missing Requirement ID {req_id}")

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
        job_id=job_id,
        final_report_context=ctx,
    )
