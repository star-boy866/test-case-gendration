import sys
sys.path.insert(0, '.')
from pathlib import Path
from app.cognos.pipeline import run_cognos_pipeline

res = run_cognos_pipeline(Path('runs/210/source/source.docx'))
dbrv = next(tc for tc in res.test_suite.test_cases if tc.test_case_id == "PRV027-DBRV-01")

print("DBRV Test Case ID:", dbrv.test_case_id)
print("DBRV Category:", dbrv.category)
print("DBRV Evidences:", len(dbrv.evidence_references))
for ev in dbrv.evidence_references:
    print("--------------------------------------------------")
    print("Type:", ev.evidence_type)
    print("Section:", ev.section)
    print("Page:", ev.page_number)
    print("Evidence Scope:", ev.evidence_scope)
    print("Target Field:", ev.target_field)
    print("Description:", ev.description)
    print("Source Text:", ev.source_text)
    print("Evidence ID:", ev.evidence_id)
