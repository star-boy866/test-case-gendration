from __future__ import annotations
import difflib
from dataclasses import dataclass
from typing import Any
from pydantic import BaseModel

@dataclass
class DiffResult:
    report_id: str
    component: str
    object_id: str
    expected: Any
    actual: Any
    severity: str
    reason: str

    def format(self) -> str:
        return (
            f"Report: {self.report_id}\n"
            f"Component: {self.component}\n"
            f"Object: {self.object_id}\n"
            f"Expected:\n{self.expected}\n"
            f"Actual:\n{self.actual}\n"
            f"Severity:\n{self.severity}\n"
            f"Likely impact:\n{self.reason}\n"
        )

def normalize_string(s: str | None) -> str | None:
    if not s:
        return s
    # Normalize whitespace
    return " ".join(s.split())

def compare_lists_unordered(expected: list, actual: list) -> bool:
    return sorted(expected) == sorted(actual)

def compare_requirements(report_id: str, expected_reqs: list[dict], actual_reqs: list[dict]) -> list[DiffResult]:
    diffs = []
    exp_map = {r["requirement_id"]: r for r in expected_reqs}
    act_map = {r["requirement_id"]: r for r in actual_reqs}

    for req_id, exp_req in exp_map.items():
        if req_id not in act_map:
            diffs.append(DiffResult(
                report_id=report_id, component="Requirement", object_id=req_id,
                expected=exp_req, actual=None, severity="CRITICAL",
                reason="Requirement missing in generated output."
            ))
            continue
        
        act_req = act_map[req_id]
        
        # Critical checks
        if exp_req.get("source_table") != act_req.get("source_table"):
            diffs.append(DiffResult(
                report_id=report_id, component="Requirement", object_id=req_id,
                expected=exp_req.get("source_table"), actual=act_req.get("source_table"), severity="CRITICAL",
                reason="Fabricated or missing source table."
            ))
            
        if not compare_lists_unordered(exp_req.get("source_columns", []), act_req.get("source_columns", [])):
            diffs.append(DiffResult(
                report_id=report_id, component="Requirement", object_id=req_id,
                expected=exp_req.get("source_columns"), actual=act_req.get("source_columns"), severity="CRITICAL",
                reason="Fabricated or incorrect source column."
            ))
            
        if normalize_string(exp_req.get("processing_rules")) != normalize_string(act_req.get("processing_rules")):
            diffs.append(DiffResult(
                report_id=report_id, component="Requirement", object_id=req_id,
                expected=exp_req.get("processing_rules"), actual=act_req.get("processing_rules"), severity="CRITICAL",
                reason="Incorrect processing rule."
            ))
            
        # High checks
        if exp_req.get("source_page") != act_req.get("source_page"):
            diffs.append(DiffResult(
                report_id=report_id, component="Requirement", object_id=req_id,
                expected=exp_req.get("source_page"), actual=act_req.get("source_page"), severity="HIGH",
                reason="Missing or incorrect source page."
            ))
            
        if not compare_lists_unordered(exp_req.get("conflicts", []), act_req.get("conflicts", [])):
            diffs.append(DiffResult(
                report_id=report_id, component="Requirement", object_id=req_id,
                expected=exp_req.get("conflicts"), actual=act_req.get("conflicts"), severity="HIGH",
                reason="Missing or incorrect conflicts."
            ))
            
        # Medium checks
        if exp_req.get("requirement_area") != act_req.get("requirement_area"):
            diffs.append(DiffResult(
                report_id=report_id, component="Requirement", object_id=req_id,
                expected=exp_req.get("requirement_area"), actual=act_req.get("requirement_area"), severity="MEDIUM",
                reason="Category drift."
            ))
            
        # Low checks (whitespace/formatting in statement)
        if normalize_string(exp_req.get("statement")) != normalize_string(act_req.get("statement")):
            diffs.append(DiffResult(
                report_id=report_id, component="Requirement", object_id=req_id,
                expected=exp_req.get("statement"), actual=act_req.get("statement"), severity="LOW",
                reason="Wording/style/whitespace changes."
            ))

    for req_id in act_map:
        if req_id not in exp_map:
            diffs.append(DiffResult(
                report_id=report_id, component="Requirement", object_id=req_id,
                expected=None, actual=act_map[req_id], severity="CRITICAL",
                reason="Fabricated requirement appeared in output."
            ))

    return diffs

