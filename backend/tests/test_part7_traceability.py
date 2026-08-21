import pytest
"""
Integration tests for Part 7 — Traceability and Coverage.
"""

from pathlib import Path
from app.cognos.pipeline import run_cognos_pipeline
from app.domain.cognos_requirement import RequirementCategory

def test_all_tests_have_requirement_links(tmp_path: Path):
    """
    Every generated test case must have requirement_ids populated,
    unless it is specifically flagged as a fallback header test.
    """
    root_dir = Path(__file__).parent / "fixtures" / "golden_sources"
    doc_path = root_dir / "Service Authorization Part E_CR18140_V0.1 1.docx"
    result = run_cognos_pipeline(doc_path)
    
    test_cases = result.test_suite.test_cases
    assert len(test_cases) > 0
    
    for tc in test_cases:
        if tc.category == "Header":
            continue
        assert len(tc.requirement_ids) > 0, f"Test {tc.test_case_id} has empty requirement_ids"
        assert tc.requirement_id != "", f"Test {tc.test_case_id} has empty requirement_id property"


def test_all_requirements_reach_excel(tmp_path: Path):
    """
    Every normalized requirement (including field-derived ones) 
    must be exported to the Excel Requirements sheet.
    """
    from app.services.cognos_excel_compiler import build_cognos_workbook
    
    root_dir = Path(__file__).parent / "fixtures" / "golden_sources"
    doc_path = root_dir / "Report Definition- OPT-TPL-005.docx"
    result = run_cognos_pipeline(doc_path)
    assert result.final_report_context is not None
    wb = build_cognos_workbook(result.final_report_context)
    assert "Requirements" in wb.sheetnames
    
    req_sheet = wb["Requirements"]
    
    # We expect roughly 1 header row + N requirement rows
    active_reqs = [r for r in result.requirement_set.requirements if not r.is_duplicate_of]
    assert len(active_reqs) > 0
    
    # Count rows with data
    row_count = sum(1 for row in req_sheet.iter_rows(min_row=2, max_row=req_sheet.max_row) if row[0].value)
    
    # Since we populated the requirements sheet from active requirements
    assert row_count == len(active_reqs), f"Expected {len(active_reqs)} requirement rows, got {row_count}"


def test_traceability_is_populated(tmp_path: Path):
    """
    The Traceability Matrix must be populated natively by the coverage analyzer.
    """
    root_dir = Path(__file__).parent / "fixtures" / "golden_sources"
    doc_path = root_dir / "Report Definition- OPT-TPL-005.docx"
    result = run_cognos_pipeline(doc_path)
    
    matrix = result.test_suite.traceability_matrix
    assert len(matrix) > 0
    
    # Check that field-level requirements reached the matrix
    field_reqs = [e for e in matrix if e.category in (RequirementCategory.COLUMN.value, RequirementCategory.COLUMN_LOGIC.value, RequirementCategory.COLUMN_LABEL.value)]
    assert len(field_reqs) > 0
    
    for entry in matrix:
        assert entry.requirement_id
        if entry.coverage_status == "Covered":
            assert len(entry.test_case_ids) > 0


@pytest.mark.skip(reason="Phase 9.8B Disposition: OBSOLETE_TEST")
def test_coverage_matches_relationships(tmp_path: Path):
    """
    Coverage percentage must exactly match unique covered IDs / total normalized IDs.
    """
    root_dir = Path("D:/test-case-gendration/healthcare-nl-testgen")
    doc_path = root_dir / "Report Definition  OPR.docx"
    result = run_cognos_pipeline(doc_path)
    
    coverage = result.test_suite.coverage
    
    active_reqs = [r for r in result.requirement_set.requirements if not r.is_duplicate_of]
    total_reqs = len(active_reqs)
    
    # Manual calculation
    covered_ids = set()
    for tc in result.test_suite.test_cases:
        for rid in tc.requirement_ids:
            covered_ids.add(rid)
            
    # Account for the fact that some requirement_ids might belong to duplicate reqs, 
    # but the active_reqs list filters duplicates. The coverage analyzer also filters duplicates.
    actual_covered = sum(1 for r in active_reqs if r.requirement_id in covered_ids)
    
    expected_pct = round((actual_covered / total_reqs * 100), 2) if total_reqs > 0 else 0.0
    
    assert coverage.total_requirements == total_reqs
    assert coverage.requirements_covered == actual_covered
    assert coverage.overall_coverage_percentage == expected_pct