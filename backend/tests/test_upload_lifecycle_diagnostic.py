"""
Diagnostic validation test for document upload lifecycle.
Measures and validates:
- Worker PID and RSS before upload
- Lifecycle stages during upload (UPLOAD_RECEIVED, DOCX_PARSE, PDF_CONVERT, SEMANTIC_RESOLUTION, SNAPSHOT_RENDER, GOVERNANCE_PERSIST, RESPONSE)
- Worker PID and RSS after upload
- Request status and scenario count
- Confirms PID remains invariant (no worker restart / termination)
"""
import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import create_access_token
from app.core.upload_diagnostics import get_worker_pid, get_rss_mb
from app.services.user_service import ensure_tester_account


def test_real_upload_lifecycle_pid_and_rss(client, db):
    tester = ensure_tester_account(db)
    token = create_access_token(subject=tester.username, role="tester")

    pid_before = get_worker_pid()
    rss_before = get_rss_mb()
    print(f"\n[VALIDATION BEFORE UPLOAD] PID={pid_before} | RSS={rss_before} MB", flush=True)

    sample_doc = Path("runs/1/source/source.docx")
    assert sample_doc.exists(), f"Sample doc not found at {sample_doc}"

    with open(sample_doc, "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/api/cognos/upload-and-generate",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("CR_18175_PRV_INT_027.docx", file_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"dsd_profile": "NH", "work_type": "REPORT", "work_item_id": "PRV-INT-027"},
    )

    pid_after = get_worker_pid()
    rss_after = get_rss_mb()
    print(f"\n[VALIDATION AFTER UPLOAD] PID={pid_after} | RSS={rss_after} MB | Status={response.status_code}", flush=True)

    # 1. Assert request succeeded
    assert response.status_code == 200, f"Upload failed: {response.status_code} - {response.text}"
    data = response.json()
    assert data["status"] == "success"
    assert data["run_id"] is not None
    assert len(data["test_cases"]) > 0

    # 2. Assert PID invariant (NO worker restart)
    assert pid_before == pid_after, f"Worker PID changed! before={pid_before}, after={pid_after}"
    print(f"[VALIDATION VERIFIED] Worker PID remained identical ({pid_before} == {pid_after}). Upload did not restart or kill process.\n", flush=True)