def compare_test_cases(report_id: str, expected_tcs: list[dict], actual_tcs: list[dict]) -> list[DiffResult]:
    diffs = []
    exp_map = {t["test_case_id"]: t for t in expected_tcs}
    act_map = {t["test_case_id"]: t for t in actual_tcs}

    for tc_id, exp_tc in exp_map.items():
        if tc_id not in act_map:
            diffs.append(DiffResult(
                report_id=report_id, component="TestCase", object_id=tc_id,
                expected=exp_tc, actual=None, severity="CRITICAL",
                reason="Missing test case."
            ))
            continue
            
        act_tc = act_map[tc_id]
        
        if not compare_lists_unordered(exp_tc.get("requirement_ids", []), act_tc.get("requirement_ids", [])):
            diffs.append(DiffResult(
                report_id=report_id, component="TestCase", object_id=tc_id,
                expected=exp_tc.get("requirement_ids"), actual=act_tc.get("requirement_ids"), severity="CRITICAL",
                reason="Test case linked to wrong requirement."
            ))

        if exp_tc.get("test_design_technique") != act_tc.get("test_design_technique"):
            diffs.append(DiffResult(
                report_id=report_id, component="TestCase", object_id=tc_id,
                expected=exp_tc.get("test_design_technique"), actual=act_tc.get("test_design_technique"), severity="HIGH",
                reason="Incorrect test-design technique."
            ))
            
        if exp_tc.get("priority") != act_tc.get("priority"):
            diffs.append(DiffResult(
                report_id=report_id, component="TestCase", object_id=tc_id,
                expected=exp_tc.get("priority"), actual=act_tc.get("priority"), severity="MEDIUM",
                reason="Priority drift."
            ))
            
        if normalize_string(exp_tc.get("preconditions")) != normalize_string(act_tc.get("preconditions")):
             diffs.append(DiffResult(
                report_id=report_id, component="TestCase", object_id=tc_id,
                expected=exp_tc.get("preconditions"), actual=act_tc.get("preconditions"), severity="LOW",
                reason="Precondition wording changed."
            ))

    for tc_id in act_map:
        if tc_id not in exp_map:
            diffs.append(DiffResult(
                report_id=report_id, component="TestCase", object_id=tc_id,
                expected=None, actual=act_map[tc_id], severity="CRITICAL",
                reason="Fabricated test case."
            ))
            
    return diffs

def compare_coverage(report_id: str, expected_cov: dict, actual_cov: dict) -> list[DiffResult]:
    diffs = []
    
    # Coverage must be independently recalculated in the test wrapper, but here we just diff the models
    if expected_cov.get("total_dsd_requirements") != actual_cov.get("total_dsd_requirements"):
        diffs.append(DiffResult(
            report_id=report_id, component="Coverage", object_id="total_dsd_requirements",
            expected=expected_cov.get("total_dsd_requirements"), actual=actual_cov.get("total_dsd_requirements"), severity="CRITICAL",
            reason="Incorrect total requirement count."
        ))
        
    if not compare_lists_unordered(expected_cov.get("covered_requirement_ids", []), actual_cov.get("covered_requirement_ids", [])):
        diffs.append(DiffResult(
            report_id=report_id, component="Coverage", object_id="covered_requirement_ids",
            expected=expected_cov.get("covered_requirement_ids"), actual=actual_cov.get("covered_requirement_ids"), severity="CRITICAL",
            reason="Covered requirement IDs mismatch."
        ))
        
    if abs(expected_cov.get("coverage_percentage", 0.0) - actual_cov.get("coverage_percentage", 0.0)) > 0.1:
        diffs.append(DiffResult(
            report_id=report_id, component="Coverage", object_id="coverage_percentage",
            expected=expected_cov.get("coverage_percentage"), actual=actual_cov.get("coverage_percentage"), severity="CRITICAL",
            reason="Incorrect coverage percentage."
        ))

    return diffs

def compare_traceability(report_id: str, expected_trace: dict, actual_trace: dict) -> list[DiffResult]:
    diffs = []
    
    exp_maps = {m["requirement_id"]: m for m in expected_trace.get("mappings", [])}
    act_maps = {m["requirement_id"]: m for m in actual_trace.get("mappings", [])}
    
    for req_id, exp_map in exp_maps.items():
        if req_id not in act_maps:
            diffs.append(DiffResult(
                report_id=report_id, component="Traceability", object_id=req_id,
                expected=exp_map, actual=None, severity="CRITICAL",
                reason="Missing traceability mapping."
            ))
            continue
            
        act_map = act_maps[req_id]
        if exp_map.get("xml_path") != act_map.get("xml_path"):
            diffs.append(DiffResult(
                report_id=report_id, component="Traceability", object_id=req_id,
                expected=exp_map.get("xml_path"), actual=act_map.get("xml_path"), severity="CRITICAL",
                reason="Incorrect XML mapping."
            ))
            
    for req_id in act_maps:
        if req_id not in exp_maps:
            diffs.append(DiffResult(
                report_id=report_id, component="Traceability", object_id=req_id,
                expected=None, actual=act_maps[req_id], severity="CRITICAL",
                reason="Fabricated traceability mapping."
            ))
            
    return diffs
