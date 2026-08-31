import sys
sys.path.insert(0, '.')
from app.cognos.pipeline import run_cognos_pipeline
from pathlib import Path

res = run_cognos_pipeline(Path('runs/210/source/source.docx'))
rd = res.report_definition
req_set = res.requirement_set
cases = res.test_suite.test_cases

print("--- Test Cases ---")
for tc in cases:
    if "DBRE" in tc.test_case_id:
        print(tc.test_case_id, "|", tc.source_field, "|", tc.source_column, "|", tc.source_table, "|", (tc.processing_rule or "")[:40])
