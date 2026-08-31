import sys
sys.path.insert(0, '.')
import sqlite3
from pathlib import Path
from app.cognos.pipeline import run_cognos_pipeline

res = run_cognos_pipeline(Path('runs/210/source/source.docx'))
print("Pipeline complete!")
print("Report ID:", res.report_definition.metadata.report_id)

dbre_cases = [tc for tc in res.test_suite.test_cases if "DBRE" in tc.test_case_id]
for tc in dbre_cases:
    print("=" * 60)
    print(f"Scenario: {tc.test_case_id} - {tc.test_case_title}")
    print(f"Target Validation Field: {tc.source_field}")
    print(f"Target Source Column: {tc.source_table}.{tc.source_column}")
    print(f"Shared SQL Group: {tc.shared_sql_group}")
    print(f"SQL Purpose: {tc.sql_purpose}")
    print(f"Expected Validation: {tc.expected_validation}")
    print(f"SQL Status: {tc.sql_status}")
