"""
Fast-Path Router — Phase 3.

Rules-based routing engine that recognizes standard, repetitive report QA
patterns (date/timestamp formatting, pagination, layout/header checks) and
returns boilerplate test scenarios instantly, bypassing the heavier
Context Minimizer -> Semantic Cache -> Planning Agent -> Generator loop
entirely. This is a real, if intentionally simple, rule engine — not a
placeholder — designed to be extended with more patterns over time without
touching the agentic pipeline at all.

Each rule is a (regex, scenario_builder) pair. Rules are checked in order;
the first match wins. No match means "not a fast-path case" — the caller
falls through to the normal pipeline (Context Minimizer -> ... -> Phase 4/5
generation).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class FastPathScenario:
    test_scenario: str
    detailed_test_steps: str
    expected_results: str
    verification_sql: str
    matched_rule: str


def _date_format_scenario(requirement: str) -> FastPathScenario:
    return FastPathScenario(
        test_scenario="Validate date/timestamp field formatting",
        detailed_test_steps=(
            "1. Identify all date/timestamp columns referenced in the report.\n"
            "2. Render the report and inspect each date/timestamp field.\n"
            "3. Confirm formatting matches the specified pattern (e.g. MM/DD/YYYY "
            "for dates, MM/DD/YYYY HH:MM:SS for timestamps)."
        ),
        expected_results=(
            "All date fields render as MM/DD/YYYY and all timestamp fields render "
            "as MM/DD/YYYY HH:MM:SS, with no raw ISO-8601 or database-native "
            "formatting leaking through to the report output."
        ),
        verification_sql=(
            "-- Placeholder: swap <TABLE> and <DATE_COLUMN> for the actual\n"
            "-- table/column identified via the Context Minimizer / Knowledge Base.\n"
            "SELECT <DATE_COLUMN> FROM <TABLE> WHERE <DATE_COLUMN> IS NOT NULL;"
        ),
        matched_rule="date_timestamp_format",
    )


def _pagination_scenario(requirement: str) -> FastPathScenario:
    return FastPathScenario(
        test_scenario="Validate report pagination behavior",
        detailed_test_steps=(
            "1. Generate a report with a result set larger than one page.\n"
            "2. Confirm the configured page size is honored on every page.\n"
            "3. Navigate to the last page and confirm the remainder renders "
            "correctly with no duplicated or dropped rows across page "
            "boundaries."
        ),
        expected_results=(
            "Every page (except possibly the last) contains exactly the "
            "configured page size of rows; total rows across all pages equals "
            "the full result set with no duplicates or omissions."
        ),
        verification_sql=(
            "-- Placeholder: swap <TABLE> for the actual table identified via\n"
            "-- the Context Minimizer / Knowledge Base.\n"
            "SELECT COUNT(*) AS total_rows FROM <TABLE>;"
        ),
        matched_rule="pagination",
    )


def _layout_header_scenario(requirement: str) -> FastPathScenario:
    return FastPathScenario(
        test_scenario="Validate standard report layout and column headers",
        detailed_test_steps=(
            "1. Generate the report.\n"
            "2. Compare rendered column headers, ordering, and section layout "
            "against the approved Report Design Document.\n"
            "3. Confirm no columns are missing, reordered, or mislabeled."
        ),
        expected_results=(
            "Rendered layout, column headers, and column order match the "
            "approved RDD exactly."
        ),
        verification_sql=(
            "-- Layout/header checks are structural, not data checks —\n"
            "-- no verification SQL applies. Compare rendered output directly\n"
            "-- against the RDD layout specification."
        ),
        matched_rule="layout_header",
    )


_RULES: list[tuple[re.Pattern, callable]] = [
    (re.compile(r"\b(date|timestamp|time)\s*(format|formatting)\b", re.IGNORECASE), _date_format_scenario),
    (re.compile(r"\bpagination\b|\bpage\s*siz(e|ing)\b", re.IGNORECASE), _pagination_scenario),
    (re.compile(r"\b(layout|header|column\s*order)\b", re.IGNORECASE), _layout_header_scenario),
]


def try_fast_path(requirement: str) -> FastPathScenario | None:
    """Returns a boilerplate scenario if the requirement matches a known
    standard pattern, else None (caller should fall through to the full
    pipeline)."""
    for pattern, builder in _RULES:
        if pattern.search(requirement or ""):
            return builder(requirement)
    return None
