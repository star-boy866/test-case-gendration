import sys
sys.path.insert(0, '.')
from pathlib import Path
from app.cognos.pipeline import run_cognos_pipeline

res = run_cognos_pipeline(Path('runs/210/source/source.docx'))
print("Total Test Cases:", len(res.test_suite.test_cases))
for tc in res.test_suite.test_cases:
    print(f"[{tc.test_case_id}] ({tc.category}) - {tc.test_case_title}")
