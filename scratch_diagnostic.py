import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(r"d:\test-case-gendration\healthcare-nl-testgen\backend").absolute()))

from app.cognos.pipeline import run_cognos_pipeline
from app.services.canonical_parser import parse_canonical_docx
from app.cognos.extraction.dsd_interpreter import interpret_dsd
from app.domain.cognos_models import ReportDefinition
from app.cognos.rules import generate_all_test_cases, assign_test_case_ids
from app.cognos.validation.coverage_analyzer import compute_coverage

def trace_pipeline():
    docx_path = Path(r"d:\test-case-gendration\healthcare-nl-testgen\backend\tests\fixtures\golden_sources\Service Authorization Part E_CR18140_V0.1 1.docx")
    
    print("========================================================")
    print("STAGE 1 - DSD PARSER")
    print("========================================================")
    canonical_doc = parse_canonical_docx(docx_path)
    total_elements = len(canonical_doc.paragraphs) + len(canonical_doc.tables)
    print(f"TOTAL PARSED DOCUMENT ELEMENTS: {total_elements}")
    
    print("========================================================")
    print("STAGE 2 - SEMANTIC EXTRACTION")
    print("========================================================")
    req_set = interpret_dsd(canonical_doc, docx_path.name)
    print(f"RequirementSet count: {len(req_set.requirements)}")
    if len(req_set.requirements) > 0:
        first_req = req_set.requirements[0]
        print(f"Sample req: {first_req.requirement_id}, {first_req.category}, {first_req.requirement_text}")
    
    print("========================================================")
    print("STAGE 3 - REQUIREMENT ID VALIDATION")
    print("========================================================")
    missing_ids = [r for r in req_set.requirements if not r.requirement_id]
    print(f"Requirements with missing IDs: {len(missing_ids)}")
    
    print("========================================================")
    print("STAGE 4 - TEST DESIGN ENGINE")
    print("========================================================")
    report_def = ReportDefinition(source_document=docx_path.name)
    report_def.metadata.report_id = req_set.report_id
    
    test_cases = generate_all_test_cases(report_def, req_set)
    test_cases = assign_test_case_ids(test_cases, report_def.metadata.report_id)
    
    print("\n========================================================")
    print("FINAL OUTPUT")
    print("========================================================")
    print(f"1. Parsed DSD count: {total_elements}")
    print(f"2. Semantic RequirementSet count: {len(req_set.requirements)}")
    print(f"3. Requirement IDs: {[r.requirement_id for r in req_set.requirements]}")
    print(f"4. Test case count before Excel: {len(test_cases)}")
    
    import os
    docs = [
        "backend/tests/fixtures/golden_sources/CR 18175 PRV-INT-027 UT DOCUMENT 1.docx",
        "backend/tests/fixtures/golden_sources/Service Authorization Part E_CR18140_V0.1 1.docx",
        "backend/tests/fixtures/golden_sources/Report Definition- OPT-TPL-005.docx"
    ]

    for doc_path in docs:
        print(f"\n{'='*60}\nDIAGNOSING: {doc_path}\n{'='*60}")
        try:
            result = run_cognos_pipeline(
                docx_path=doc_path,
                source_document_name=os.path.basename(doc_path)
            )
            print(f"FinalReportContext counts: reqs={len(result.final_report_context.requirement_set.requirements)}, tcs={len(result.final_report_context.test_suite.test_cases)}")
            
            # Check evidence mapping on the first few test cases
            for tc in result.test_suite.test_cases[:3]:
                print(f"  TC {tc.test_case_id}:")
                print(f"    - evidence_type: {tc.evidence_type}")
                print(f"    - evidence_required: {repr(tc.evidence_required)}")
                print(f"    - source_table: {tc.source_table}")
                
        except Exception as e:
            print(f"FAILED on {doc_path}: {e}")

if __name__ == "__main__":
    trace_pipeline()
