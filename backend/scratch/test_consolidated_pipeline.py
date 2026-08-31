import sys
sys.path.insert(0, '.')
from pathlib import Path
from app.cognos.pipeline import run_cognos_pipeline

res = run_cognos_pipeline(Path('runs/210/source/source.docx'))
cases = res.test_suite.test_cases

print(f"Total Test Cases Generated: {len(cases)}")
print("=" * 70)
for idx, tc in enumerate(cases):
    print(f"{idx+1:02d}. [{tc.test_case_id}] ({tc.category}) - {tc.test_case_title}")
    if tc.category in ("DB Report Data Validation", "Sort Validation"):
        print(f"    Scenario Order: {tc.scenario_order}")
        print(f"    Req IDs: {tc.requirement_ids}")
        print(f"    Source Table: {tc.source_table}")
        print(f"    Source Column(s): {tc.source_column}")
        print(f"    Source Field(s): {tc.source_field}")
        print(f"    SQL Status: {tc.sql_status}")
        print(f"    SQL Purpose: {tc.sql_purpose}")
        print(f"    Source Mappings: {len(tc.source_mappings)} entries")
        for m in tc.source_mappings:
            print(f"       - {m}")
        print(f"    Validation SQL:\n{tc.validation_sql}")
        print("-" * 70)
