import asyncio
import os
from pathlib import Path
from app.cognos.pipeline import run_cognos_pipeline
from app.services.cognos_excel_compiler import build_cognos_workbook

async def generate_workbooks():
    reports = [
        ("OPR-TPL-016", "Report Definition ? OPR.docx"),
        ("OPR-TPL-004", "Report Definition OPR-TPL-004 * OPR.docx"),
        ("OPR-TPL-005", "Report Definition- OPT-TPL-005.docx")
    ]
    
    root_dir = Path("D:/test-case-gendration/healthcare-nl-testgen")
    
    for report_id, pattern in reports:
        matched = list(root_dir.glob(pattern))
        if not matched:
            print(f"Could not find {report_id} with pattern {pattern}")
            continue
            
        doc_path = matched[0]
        print(f"\nProcessing {doc_path}...")
        
        result = run_cognos_pipeline(doc_path)
        wb = build_cognos_workbook(result.test_suite, result.requirement_set)
        
        out_name = f"Final_Output_{result.test_suite.report_id}.xlsx"
        wb.save(out_name)
        print(f"Saved {out_name}")

if __name__ == "__main__":
    asyncio.run(generate_workbooks())
