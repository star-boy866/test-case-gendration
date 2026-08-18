import os
import sys
from pathlib import Path
from pprint import pprint

# Add backend directory to sys.path so imports work
backend_dir = Path(r"D:\test-case-gendration\healthcare-nl-testgen\backend")
sys.path.insert(0, str(backend_dir))

# pyrefly: ignore [missing-import]
from app.cognos.pipeline import run_cognos_pipeline

def test_pipeline():
    docx_path = Path(r"D:\test-case-gendration\healthcare-nl-testgen\Service Authorization Part E_CR18140_V0.1 1.docx")
    
    print(f"Running pipeline on: {docx_path} for OPR-SRA-139")
    result = run_cognos_pipeline(docx_path, target_report_id="OPR-SRA-139")
    
    print("\n--- Pipeline Summary ---")
    print(f"Report ID: {result.report_definition.metadata.report_id}")
    print(f"Report Title: {result.report_definition.metadata.report_title}")
    
    print(f"\nExtracted Requirements: {len(result.requirement_set.requirements)}")
    print(f"Generated Test Cases: {len(result.test_suite.test_cases)}")
    print(f"Overall Coverage: {result.test_suite.coverage.overall_coverage_percentage}%")
    
    print("\n--- Coverage by Category ---")
    for cat in result.test_suite.coverage.category_coverage:
        print(f"  {cat.category}: {cat.requirements_covered}/{cat.requirements_found} ({cat.coverage_percentage}%) - {cat.test_cases_generated} test cases")
        
    print("\n--- Top 5 Test Cases ---")
    for i, tc in enumerate(result.test_suite.test_cases[:5]):
        print(f"{tc.test_case_id}: [{tc.category}] {tc.test_case_title}")
        
    print("\n--- Warnings ---")
    for w in result.test_suite.generation_warnings:
        print(f"WARNING: {w}")

    # pyrefly: ignore [missing-import]
    from app.services.cognos_excel_compiler import build_cognos_workbook
    wb = build_cognos_workbook(result.final_report_context)
    out_name = f"../Cognos_UT_{result.test_suite.report_id}_FINAL.xlsx"
    wb.save(out_name)
    print(f"\nSaved {out_name}")

if __name__ == "__main__":
    test_pipeline()
