"""
Phase 12Q.1 — Database Migration & Persistence Verification Tests.

Verifies:
1. `cognos_test_cases` table schema has `scenario_order` column.
2. Generating test cases via pipeline persists to SQLite database without OperationalError.
3. Retrieved database rows have correct `scenario_order` values (10, 20, ..., 240).
4. FastAPI upload_and_generate endpoint succeeds (HTTP 200) with 24 ordered scenarios.
"""

from fastapi.testclient import TestClient
from sqlalchemy import inspect
import pytest

from app.main import app
from app.db.session import engine, SessionLocal
from app.models.cognos_orm import CognosTestCaseModel, CognosGenerationRun
from app.cognos.pipeline import run_cognos_pipeline
from app.cognos.rules import order_cognos_test_cases

EXPECTED_ORDERED_IDS = [
    "PRV027-REPO-01",
    "PRV027-RHDR-01",
    "PRV027-SECT-01",
    "PRV027-SELC-01",
    "PRV027-LABE-01",
    "PRV027-LAYO-01",
    "PRV027-LOOK-01",
    "PRV027-OUTP-01",
    "PRV027-OUTP-02",
    "PRV027-SCRI-01",
    "PRV027-SCRI-02",
    "PRV027-SCHE-01",
    "PRV027-SORT-01",
    "PRV027-SORT-02",
    "PRV027-SPEC-01",
    "PRV027-DATE-01",
    "PRV027-DATE-02",
    "PRV027-DBRE-01",
    "PRV027-DBRE-02",
    "PRV027-DBRE-03",
    "PRV027-DBRE-04",
    "PRV027-DBRE-05",
    "PRV027-DBRE-06",
    "PRV027-DBCO-01",
    "PRV027-DUPL-01",
]


from app.core.security import create_access_token, hash_password
from app.models.user import User


def _ensure_test_user(username: str = "test_admin_phase12q1") -> str:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(
                username=username,
                hashed_password=hash_password("adminpass123"),
                role="admin",
                is_active=True,
            )
            db.add(user)
            db.commit()
        return username
    finally:
        db.close()


def test_schema_has_scenario_order_column():
    """Verify that the database schema contains scenario_order in cognos_test_cases."""
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("cognos_test_cases")]
    assert "scenario_order" in columns, "scenario_order column missing from cognos_test_cases table"


def test_upload_and_generate_api_success_and_db_persistence():
    """Verify end-to-end API upload-and-generate persists 25 test cases with scenario_order."""
    client = TestClient(app)
    docx_path = "runs/94/source/source.docx"
    username = _ensure_test_user()
    token = create_access_token(subject=username, role="admin")

    with open(docx_path, "rb") as f:
        response = client.post(
            "/api/cognos/upload-and-generate",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("source.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"requested_by": "test_user_phase12q1"}
        )

    assert response.status_code == 200, f"Upload API failed with {response.status_code}: {response.text}"
    data = response.json()
    test_cases = data.get("test_cases", [])

    assert len(test_cases) == 25, f"Expected 25 test cases, got {len(test_cases)}"
    
    # Verify API response ordering
    actual_ids = [tc["test_case_id"] for tc in test_cases]
    assert actual_ids == EXPECTED_ORDERED_IDS, f"API test cases order mismatch:\nActual: {actual_ids}\nExpected: {EXPECTED_ORDERED_IDS}"

    # Verify scenario_order in API response
    for idx, tc in enumerate(test_cases):
        expected_order = (idx + 1) * 10
        assert tc.get("scenario_order") == expected_order, f"{tc['test_case_id']} expected scenario_order {expected_order}, got {tc.get('scenario_order')}"

    # Verify persistence in Database
    run_id = data.get("run_id")
    assert run_id is not None
    db = SessionLocal()
    try:
        db_cases = db.query(CognosTestCaseModel).filter(CognosTestCaseModel.run_id == run_id).order_by(CognosTestCaseModel.scenario_order.asc()).all()
        assert len(db_cases) == 25
        db_ids = [c.test_case_id for c in db_cases]
        assert db_ids == EXPECTED_ORDERED_IDS
        for idx, c in enumerate(db_cases):
            assert c.scenario_order == (idx + 1) * 10
    finally:
        db.close()
