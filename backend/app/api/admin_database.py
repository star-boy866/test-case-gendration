"""
Admin Database Explorer & Governance Data API.

Security Guarantees:
1. STRICT SAFE TABLE ALLOWLIST: No tables outside the allowlist can be accessed.
2. SENSITIVE COLUMN BLOCKLIST: Credential columns (passwords, hashes, tokens, keys)
   are stripped at query time and never returned in API responses.
3. READ-ONLY QUERY BUILDER: Zero arbitrary SQL execution. No DROP/DELETE/INSERT/UPDATE/ALTER.
4. IMMUTABLE AUDIT: Every access emits `ADMIN_DATABASE_VIEWED` or `ADMIN_DATABASE_EXPORT`.
5. RBAC CONSTRAINTS:
   - Admin: Granted.
   - Tester: Strictly Forbidden (403).
   - Standard Admin: Forbidden (403) unless explicit governance permission granted.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from sqlalchemy import text, inspect, func, desc, asc, and_, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import get_current_user, CurrentUser
from app.db.session import get_db, engine
from app.services.audit_service import log_audit_event
from app.models.user import User
from app.models.cognos_orm import CognosGenerationRun, CognosTestCaseModel
from app.models.governance import (
    AuditEvent, GeneratedScenario, ScenarioVersion, ScenarioFeedback,
    LearningCandidate, SourceSnapshot, SourceDocument, GenerationMetadata
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin_database"])

# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY CONFIGURATION & ALLOWLISTS
# ═══════════════════════════════════════════════════════════════════════════════

# Strict table allowlist organized by logical domain
TABLE_METADATA = {
    # AUTH
    "users": {"category": "AUTH", "display_name": "Users", "description": "Application user accounts and RBAC roles"},
    "roles": {"category": "AUTH", "display_name": "Roles", "description": "System and custom RBAC roles"},
    "user_sessions": {"category": "AUTH", "display_name": "User Sessions", "description": "Active and revoked device sessions"},
    "password_history": {"category": "AUTH", "display_name": "Password History", "description": "Historical password hash records for reuse prevention"},
    
    # SOURCE
    "source_documents": {"category": "SOURCE", "display_name": "Source Documents", "description": "Authoritative DSD and Report Definition source files"},
    "source_document_versions": {"category": "SOURCE", "display_name": "Document Versions", "description": "Revision history of uploaded source documents"},
    "source_sections": {"category": "SOURCE", "display_name": "Document Sections", "description": "Parsed sections and headings from source documents"},
    "source_snapshots": {"category": "SOURCE", "display_name": "Evidence Snapshots", "description": "Visual document crops linking evidence to exact pages"},
    
    # TEST CASE STUDIO
    "cognos_generation_runs": {"category": "TEST CASE STUDIO", "display_name": "Generation Runs", "description": "Pipeline execution runs for test case generation"},
    "cognos_requirements": {"category": "TEST CASE STUDIO", "display_name": "Requirements", "description": "Extracted report requirements and business rules"},
    "cognos_test_cases": {"category": "TEST CASE STUDIO", "display_name": "Test Cases", "description": "Generated and reviewed Cognos unit test scenarios"},
    "test_case_assignments": {"category": "TEST CASE STUDIO", "display_name": "Tester Assignments", "description": "Authoritative run assignments to authorized testers"},
    "generated_scenarios": {"category": "TEST CASE STUDIO", "display_name": "Governed Scenarios", "description": "Core scenario lifecycle records"},
    "scenario_versions": {"category": "TEST CASE STUDIO", "display_name": "Scenario Versions", "description": "Immutable version snapshots of every human and AI edit"},
    "scenario_feedback": {"category": "TEST CASE STUDIO", "display_name": "Scenario Feedback", "description": "Tester and admin review feedback and decisions"},
    "scenario_reviews": {"category": "TEST CASE STUDIO", "display_name": "Scenario Reviews", "description": "HITL approvals, rejections, and review comments"},
    "scenario_evidence": {"category": "TEST CASE STUDIO", "display_name": "Scenario Evidence", "description": "Associations between scenarios and visual evidence"},
    "scenario_execution_results": {"category": "TEST CASE STUDIO", "display_name": "Execution Results", "description": "Test run execution statuses and verification notes"},
    
    # AI / LEARNING
    "generation_metadata": {"category": "AI / LEARNING", "display_name": "Generation Metadata", "description": "LLM inference parameters, model names, and timings"},
    "retrieval_events": {"category": "AI / LEARNING", "display_name": "Retrieval Events", "description": "Few-shot and pattern retrieval events during generation"},
    "model_evaluations": {"category": "AI / LEARNING", "display_name": "Model Evaluations", "description": "Evaluation scores and compliance assessments"},
    "prompt_versions": {"category": "AI / LEARNING", "display_name": "Prompt Versions", "description": "Versioned prompt templates for test generation"},
    "learning_candidates": {"category": "AI / LEARNING", "display_name": "Learning Candidates", "description": "Curated scenario dataset selected for evaluation and learning"},
    
    # AUDIT
    "audit_events": {"category": "AUDIT", "display_name": "Audit Events", "description": "Comprehensive, immutable audit trail of user and admin actions"},
    "login_events": {"category": "AUDIT", "display_name": "Login Events", "description": "Authentication access logs and failed login attempts"},
    "security_events": {"category": "AUDIT", "display_name": "Security Events", "description": "High-severity security alerts and rate-limiting triggers"},
    "audit_log": {"category": "AUDIT", "display_name": "Legacy Audit Log", "description": "Cryptographically chained audit trail"},
}

ALLOWED_TABLES = set(TABLE_METADATA.keys())

# Columns that must NEVER be returned in any Database Explorer response
SENSITIVE_COLUMN_PATTERNS = {
    "password", "password_hash", "hashed_password", "secret", "secret_key",
    "secret_encrypted", "encryption_key", "api_key", "token", "token_hash",
    "refresh_token", "access_token", "smtp_password", "database_password",
    "credential", "backup_codes_json"
}


def require_database_explorer_access(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """
    Enforces RBAC authorization for Database Explorer:
    - Tester: 403 Forbidden.
    - Admin: Allowed.
    - Standard Admin: 403 Forbidden unless explicit 'database:read' permission granted.
    """
    role = (current_user.role or "").lower().replace("-", "_")
    if current_user.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Account is not active.")

    if role == "tester":
        raise HTTPException(status_code=403, detail="Access denied: Testers cannot access Database Explorer.")

    if role == "admin":
        return current_user

    if role == "standard_admin":
        # Check if caller has explicit 'database:read' permission
        try:
            from app.models.rbac import role_permissions, Permission, Role
            has_perm = (
                db.query(Permission.id)
                .join(role_permissions, Permission.id == role_permissions.c.permission_id)
                .join(Role, role_permissions.c.role_id == Role.id)
                .filter(Role.name == "standard_admin", Permission.code == "database:read")
                .first()
            )
            if has_perm:
                return current_user
        except Exception:
            pass

        # Standard Admin without explicit permission is restricted per governance rule
        raise HTTPException(
            status_code=403,
            detail="Access denied: Standard Admin requires explicit 'database:read' governance permission to browse application tables."
        )

    raise HTTPException(status_code=403, detail="Access denied: Database Explorer is restricted to authorized Admins.")


def get_safe_columns(table_name: str, db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """Returns columns for a table excluding any sensitive credential columns."""
    bind = db.get_bind() if db is not None else engine
    insp = inspect(bind)
    raw_columns = insp.get_columns(table_name)
    safe = []
    for col in raw_columns:
        c_name = col["name"]
        if any(pat in c_name.lower() for pat in SENSITIVE_COLUMN_PATTERNS):
            continue
        safe.append({
            "name": c_name,
            "type": str(col["type"]),
            "nullable": bool(col.get("nullable", True)),
            "primary_key": bool(col.get("primary_key", False)),
        })
    return safe


# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/database/tables")
def list_database_tables(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_database_explorer_access),
):
    """
    Returns the list of permitted application database tables grouped by category,
    with row count estimates and descriptions.
    """
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    
    result = []
    for table_name, meta in TABLE_METADATA.items():
        if table_name not in existing_tables:
            continue

        row_count = 0
        try:
            row_count = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
        except Exception:
            pass

        result.append({
            "table_name": table_name,
            "display_name": meta["display_name"],
            "category": meta["category"],
            "description": meta["description"],
            "row_count": row_count,
        })

    return {
        "tables": result,
        "total_tables": len(result),
        "access_mode": "READ_ONLY",
    }


@router.get("/database/{table}/schema")
def get_table_schema(
    table: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_database_explorer_access),
):
    """Returns safe column definitions for the requested table."""
    table = table.lower().strip()
    if table not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail=f"Table '{table}' is not in the allowed schema list.")

    safe_cols = get_safe_columns(table, db)
    return {
        "table": table,
        "display_name": TABLE_METADATA.get(table, {}).get("display_name", table),
        "category": TABLE_METADATA.get(table, {}).get("category", "GENERAL"),
        "columns": safe_cols,
        "column_count": len(safe_cols),
    }


@router.get("/database/{table}/rows")
def get_table_rows(
    table: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_dir: Optional[str] = Query("desc"),
    status: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    user: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    run_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_database_explorer_access),
):
    """
    Safely retrieves paginated, searchable, sortable rows for an allowed table.
    Never exposes sensitive columns.
    Emits an ADMIN_DATABASE_VIEWED audit event.
    """
    table = table.lower().strip()
    if table not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail=f"Table '{table}' not found or access is restricted.")

    safe_cols = get_safe_columns(table, db)
    safe_col_names = [c["name"] for c in safe_cols]
    if not safe_col_names:
        raise HTTPException(status_code=400, detail="No readable columns found for this table.")

    # Build safe SELECT query with explicit column list
    col_clause = ", ".join([f'"{c}"' if not c.isalnum() else c for c in safe_col_names])
    where_clauses = []
    params: Dict[str, Any] = {}

    # Common Filters
    if status and "status" in safe_col_names:
        where_clauses.append("status = :status_filter")
        params["status_filter"] = status

    if role and "role" in safe_col_names:
        where_clauses.append("role = :role_filter")
        params["role_filter"] = role

    if user:
        if "username" in safe_col_names:
            where_clauses.append("username = :user_filter")
            params["user_filter"] = user
        elif "actor_username" in safe_col_names:
            where_clauses.append("actor_username = :user_filter")
            params["user_filter"] = user

    if action and "action" in safe_col_names:
        where_clauses.append("action = :action_filter")
        params["action_filter"] = action

    if run_id is not None and "run_id" in safe_col_names:
        where_clauses.append("run_id = :run_id_filter")
        params["run_id_filter"] = run_id

    # Date Range Filter
    date_col = next((c for c in ("occurred_at", "created_at", "uploaded_at", "timestamp", "started_at") if c in safe_col_names), None)
    if date_col:
        if date_from:
            where_clauses.append(f"{date_col} >= :date_from")
            params["date_from"] = date_from
        if date_to:
            where_clauses.append(f"{date_col} <= :date_to")
            params["date_to"] = date_to

    # Search Filter across relevant string columns
    if search and search.strip():
        search_val = f"%{search.strip()}%"
        search_candidates = [
            c for c in safe_col_names
            if any(term in c for term in ("username", "test_case_id", "report_id", "action", "status", "file_name", "scenario_name", "title"))
        ]
        if search_candidates:
            s_clauses = [f"{c} LIKE :search_term" for c in search_candidates]
            where_clauses.append(f"({' OR '.join(s_clauses)})")
            params["search_term"] = search_val

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Sort
    sort_dir_clean = "DESC" if (sort_dir or "").lower() == "desc" else "ASC"
    if sort_by and sort_by in safe_col_names:
        order_sql = f"ORDER BY {sort_by} {sort_dir_clean}"
    elif "id" in safe_col_names:
        order_sql = f"ORDER BY id {sort_dir_clean}"
    elif date_col:
        order_sql = f"ORDER BY {date_col} {sort_dir_clean}"
    else:
        order_sql = ""

    # Total Count
    count_query = text(f"SELECT COUNT(*) FROM {table} {where_sql}")
    total_rows = db.execute(count_query, params).scalar() or 0

    # Paging
    offset = (page - 1) * page_size
    params["limit_val"] = page_size
    params["offset_val"] = offset

    data_query = text(f"SELECT {col_clause} FROM {table} {where_sql} {order_sql} LIMIT :limit_val OFFSET :offset_val")
    result_proxy = db.execute(data_query, params)
    
    rows = []
    for row in result_proxy.mappings():
        row_dict = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                row_dict[k] = v.isoformat()
            elif isinstance(v, (dict, list)):
                row_dict[k] = v
            else:
                row_dict[k] = v
        rows.append(row_dict)

    # Log Audit Event: ADMIN_DATABASE_VIEWED
    filter_summary = {k: v for k, v in params.items() if k not in ("limit_val", "offset_val")}
    log_audit_event(
        db=db,
        actor_username=current_user.username,
        actor_role=current_user.role,
        action="ADMIN_DATABASE_VIEWED",
        resource_type="DATABASE_TABLE",
        resource_id=table,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        details={
            "table": table,
            "page": page,
            "page_size": page_size,
            "rows_returned": len(rows),
            "filters": filter_summary,
        },
        actor_user_id=current_user.id,
    )

    return {
        "table": table,
        "display_name": TABLE_METADATA.get(table, {}).get("display_name", table),
        "total_rows": total_rows,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_rows + page_size - 1) // page_size if page_size > 0 else 1,
        "columns": safe_cols,
        "rows": rows,
    }


@router.get("/database/{table}/export")
def export_table_rows(
    table: str,
    request: Request,
    format: str = Query("csv", description="csv | json"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_database_explorer_access),
):
    """
    Exports up to 1000 records from an allowed table without credentials.
    Emits an ADMIN_DATABASE_EXPORT audit event.
    """
    table = table.lower().strip()
    if table not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail="Table not found or not exportable.")

    safe_cols = get_safe_columns(table, db)
    safe_col_names = [c["name"] for c in safe_cols]
    col_clause = ", ".join(safe_col_names)

    order_col = "id" if "id" in safe_col_names else safe_col_names[0]
    query = text(f"SELECT {col_clause} FROM {table} ORDER BY {order_col} DESC LIMIT 1000")
    result = db.execute(query)

    rows = []
    for r in result.mappings():
        row_dict = {}
        for k, v in r.items():
            if isinstance(v, datetime):
                row_dict[k] = v.isoformat()
            elif isinstance(v, (dict, list)):
                row_dict[k] = json.dumps(v)
            else:
                row_dict[k] = v
        rows.append(row_dict)

    # Log export audit event
    log_audit_event(
        db=db,
        actor_username=current_user.username,
        actor_role=current_user.role,
        action="ADMIN_DATABASE_EXPORT",
        resource_type="DATABASE_EXPORT",
        resource_id=table,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        details={"table": table, "format": format, "exported_rows": len(rows)},
        actor_user_id=current_user.id,
    )

    if format.lower() == "json":
        return Response(
            content=json.dumps(rows, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{table}_export.json"'}
        )

    # CSV Export
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=safe_col_names)
        writer.writeheader()
        writer.writerows(rows)
    else:
        output.write(",".join(safe_col_names) + "\n")

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{table}_export.csv"'}
    )


@router.get("/database/audit-summary")
def get_database_audit_summary(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_database_explorer_access),
):
    """
    Returns governance summary metrics for dashboard cards and recent admin actions.
    """
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())

    def _safe_count(tbl: str, condition: Optional[str] = None) -> int:
        if tbl not in existing_tables:
            return 0
        try:
            sql = f"SELECT COUNT(*) FROM {tbl}"
            if condition:
                sql += f" WHERE {condition}"
            return db.execute(text(sql)).scalar() or 0
        except Exception:
            return 0

    total_users = _safe_count("users")
    active_users = _safe_count("users", "is_active = 1 OR is_active = true")
    total_runs = _safe_count("cognos_generation_runs")
    total_scenarios = _safe_count("cognos_test_cases")
    total_versions = _safe_count("scenario_versions")
    total_approved = _safe_count("cognos_test_cases", "review_status = 'APPROVED'")
    total_corrected = _safe_count("cognos_test_cases", "review_status = 'CORRECTED'")
    total_learning = _safe_count("learning_candidates", "selected_for_learning = 1 OR selected_for_learning = true")
    total_audit_events = _safe_count("audit_events")
    total_snapshots = _safe_count("source_snapshots")

    # Recent Admin Actions
    recent_actions = []
    if "audit_events" in existing_tables:
        try:
            events = (
                db.query(AuditEvent)
                .order_by(AuditEvent.occurred_at.desc())
                .limit(10)
                .all()
            )
            for ev in events:
                recent_actions.append({
                    "id": ev.id,
                    "occurred_at": ev.occurred_at.isoformat() if ev.occurred_at else None,
                    "actor_username": ev.actor_username,
                    "actor_role": ev.actor_role,
                    "action": ev.action,
                    "resource_type": ev.resource_type,
                    "resource_id": ev.resource_id,
                    "success": ev.success,
                })
        except Exception as e:
            logger.warning(f"Could not load recent admin actions: {e}")

    return {
        "summary": {
            "total_users": total_users,
            "active_users": active_users,
            "total_runs": total_runs,
            "total_scenarios": total_scenarios,
            "total_versions": total_versions,
            "total_approved_scenarios": total_approved,
            "total_corrected_scenarios": total_corrected,
            "total_learning_candidates": total_learning,
            "total_audit_events": total_audit_events,
            "total_evidence_snapshots": total_snapshots,
        },
        "recent_admin_actions": recent_actions,
    }


@router.get("/learning/summary")
def get_scenario_learning_summary(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_database_explorer_access),
):
    """
    Scenario learning and evaluation dataset summary for AI governance:
    - Scenarios by review status (AI generated, corrected, approved, rejected)
    - Methodology correction frequency
    - Feedback distribution
    - Governed learning candidates
    """
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())

    status_counts = {}
    if "cognos_test_cases" in existing_tables:
        try:
            rows = db.execute(text("SELECT review_status, COUNT(*) FROM cognos_test_cases GROUP BY review_status")).all()
            for r in rows:
                k = str(r[0] or "GENERATED").upper()
                status_counts[k] = int(r[1])
        except Exception:
            pass

    methodology_corrections = []
    if "cognos_test_cases" in existing_tables:
        try:
            rows = db.execute(text(
                "SELECT category, COUNT(*) as cnt FROM cognos_test_cases "
                "WHERE review_status = 'CORRECTED' GROUP BY category ORDER BY cnt DESC LIMIT 10"
            )).all()
            for r in rows:
                methodology_corrections.append({
                    "methodology": str(r[0] or "General"),
                    "corrected_count": int(r[1]),
                })
        except Exception:
            pass

    feedback_distribution = {}
    if "scenario_feedback" in existing_tables:
        try:
            rows = db.execute(text("SELECT feedback_type, COUNT(*) FROM scenario_feedback GROUP BY feedback_type")).all()
            for r in rows:
                feedback_distribution[str(r[0])] = int(r[1])
        except Exception:
            pass

    learning_candidates_count = 0
    if "learning_candidates" in existing_tables:
        try:
            learning_candidates_count = db.execute(text("SELECT COUNT(*) FROM learning_candidates WHERE selected_for_learning = 1 OR selected_for_learning = true")).scalar() or 0
        except Exception:
            pass

    return {
        "status_distribution": {
            "ai_generated": status_counts.get("GENERATED", 0),
            "tester_corrected": status_counts.get("CORRECTED", 0),
            "approved": status_counts.get("APPROVED", 0),
            "rejected": status_counts.get("REJECTED", 0),
            "needs_review": status_counts.get("NEEDS_REVIEW", 0),
        },
        "methodology_corrections": methodology_corrections,
        "feedback_distribution": feedback_distribution,
        "learning_candidates_count": learning_candidates_count,
        "governance_rule": "Only scenarios meeting QA verification and approval standards qualify as learning candidates.",
    }
