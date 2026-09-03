"""
Cognos Human-in-the-Loop (HITL) Service.

Provides:
1. Scenario review state machine (GENERATED, NEEDS_REVIEW, CORRECTED, APPROVED, REJECTED).
2. AI-assisted correction suggestions analyzing execution method rules, DSD references, and user issues.
3. Execution method logic:
   - NH Scheduled/Other: IWA, RPT- prefix, SDR delivery, ~20 min delivery note.
   - ND Scheduled/Other: UC4, RPT- prefix, SDR delivery.
   - On Request: Cognos Portal OR Application UI (Info Analysis).
4. Missing scenario proposal generation.
5. Scenario revision history tracking with change diffs.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def evaluate_execution_path_rules(
    tc_data: Dict[str, Any],
    report_id: str = "",
    dsd_profile: str = "NH",
    frequency_type: str = "Scheduled",
) -> Dict[str, Any]:
    """
    Evaluates whether the test scenario matches the required enterprise execution rules:
    - NH Scheduled/Other: IWA, RPT- prefix, SDR delivery, 20 minute note.
    - ND Scheduled/Other: UC4, RPT- prefix, SDR delivery.
    - On Request: Cognos Portal or Application UI (Info Analysis).
    """
    rid = (tc_data.get("report_id") or report_id or "PRV-INT-027").strip()
    raw_id = rid[4:] if rid.startswith("RPT-") else rid
    rpt_id = f"RPT-{raw_id}"

    state_code = "ND" if ("ND" in dsd_profile.upper() or "ND-" in rid.upper() or "OPR-" in rid.upper()) else "NH"
    freq_lower = (frequency_type or "Scheduled").lower()
    is_on_request = "on request" in freq_lower or "on-request" in freq_lower

    steps_text = ""
    raw_steps = tc_data.get("test_steps", "")
    if isinstance(raw_steps, list):
        steps_text = "\n".join(str(s) for s in raw_steps)
    else:
        steps_text = str(raw_steps or "")

    steps_lower = steps_text.lower()
    has_cognos_direct = "login to cognos" in steps_lower or "cognos portal" in steps_lower

    if not is_on_request:
        expected_tool = "IWA" if state_code == "NH" else "UC4"
        expected_steps = [
            f"1. Login to {expected_tool}.",
            f"2. Search for {rpt_id}.",
            f"3. Run the report.",
            f"4. Verify report output moves to SDR (Search Document Repository).",
            f"5. Note that output may take approximately 20 minutes to appear in SDR.",
        ]

        mismatch = has_cognos_direct and expected_tool.lower() not in steps_lower
        return {
            "is_scheduled": True,
            "state_code": state_code,
            "expected_tool": expected_tool,
            "expected_report_id": rpt_id,
            "mismatch_detected": mismatch,
            "suggested_steps": "\n".join(expected_steps),
            "suggested_expected_result": f"Report output is generated via {expected_tool} and available in SDR within approximately 20 minutes.",
            "reason": (
                f"Scheduled execution for {state_code} must be performed through {expected_tool} rather than direct Cognos execution. "
                f"The report uses the '{rpt_id}' identifier in the scheduler, and output delivers to SDR (~20 min latency)."
            ),
        }
    else:
        expected_steps_opt_a = [
            f"1. Login to Cognos portal.",
            f"2. Search for {raw_id}.",
            f"3. Run using required format (PDF / Excel / CSV etc.).",
            f"4. Verify report output is generated and downloaded.",
        ]
        expected_steps_opt_b = [
            f"1. Login to the application UI.",
            f"2. Navigate to Info Analysis.",
            f"3. Search for {raw_id}.",
            f"4. Select required output format (PDF / Excel / CSV etc.).",
            f"5. Verify report output is downloaded.",
        ]
        return {
            "is_scheduled": False,
            "state_code": state_code,
            "expected_tool": "Cognos Portal / Info Analysis",
            "expected_report_id": raw_id,
            "mismatch_detected": False,
            "suggested_steps": "\n".join(expected_steps_opt_a),
            "suggested_steps_alt": "\n".join(expected_steps_opt_b),
            "suggested_expected_result": f"Report {raw_id} executes on request and output is downloaded in the selected format.",
            "reason": "On-request execution supports direct execution via Cognos Portal or Application UI (Info Analysis).",
        }


def generate_suggested_correction(
    tc_data: Dict[str, Any],
    issue_type: str = "",
    issue_comment: str = "",
    report_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generates an AI suggested correction for a scenario based on:
    - scenario objective, steps, expected result, DSD references
    - user-flagged issue and comment
    - execution method rules (NH IWA vs ND UC4 vs On-Request)
    """
    meta = report_metadata or {}
    report_id = meta.get("report_id") or tc_data.get("report_id") or "PRV-INT-027"
    dsd_profile = meta.get("dsd_profile") or ("ND" if "ND" in report_id else "NH")
    frequency = meta.get("frequency_type") or "Scheduled"

    exec_eval = evaluate_execution_path_rules(
        tc_data,
        report_id=report_id,
        dsd_profile=dsd_profile,
        frequency_type=frequency,
    )

    steps_raw = tc_data.get("test_steps", "")
    if isinstance(steps_raw, list):
        current_steps_list = [str(s).strip() for s in steps_raw if str(s).strip()]
    else:
        current_steps_list = [s.strip() for s in str(steps_raw or "").split("\n") if s.strip()]

    current_steps_formatted = "\n".join(current_steps_list)

    # 1. Execution method mismatch check or issue
    is_exec_issue = (
        "execution method" in (issue_type or "").lower()
        or "scheduler" in (issue_comment or "").lower()
        or "iwa" in (issue_comment or "").lower()
        or "uc4" in (issue_comment or "").lower()
        or exec_eval.get("mismatch_detected", False)
    )

    if is_exec_issue or exec_eval.get("is_scheduled", False) and exec_eval.get("mismatch_detected"):
        suggested_steps = exec_eval["suggested_steps"]
        suggested_result = exec_eval["suggested_expected_result"]
        tool = exec_eval["expected_tool"]
        return {
            "correction_type": "EXECUTION_METHOD_CORRECTION",
            "title": "Execution Path Alignment",
            "summary": f"Align execution steps with {tool} enterprise scheduler and SDR output repository.",
            "current": {
                "execution_method": tc_data.get("execution_method") or "Cognos Direct",
                "execution_tool": tc_data.get("execution_tool") or "Cognos Portal",
                "report_id": tc_data.get("report_id") or report_id,
                "test_steps": current_steps_formatted,
                "expected_result": tc_data.get("expected_result", ""),
            },
            "suggested": {
                "execution_method": "Scheduled",
                "execution_tool": tool,
                "report_id": exec_eval["expected_report_id"],
                "test_steps": suggested_steps,
                "expected_result": suggested_result,
            },
            "reason": exec_eval["reason"] + (f" Reviewer note: '{issue_comment}'" if issue_comment else ""),
            "changes_summary": [
                f"Execution Tool: Cognos Portal → {tool}",
                f"Report ID: {report_id} → {exec_eval['expected_report_id']}",
                "Delivery Destination: Cognos Download → SDR (20-minute SLA)",
            ],
        }

    # 2. Expected result correction
    if "expected result" in (issue_type or "").lower():
        clean_comment = issue_comment.strip() if issue_comment else "Align with DSD specification"
        new_result = (
            f"{tc_data.get('expected_result', '')}\n"
            f"[Correction per Review]: {clean_comment}"
        ) if clean_comment else tc_data.get("expected_result", "")

        return {
            "correction_type": "EXPECTED_RESULT_CORRECTION",
            "title": "Expected Result Precision",
            "summary": "Refine verification outcome per reviewer feedback.",
            "current": {
                "expected_result": tc_data.get("expected_result", ""),
                "test_steps": current_steps_formatted,
            },
            "suggested": {
                "expected_result": new_result,
                "test_steps": current_steps_formatted,
            },
            "reason": f"Reviewer noted: {issue_comment or 'Expected result requires clarification.'}",
            "changes_summary": ["Updated Expected Result text with reviewer clarification"],
        }

    # 3. SQL / Source Mapping correction
    if "sql" in (issue_type or "").lower() or "source mapping" in (issue_type or "").lower():
        current_sql = tc_data.get("validation_sql", "")
        return {
            "correction_type": "SQL_MAPPING_CORRECTION",
            "title": "SQL & Source Mapping Refinement",
            "summary": "Ensure column aliases and joins match authoritative DSD field definitions.",
            "current": {
                "validation_sql": current_sql,
                "source_mapping": tc_data.get("source_column", ""),
            },
            "suggested": {
                "validation_sql": current_sql,
                "source_mapping": tc_data.get("source_column", ""),
                "note": "Verify that all column aliases match human-readable DSD Business Labels.",
            },
            "reason": f"Reviewer noted: {issue_comment or 'Review SQL query and business label aliases.'}",
            "changes_summary": ["Reviewed SQL alias mapping against DSD source fields"],
        }

    # 4. Generic / Test step correction
    suggested_steps_list = list(current_steps_list)
    if issue_comment:
        suggested_steps_list.append(f"{len(suggested_steps_list) + 1}. Verify: {issue_comment}")

    return {
        "correction_type": "GENERAL_CORRECTION",
        "title": "Scenario Step Correction",
        "summary": "Refined procedure incorporating reviewer feedback.",
        "current": {
            "test_steps": current_steps_formatted,
            "expected_result": tc_data.get("expected_result", ""),
        },
        "suggested": {
            "test_steps": "\n".join(suggested_steps_list),
            "expected_result": tc_data.get("expected_result", ""),
        },
        "reason": f"Incorporated reviewer observation: {issue_comment or 'Step refinement requested.'}",
        "changes_summary": ["Updated test steps based on reviewer input"],
    }


