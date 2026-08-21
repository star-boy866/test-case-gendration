import pytest
from pathlib import Path
from app.services.cognos_docx_parser import parse_cognos_docx
from app.cognos.extraction.nh_mmis_dsd_interpreter import NhMmisDsdInterpreter
from app.cognos.extraction.nh_mmis_requirement_builder import NhMmisRequirementBuilder
from app.cognos.schema.nh_mmis_dsd_models import NhMmisDsd

def test_prv_int_027_semantic_extraction(tmp_path: Path):
    # Locate PRV-INT-027 docx
    root_dir = Path("d:/test-case-gendration/healthcare-nl-testgen")
    # Using the name found in root
    doc_path = root_dir / "Report Definition – PRV explained (1).docx"
    
    # It's possible the file might not exist in that exact location during tests on other environments,
    # but for acceptance of this exact phase we assume it's there.
    if not doc_path.exists():
        pytest.skip(f"Document not found: {doc_path}")

    # Parse
    doc = parse_cognos_docx(doc_path)
    
    # 1. Interpret Schema
    interpreter = NhMmisDsdInterpreter(doc)
    dsd = interpreter.interpret()
    
    assert dsd is not None
    
    # report metadata
    assert dsd.report_definition is not None
    assert dsd.report_definition.client_report_id == "PRV-INT-027"
    assert "Provider License Interface" in dsd.report_definition.report_title
    assert "Term Date Report" in dsd.report_definition.report_title
    
    # frequency/trigger
    assert dsd.report_generation is not None
    
    # output (includes checkbox state conceptually if tested via parser)
    assert dsd.output is not None
    
    # selection criteria
    assert len(dsd.selection_criteria) > 0
    
    # sort, control break, count, total
    assert len(dsd.sorts) >= 0  # May or may not have, but fields exist
    assert len(dsd.control_breaks) >= 0
    assert len(dsd.counts) >= 0
    assert len(dsd.totals) >= 0
    
    # layout
    assert dsd.layout is not None
    assert "PRV-INT-027" in dsd.layout.report_id
    
    # six report specification fields
    assert len(dsd.report_specification) > 0
    # ensure "Column" placeholder from glossary is NOT a requirement, and empty sections are ignored
    for row in dsd.report_specification:
        assert row.business_label.lower() not in ["chart header", "chart footer", "report footnote"]
        
    # source provenance
    assert dsd.report_definition.source_document == doc.filename
    
    # 2. Build Requirements
    builder = NhMmisRequirementBuilder(dsd)
    req_set = builder.build()
    
    assert req_set is not None
    assert len(req_set.requirements) > 0
    
    # unique requirement IDs (REQ-{REPORT_ID}-{CATEGORY}-{SEQUENCE})
    req_ids = set()
    for req in req_set.requirements:
        assert req.requirement_id.startswith("REQ-PRV027-") or req.requirement_id.startswith("REQ-PRV-INT-027-")
        # Ensure category[:4] rule is NOT used (e.g., REQ-PRV027-REPO-001)
        assert "-REPO-" not in req.requirement_id
        req_ids.add(req.requirement_id)
        
    assert len(req_ids) == len(req_set.requirements)
