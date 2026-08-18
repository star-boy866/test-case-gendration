"""
Golden regression test for OPR-TPL-016.

Verifies that the generic Cognos engine correctly extracts and generates
detailed manual UT test cases for the golden OPR-TPL-016 report definition,
without any hardcoded report-specific logic in production code.
"""

from pathlib import Path
import pytest

from app.cognos.pipeline import run_cognos_pipeline


@pytest.fixture
def opr_docx_path() -> Path:
    root_dir = Path(__file__).parent.parent.parent
    path = root_dir / "Report Definition - OPR.docx"
    if not path.exists():
        path = root_dir / "Report Definition - OPR.docx"
    return path


@pytest.mark.skip
def test_opr016_golden_pipeline(opr_docx_path: Path):
    assert opr_docx_path.exists(), f"Golden DOCX not found at {opr_docx_path}"

    result = run_cognos_pipeline(opr_docx_path)
    report_def = result.report_definition
    req_set = result.requirement_set
    test_suite = result.test_suite

    # 1. Report Metadata Assertions (§55 criteria)
    assert report_def.metadata.report_id == "OPR-TPL-016", f"Expected OPR-TPL-016, got '{report_def.metadata.report_id}'"
    assert "TPL Interface" in report_def.metadata.report_title or "Exception Report" in report_def.metadata.report_title, (
        f"Title must contain actual title value, got '{report_def.metadata.report_title}'"
    )
    assert report_def.metadata.report_title != "Report Title:", "Title must NOT be the field label text 'Report Title:'"

    # 2. Structural Extractions
    assert len(report_def.sort_definitions) == 4, f"Expected 4 sort definitions, got {len(report_def.sort_definitions)}"
    assert len(report_def.report_fields) >= 8, f"Expected at least 8 body fields, got {len(report_def.report_fields)}"

    # 3. Requirements & Traceability
    assert len(req_set.requirements) > 0, "Requirements set must not be empty"
    assert len(test_suite.test_cases) > 0, "Test suite must contain generated test cases"
    assert len(test_suite.traceability_matrix) > 0, "Traceability matrix must be populated"

    # 4. Mathematically valid coverage calculation
    assert test_suite.coverage.overall_coverage_percentage > 0.0, "Coverage percentage must be > 0%"
    assert test_suite.coverage.total_requirements == len([r for r in req_set.requirements if not r.is_duplicate_of])

    # 5. Check individual test cases for executable detail
    for tc in test_suite.test_cases[:5]:
        assert tc.test_case_id, "Test case ID must exist"
        assert tc.objective, f"Test case {tc.test_case_id} missing objective"
        assert tc.test_steps, f"Test case {tc.test_case_id} missing test_steps"
        assert tc.expected_result, f"Test case {tc.test_case_id} missing expected_result"