def generate_missing_scenario(
    what_to_test: str,
    dsd_reference: str,
    report_id: str = "PRV-INT-027",
    report_title: str = "Provider License Interface Report",
    existing_count: int = 10,
) -> Dict[str, Any]:
    """
    Generates a proposed new scenario from a user's requirement ("what to test" and "DSD reference").
    """
    clean_test = what_to_test.strip()
    clean_ref = dsd_reference.strip()

    category = "Custom Validation"
    test_id_prefix = "SPEC"
    clean_lower = clean_test.lower()

    if "retention" in clean_lower or "purge" in clean_lower:
        category = "Report Retention Validation"
        test_id_prefix = "RETN"
    elif "security" in clean_lower or "role" in clean_lower or "access" in clean_lower:
        category = "Security & Access Validation"
        test_id_prefix = "SECU"
    elif "format" in clean_lower or "layout" in clean_lower:
        category = "Layout Validation"
        test_id_prefix = "LAYO"
    elif "filter" in clean_lower or "selection" in clean_lower:
        category = "Selection Criteria Validation"
        test_id_prefix = "SELC"
    elif "header" in clean_lower:
        category = "Report Header Validation"
        test_id_prefix = "RHDR"

    rid_clean = re.sub(r'[^a-zA-Z0-9]', '', report_id)
    new_tc_id = f"{rid_clean}-{test_id_prefix}-{existing_count + 1:02d}"

    title = f"Verify {clean_test} for {report_id}"
    objective = f"Validate that {clean_test} operates strictly according to specification in {clean_ref}."

    test_steps = [
        f"1. Open the {report_id} specification at {clean_ref}.",
        f"2. Execute report {report_id} in the designated test environment.",
        f"3. Verify {clean_test} matches the documented DSD requirements.",
        f"4. Confirm that no unauthorized data exposure, corruption, or layout defects occur.",
        f"5. Capture screenshots and operational logs as verification evidence.",
    ]

    expected_result = (
        f"{clean_test.capitalize()} complies fully with DSD requirements documented at {clean_ref}. "
        f"All outputs and retention/security behaviors match expected criteria."
    )

    return {
        "test_case_id": new_tc_id,
        "report_id": report_id,
        "test_case_title": title,
        "category": category,
        "objective": objective,
        "execution_method": "Scheduled" if "PRV" in report_id else "On Request",
        "execution_tool": "IWA" if "PRV" in report_id else "Cognos Portal",
        "test_steps": "\n".join(test_steps),
        "expected_result": expected_result,
        "source_section": clean_ref.split("•")[0].strip() if "•" in clean_ref else clean_ref,
        "dsd_reference": clean_ref,
        "priority": "Medium",
        "review_status": "GENERATED",
        "version": 1,
        "scenario_order": (existing_count + 1) * 10,
    }


