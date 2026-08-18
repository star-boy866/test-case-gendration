import json
import pytest
import hashlib
from pathlib import Path

from app.cognos.pipeline import run_cognos_pipeline
from app.testing.golden.comparator import (
    compare_requirements,
    compare_test_cases,
    compare_coverage,
    compare_traceability,
    DiffResult
)
from tests.golden_framework.generate import (
    normalize_requirement,
    normalize_test_case,
    compute_sha256
)

GOLDEN_REPORTS_DIR = Path("tests/golden/reports")
FIXTURES_DIR = Path("tests/fixtures/golden_sources")

def get_golden_reports():
    if not GOLDEN_REPORTS_DIR.exists():
        return []
    return [p.name for p in GOLDEN_REPORTS_DIR.iterdir() if p.is_dir()]

@pytest.mark.parametrize("report_id", get_golden_reports())
def test_golden_corpus_validity(report_id):
    """
    Verify the golden fixture itself is valid before using it.
    - Check hashes
    - Check coverage math
    - Check IDs
    """
    report_dir = GOLDEN_REPORTS_DIR / report_id
    with open(report_dir / "metadata.json") as f:
        meta = json.load(f)
        
    docx_path = FIXTURES_DIR / meta["source_filename"]
    assert docx_path.exists(), f"Source DOCX {meta['source_filename']} missing!"
    
    current_sha = compute_sha256(docx_path)
    if current_sha != meta["source_sha256"]:
        pytest.fail(f"GOLDEN SOURCE CHANGED for {report_id}. Expected {meta['source_sha256']}, got {current_sha}. Do not auto-update without review.")
        
    with open(report_dir / "expected_coverage.json") as f:
        cov = json.load(f)
        
    # verify coverage math independently
    total = cov["total_dsd_requirements"]
    covered = len(cov["covered_requirement_ids"])
    if total > 0:
        expected_pct = round((covered / total) * 100, 1)
        # allow small floating point fuzziness
        assert abs(cov["coverage_percentage"] - expected_pct) <= 0.1, f"Coverage math invalid: {covered}/{total} != {cov['coverage_percentage']}%"

@pytest.mark.parametrize("report_id", get_golden_reports())
def test_semantic_regression_pipeline(report_id):
    """
    Run the production pipeline and verify output semantically matches golden.
    """
    report_dir = GOLDEN_REPORTS_DIR / report_id
    with open(report_dir / "metadata.json") as f:
        meta = json.load(f)
        
    docx_path = FIXTURES_DIR / meta["source_filename"]
    
    xml_path = None
    # For testing, if the xml exists in the same dir and matches sha, use it
    if meta.get("xml_sha256"):
        # We assume the xml file is named {report_id}.xml or similar. Let's find it.
        possible_xml = FIXTURES_DIR / f"{report_id}.xml"
        if possible_xml.exists() and compute_sha256(possible_xml) == meta["xml_sha256"]:
            xml_path = possible_xml
            
    # RUN REAL PRODUCTION PIPELINE
    result = run_cognos_pipeline(
        docx_path=docx_path,
        xml_path=xml_path,
        source_document_name=meta["source_filename"],
        target_report_id=report_id
    )
    
    # 1. Compare Requirements
    with open(report_dir / "expected_requirements.json") as f:
        expected_reqs = json.load(f)
        
    actual_reqs = [normalize_requirement(r) for r in result.requirement_set.requirements]
    req_diffs = compare_requirements(report_id, expected_reqs, actual_reqs)
    
    # 2. Compare Test Cases
    with open(report_dir / "expected_test_cases.json") as f:
        expected_tcs = json.load(f)
        
    actual_tcs = [normalize_test_case(tc) for tc in result.test_suite.test_cases]
    tc_diffs = compare_test_cases(report_id, expected_tcs, actual_tcs)
    
    # 3. Compare Coverage
    with open(report_dir / "expected_coverage.json") as f:
        expected_cov = json.load(f)
        
    cov = result.test_suite.coverage
    actual_cov = {
        "total_dsd_requirements": cov.total_requirements,
        "covered_requirement_ids": sorted([t.requirement_id for t in result.test_suite.traceability_matrix if t.coverage_status == "Covered"]),
        "coverage_percentage": cov.overall_coverage_percentage
    }
    cov_diffs = compare_coverage(report_id, expected_cov, actual_cov)
    
    all_diffs = req_diffs + tc_diffs + cov_diffs
    
    # 4. Compare Traceability (if applicable)
    if (report_dir / "expected_traceability.json").exists() and getattr(result.final_report_context, 'traceability_result', None):
        with open(report_dir / "expected_traceability.json") as f:
            expected_trace = json.load(f)
            
        trace = result.final_report_context.traceability_result
        actual_mappings = []
        for match in getattr(trace, 'field_traces', []):
            actual_mappings.append({
                "requirement_id": match.dsd_field_name,
                "xml_path": match.xml_data_item_name
            })
        actual_trace = {"mappings": actual_mappings}
        trace_diffs = compare_traceability(report_id, expected_trace, actual_trace)
        all_diffs.extend(trace_diffs)
        
    # Evaluate Severities
    criticals = [d for d in all_diffs if d.severity == "CRITICAL"]
    highs = [d for d in all_diffs if d.severity == "HIGH"]
    
    if criticals or highs:
        msg = f"Golden Regression Failure for {report_id}:\n"
        for c in criticals + highs:
            msg += c.format() + "\n"
        pytest.fail(msg)


# --- META TESTS ---

def test_meta_golden_comparator_catches_missing_requirement():
    diffs = compare_requirements("TEST", [{"requirement_id": "REQ1"}], [])
    assert len(diffs) == 1
    assert diffs[0].severity == "CRITICAL"
    assert "missing" in diffs[0].reason.lower()

def test_meta_golden_comparator_catches_altered_semantic_column():
    exp = [{"requirement_id": "REQ1", "source_columns": ["COL_A"]}]
    act = [{"requirement_id": "REQ1", "source_columns": ["COL_B"]}]
    diffs = compare_requirements("TEST", exp, act)
    assert len(diffs) == 1
    assert diffs[0].severity == "CRITICAL"
    
def test_meta_golden_comparator_ignores_harmless_whitespace():
    exp = [{"requirement_id": "REQ1", "statement": "This   is  a test."}]
    act = [{"requirement_id": "REQ1", "statement": "This is a test."}]
    diffs = compare_requirements("TEST", exp, act)
    assert len(diffs) == 0

def test_meta_golden_comparator_catches_fabricated_mapping():
    exp = {"mappings": []}
    act = {"mappings": [{"requirement_id": "REQ1", "xml_path": "a/b/c"}]}
    diffs = compare_traceability("TEST", exp, act)
    assert len(diffs) == 1
    assert diffs[0].severity == "CRITICAL"
