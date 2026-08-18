"""
Ingestion endpoints — Phase 1.

Accepts an RDD/LDM upload scoped to a report_id (and optional cr_id),
parses it via app.services.document_parser, and persists structured
results via app.services.knowledge_base.

Per Hallucination Prevention rules: if nothing structured is found, the
response carries the exact mandated message and a `parse_status` of
"insufficient_metadata" rather than failing silently or inventing content.
"""

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import require_role, CurrentUser
from app.db.session import get_db
from app.services.document_parser import parse_document, SUPPORTED_EXTENSIONS
from app.services.knowledge_base import persist_parsed_document, get_knowledge_base_summary
from app.services.semantic_cache import invalidate_cache_for_report
from app.services.malware_scan import scan_file
from app.models.audit import AuditLogEntry

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


class IngestionResponse(BaseModel):
    filename: str
    report_id: str
    cr_id: Optional[str] = None
    parse_status: str
    source_document_id: int
    kb_invalidated_prior_version: bool
    counts: dict
    warnings: list[str]
    message: Optional[str] = None


@router.post("/upload", response_model=IngestionResponse)
async def upload_document(
    file: UploadFile = File(...),
    report_id: str = Form(...),
    cr_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    contents = await file.read()
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds MAX_UPLOAD_MB ({settings.MAX_UPLOAD_MB} MB) limit.",
        )

    # Write to a temp file for parsing — never persist raw uploads longer
    # than necessary, and never write outside the configured upload dir.
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(dir=upload_dir, suffix=ext, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    # Malware scan (Phase 9) — runs on every upload, before parsing ever
    # touches the file. Structural-validation failures (extension doesn't
    # match actual file bytes, or an executable/script signature) are a
    # hard block: there is no legitimate RDD/LDM that looks like this.
    # ClamAV not being reachable is logged but non-fatal by default — see
    # malware_scan.py's docstring for why.
    scan_result = scan_file(tmp_path, ext)
    if not scan_result.is_safe:
        db.add(AuditLogEntry(
            user_id=current_user.username,
            event_type="MALWARE_SCAN_BLOCKED",
            detail=f'{{"filename": "{file.filename}", "reasons": {scan_result.reasons!r}}}',
        ))
        db.commit()
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"File rejected by malware/integrity scan: {'; '.join(scan_result.reasons)}",
        )
    if not scan_result.clamav_checked:
        db.add(AuditLogEntry(
            user_id=current_user.username,
            event_type="MALWARE_SCAN_CLAMAV_UNAVAILABLE",
            detail=f'{{"filename": "{file.filename}", "note": "structural validation passed; ClamAV was not reachable/configured for this scan"}}',
        ))
        db.commit()

    try:
        parsed = parse_document(tmp_path)
        result = persist_parsed_document(
            db,
            report_id=report_id,
            cr_id=cr_id,
            filename=file.filename,
            file_path=tmp_path,
            file_type=ext.lstrip("."),
            uploaded_by=current_user.username,
            parsed=parsed,
        )
    finally:
        # Phase 0/1: no long-term raw file retention. If a future phase needs
        # to keep the original file (e.g. for SharePoint sync provenance),
        # move it into permanent storage here instead of deleting it.
        tmp_path.unlink(missing_ok=True)

    # Phase 3: a changed source file already invalidated Gatekeeper
    # confirmation and KB rows (see knowledge_base.invalidate_existing_kb).
    # Close the same loop for the semantic cache — stale cached test
    # scenarios must not survive a KB change for this report_id.
    if result["kb_invalidated_prior_version"]:
        invalidate_cache_for_report(db, report_id)

    return IngestionResponse(
        filename=file.filename,
        report_id=report_id,
        cr_id=cr_id,
        parse_status=result["parse_status"],
        source_document_id=result["source_document_id"],
        kb_invalidated_prior_version=result["kb_invalidated_prior_version"],
        counts=result["counts"],
        warnings=result["warnings"],
        message=result["message"],
    )


@router.get("/knowledge-base/{report_id}")
def view_knowledge_base(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    Full listing of everything extracted for a report_id so far. Powers the
    Gatekeeper confirmation UI (Phase 2) and the Context Minimizer (Phase 3).
    """
    summary = get_knowledge_base_summary(db, report_id)
    if not summary["source_documents"]:
        raise HTTPException(
            status_code=404,
            detail=f"No documents have been ingested yet for report_id='{report_id}'.",
        )
    return summary