def compute_field_diffs(old_data: Dict[str, Any], new_data: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Computes human-readable diffs between two scenario revisions.
    """
    fields_to_track = [
        ("test_case_title", "Scenario Name"),
        ("objective", "Objective"),
        ("execution_method", "Execution Method"),
        ("execution_tool", "Execution Tool"),
        ("report_id", "Report ID"),
        ("test_steps", "Test Steps"),
        ("expected_result", "Expected Result"),
        ("review_comments", "Execution Comments"),
    ]

    diffs = []
    for key, label in fields_to_track:
        old_val = str(old_data.get(key, "") or "").strip()
        new_val = str(new_data.get(key, "") or "").strip()
        if old_val != new_val:
            diffs.append({
                "field": label,
                "from": old_val[:120] + ("..." if len(old_val) > 120 else ""),
                "to": new_val[:120] + ("..." if len(new_val) > 120 else ""),
            })
    return diffs


def record_history_entry(
    history_list: Optional[List[Dict[str, Any]]],
    version: int,
    action_type: str,
    status: str,
    author: str,
    summary: str,
    diffs: Optional[List[Dict[str, str]]] = None,
    issue_details: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Appends a new immutable history record to the scenario revision history.
    """
    history = list(history_list or [])
    now_iso = datetime.now(timezone.utc).isoformat()

    entry: Dict[str, Any] = {
        "version": version,
        "action": action_type,
        "status": status,
        "author": author or "Current User",
        "timestamp": now_iso,
        "summary": summary,
    }
    if diffs:
        entry["diffs"] = diffs
    if issue_details:
        entry["issue_details"] = issue_details

    history.append(entry)
    return history
