import sys
sys.path.insert(0, '.')
from app.cognos.pipeline import run_cognos_pipeline
from app.cognos.rules.sql_generator import DeterministicSqlGenerator
from pathlib import Path

res = run_cognos_pipeline(Path('runs/210/source/source.docx'))
rd = res.report_definition
req_set = res.requirement_set
cases = res.test_suite.test_cases

field_to_col, col_to_table = DeterministicSqlGenerator._build_source_mappings(cases[0], rd, req_set)
raw_criteria = DeterministicSqlGenerator._extract_raw_criteria(cases[0], rd, req_set)

print("Field to col:", field_to_col)
print("Col to table:", col_to_table)
print("Raw criteria:", raw_criteria)
