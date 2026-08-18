"""
Test dynamic scenario generation based on Part 5 classifications.
"""
from pathlib import Path
import pytest

from app.services.cognos_docx_parser import parse_cognos_docx
from app.cognos.pipeline import run_cognos_pipeline
from app.domain.cognos_models import SourceLogicType

@pytest.fixture
def root_dir() -> Path:
    return Path(__file__).parent.parent.parent

@pytest.mark.skip
def test_opr016_scenarios(root_dir: Path):
    doc_path = root_dir / "Report Definition - OPR.docx"
    result = run_cognos_pipeline(doc_path)
    
    # Verify Mbr Name-Full (CONCATENATED, 3 inputs) -> 6 combinations generated
    name_cases = [c for c in result.test_cases if c.source_field == "Mbr Name-Full"]
    assert len(name_cases) == 6, f"Expected 6 combinations for 3 inputs, got {len(name_cases)}"
    
    # Verify Carrier ID (DIRECT_SOURCE) -> 1 mapping validation
    carrier_cases = [c for c in result.test_cases if c.source_field == "Carrier ID"]
    assert len(carrier_cases) == 1, "Expected 1 direct source case"
    assert carrier_cases[0].category == "Column Source Mapping"

@pytest.mark.skip
def test_opr004_scenarios(root_dir: Path):
    doc_path = root_dir / "Report Definition OPR-TPL-004 - OPR.docx"
    result = run_cognos_pipeline(doc_path)
    
    # Verify Mbr Name-Full (CONCATENATED, 4 inputs) -> 7 combinations generated
    name_cases = [c for c in result.test_cases if "Mbr Name-Full" in c.source_field or "TPL Plcyhldr" in c.source_field]
    assert len(name_cases) == 7, f"Expected 7 combinations for 4 inputs, got {len(name_cases)}"

@pytest.mark.skip
def test_opr005_scenarios(root_dir: Path):
    doc_path = root_dir / "Report Definition- OPT-TPL-005.docx"
    result = run_cognos_pipeline(doc_path)
    
    # Verify Partial Matches (PROGRAM_GENERATED)
    pm_cases = [c for c in result.test_cases if c.source_field == "Partial Matches"]
    assert len(pm_cases) >= 1
    assert pm_cases[0].category == "Business Rule"
    assert "calculation" in pm_cases[0].test_case_title.lower()
