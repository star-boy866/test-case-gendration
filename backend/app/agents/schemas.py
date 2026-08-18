"""
Shared types for the Phase 4 agent pipeline — Planning Agent -> AST Builder
-> Generator.

Kept in one small module (rather than scattered across each agent file) so
the pipeline's data contracts are visible in one place, and so ast_builder.py
doesn't need to import planning_agent.py just to reference its output type.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class ScenarioIntent:
    """One proposed test scenario, as planned by the Planning Agent — before
    any SQL exists. `filters` and similar fields are proposed by the LLM and
    are NOT yet trusted; AST Builder is what validates them against the real
    Knowledge Base."""

    title: str
    rationale: str
    category: str  # e.g. "valid_value_check" | "null_check" | "join_integrity" | "format_check" | "boundary_check"
    target_table: str
    target_columns: list[str] = field(default_factory=list)
    filters: list[dict] = field(default_factory=list)  # [{"column": str, "op": str, "value": str}, ...]
    joins_needed: list[str] = field(default_factory=list)  # table names the scenario also needs, beyond target_table
    group_by: list[str] = field(default_factory=list)
    order_by: list[str] = field(default_factory=list)
    having: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidatedAST:
    """Output of ast_builder.build_ast: either a validated, KB-grounded AST
    ready for SQL rendering, or a rejection with explicit reasons — never a
    silently-corrected guess."""

    is_valid: bool
    select: list[str] = field(default_factory=list)
    from_table: str | None = None
    joins: list[dict] = field(default_factory=list)  # [{"table": str, "on": str, "join_type": str}, ...]
    where: list[dict] = field(default_factory=list)   # normalized filters, same shape as ScenarioIntent.filters
    order_by: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    having: list[dict] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GeneratedScenario:
    """Final, complete output for one scenario — matches the 5-column Excel
    Scenario Output Specification (SL# is assigned by the caller, not here).

    `referenced_tables`/`referenced_columns` are carried through from the
    ValidatedAST that produced this scenario (Phase 4), specifically so the
    Critic (Phase 5) can check schema adherence and business-rule coverage
    directly against known-good data rather than re-parsing verification_sql
    text — parsing SQL back out of a string to re-derive what it references
    is exactly the kind of fragile, error-prone step this architecture is
    designed to avoid."""

    test_scenario: str
    detailed_test_steps: str
    expected_results: str
    verification_sql: str
    category: str
    ast_valid: bool
    referenced_tables: list[str] = field(default_factory=list)
    referenced_columns: list[str] = field(default_factory=list)  # "TABLE.COLUMN" strings
    validation_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
