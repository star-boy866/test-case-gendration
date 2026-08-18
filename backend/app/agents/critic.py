"""
Critic Agent — Phase 5.

Implements the Master System Prompt's 4-point Boolean checklist verbatim:
  1. Are all business rules in the verified Design Document fully accounted for?
  2. Does the verification SQL use only valid columns/tables present in the LDM?
  3. Are there overlapping or duplicate scenarios?
  4. Are explicit negative conditions and edge cases (null fields, boundary
     lengths) properly covered?

DESIGN CHOICE, stated plainly: this Critic is fully deterministic/rule-based
rather than LLM-based. The spec calls it a "Critic/Judge Agent," which
could imply an LLM doing qualitative review — that's a legitimate reading,
and Section 6's "LLM-as-a-Judge Evaluation Pipeline" (async evaluator
sub-agents scoring Completeness/Hallucination Prevention/Schema Adherence)
is exactly that, explicitly scoped to Phase 10 in this build plan. For
THIS checklist specifically, every one of the four items is something a
deterministic check can answer more reliably and auditably than an LLM
judging its own (or a sibling agent's) output — which matters a lot in a
HIPAA-adjacent compliance context. An LLM-based qualitative pass remains a
reasonable Phase 10 addition on TOP of this, not a replacement for it.

Every check operates on GeneratedScenario.referenced_tables/columns (set
by pipeline.py from the already-validated AST) rather than re-parsing
verification_sql text — parsing SQL back out of a string to figure out
what it references is exactly the kind of fragile step this architecture
avoids elsewhere, so the Critic doesn't reintroduce it here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.embeddings import HashingEmbedder
from app.agents.schemas import GeneratedScenario

_DUPLICATE_TITLE_DISTANCE_THRESHOLD = 0.05  # near-identical wording
_EDGE_CASE_CATEGORIES = {"null_check", "boundary_check", "duplicate_check"}


@dataclass
class CriticReport:
    passed: bool
    score: float  # fraction of the 4 checklist items that passed, 0.0-1.0
    checklist: dict = field(default_factory=dict)  # {"business_rules_covered": bool, ...}
    issues: list = field(default_factory=list)  # human-readable explanations, one per failure

    def to_dict(self) -> dict:
        return {"passed": self.passed, "score": self.score, "checklist": self.checklist, "issues": self.issues}


def _check_business_rules_covered(scenarios: list[GeneratedScenario], context_slice: dict) -> tuple[bool, list[str]]:
    rules = context_slice.get("business_rules", [])
    if not rules:
        return True, []  # nothing to cover — vacuously satisfied

    covered_tables = set()
    covered_columns = set()
    for s in scenarios:
        covered_tables.update(s.referenced_tables)
        covered_columns.update(s.referenced_columns)

    issues = []
    for rule in rules:
        table = rule.get("related_table")
        column = rule.get("related_column")
        col_ref = f"{table}.{column}" if table and column else None

        if col_ref:
            # A column-specific rule requires column-level coverage — being
            # in the same TABLE as some unrelated scenario doesn't count.
            touched = col_ref in covered_columns
        elif table:
            # Table-level rule (no specific column given): table match is
            # the most precise signal available.
            touched = table in covered_tables
        else:
            touched = False  # a rule with no table/column reference at all can't be checked

        if not touched:
            issues.append(
                f"Business rule not covered by any scenario: "
                f"\"{rule.get('rule_text', '(no text)')}\" "
                f"(related to {table or '?'}.{column or '?'})"
            )

    return (len(issues) == 0), issues


def _check_sql_schema_valid(scenarios: list[GeneratedScenario]) -> tuple[bool, list[str]]:
    # Defense-in-depth re-verification: every scenario reaching the Critic
    # should already have ast_valid=True, since pipeline.py only ever
    # constructs a GeneratedScenario from a validated AST. This check exists
    # to catch a REGRESSION in that guarantee, not because it's expected to
    # ever fail in normal operation.
    issues = [
        f"Scenario '{s.test_scenario}' has ast_valid=False — this should be "
        f"structurally impossible; pipeline.py must have a bug if this fires."
        for s in scenarios if not s.ast_valid
    ]
    return (len(issues) == 0), issues


def _check_no_duplicate_scenarios(scenarios: list[GeneratedScenario]) -> tuple[bool, list[str]]:
    issues = []

    # Exact-duplicate SQL (normalized whitespace/case) — a strong signal.
    seen_sql: dict[str, str] = {}
    for s in scenarios:
        normalized = " ".join(s.verification_sql.lower().split())
        if normalized in seen_sql:
            issues.append(
                f"Scenarios '{seen_sql[normalized]}' and '{s.test_scenario}' "
                f"have identical verification SQL."
            )
        else:
            seen_sql[normalized] = s.test_scenario

    # Near-duplicate titles via the same hashing embedder used by the
    # semantic cache (Phase 3) — reused here rather than reinvented.
    if len(scenarios) > 1:
        embedder = HashingEmbedder(dim=64)
        vectors = embedder.embed_batch([s.test_scenario for s in scenarios])
        for i in range(len(scenarios)):
            for j in range(i + 1, len(scenarios)):
                dist = float(((vectors[i] - vectors[j]) ** 2).sum() ** 0.5)
                if dist <= _DUPLICATE_TITLE_DISTANCE_THRESHOLD:
                    issues.append(
                        f"Scenarios '{scenarios[i].test_scenario}' and "
                        f"'{scenarios[j].test_scenario}' have near-identical titles."
                    )

    return (len(issues) == 0), issues


def _check_edge_cases_covered(scenarios: list[GeneratedScenario], context_slice: dict) -> tuple[bool, list[str]]:
    # Heuristic, disclosed: edge-case coverage is only REQUIRED when the
    # schema gives a concrete signal that edge cases matter — a constrained
    # value domain (valid_values present) or a primary key (worth a
    # null/duplicate check). With no such signal, this check is vacuously
    # satisfied rather than demanding edge-case scenarios out of nowhere.
    has_valid_value_domain = bool(context_slice.get("valid_values"))
    has_primary_key = any(c.get("key_type") == "PK" for c in context_slice.get("columns", []))

    if not (has_valid_value_domain or has_primary_key):
        return True, []

    categories_present = {s.category for s in scenarios}
    if categories_present & _EDGE_CASE_CATEGORIES:
        return True, []

    return False, [
        "The schema has a constrained value domain and/or a primary key, "
        "but no scenario covers null/boundary/duplicate edge cases "
        f"(categories present: {sorted(categories_present) or ['none']})."
    ]


def evaluate(scenarios: list[GeneratedScenario], context_slice: dict) -> CriticReport:
    checks = {
        "business_rules_covered": _check_business_rules_covered(scenarios, context_slice),
        "sql_schema_valid": _check_sql_schema_valid(scenarios),
        "no_duplicate_scenarios": _check_no_duplicate_scenarios(scenarios),
        "edge_cases_covered": _check_edge_cases_covered(scenarios, context_slice),
    }

    checklist = {name: passed for name, (passed, _) in checks.items()}
    issues = [issue for _, (_, issue_list) in checks.items() for issue in issue_list]
    score = sum(checklist.values()) / len(checklist) if checklist else 0.0

    return CriticReport(
        passed=all(checklist.values()),
        score=round(score, 3),
        checklist=checklist,
        issues=issues,
    )
