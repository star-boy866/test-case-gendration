import sys
sys.path.insert(0, '.')
from pathlib import Path
from app.db.session import SessionLocal
from app.api.cognos_api import get_source_snapshot
from app.models.user import User

db = SessionLocal()
user = db.query(User).filter(User.username == "obuli").first()
if not user:
    user = User(username="admin", role="admin")

response = get_source_snapshot(
    run_id=210,
    evidence_id="snapshot_PRV027-DBRV-01_DB_FULL",
    section="Report Body",
    methodology="DB_REPORT_DATA_VALIDATION",
    target_field="Full Mapping",
    evidence_scope="REPORT_BODY_MAPPING",
    test_case_id="PRV027-DBRV-01",
    db=db,
    current_user=user,
)

print("Response path:", response.path)
print("Response status_code:", response.status_code)
print("File size:", Path(response.path).stat().st_size, "bytes")
