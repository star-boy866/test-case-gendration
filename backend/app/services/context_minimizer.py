"""
Context Minimizer / Schema-Linking Reduce Layer — Phase 3.

Given a report_id's full Knowledge Base (which may span many tables) and a
natural-language requirement, isolate only the tables/columns/joins/
valid-values/business-rules actually relevant to that requirement, so a
future Planning/Generator agent (Phase 4) gets a compressed, high-signal
context slice instead of the entire schema — fighting LLM attention
degradation and token bloat per the Master System Prompt.

Design note: the matching logic (`_select_context`) is a PURE function
over a plain dict shaped like `knowledge_base.get_knowledge_base_summary`'s
return value. It has no database dependency, which makes it directly unit
testable. `minimize_context` is a thin wrapper that fetches the KB from
the DB and delegates to the pure function.

Hallucination-prevention posture: if no keyword in the requirement matches
anything in the Knowledge Base, this does NOT silently return an empty
(and therefore misleading) context — it fails OPEN to the full KB and
attaches a warning, on the theory that over-including known-real metadata
is safe while guessing a subset is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import TYPE_CHECKING

from app.services.embeddings import tokenize

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class ContextSlice:
    report_id: str
    requirement: str
    candidate_tables: list[str] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    columns: list[dict] = field(default_factory=list)
    joins: list[dict] = field(default_factory=list)
    valid_values: list[dict] = field(default_factory=list)
    business_rules: list[dict] = field(default_factory=list)
    directly_matched_tables: list[str] = field(default_factory=list)
    join_expanded_tables: list[str] = field(default_factory=list)
    full_kb_counts: dict = field(default_factory=dict)
    reduced_counts: dict = field(default_factory=dict)
    reduction_ratio: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _select_context(kb: dict, report_id: str, requirement: str) -> ContextSlice:
    full_counts = {
        "tables": len(kb["tables"]),
        "columns": len(kb["columns"]),
        "joins": len(kb["joins"]),
        "valid_values": len(kb["valid_values"]),
        "business_rules": len(kb["business_rules"]),
    }

    req_tokens = set(tokenize(requirement))

    # Step 1: direct matches — table names, column names, valid-value
    # "meanings" (business-concept language, e.g. "swipe card issuance"
    # matching SWIPE_CARD_IND's valid-value meaning even if the column name
    # itself isn't mentioned), and business-rule text.
    directly_matched: set[str] = set()

    for t in kb["tables"]:
        if set(tokenize(t["table_name"])) & req_tokens:
            directly_matched.add(t["table_name"])

    for c in kb["columns"]:
        name_tokens = set(tokenize(c["column_name"])) | set(tokenize(c["table_name"]))
        if name_tokens & req_tokens:
            directly_matched.add(c["table_name"])

    for v in kb["valid_values"]:
        meaning_tokens = set(tokenize(v.get("meaning") or ""))
        value_tokens = set(tokenize(v.get("valid_value") or ""))
        if (meaning_tokens | value_tokens) & req_tokens:
            directly_matched.add(v["table_name"])

    for r in kb["business_rules"]:
        rule_tokens = set(tokenize(r.get("rule_text") or ""))
        if rule_tokens & req_tokens and r.get("related_table"):
            directly_matched.add(r["related_table"])

    # Step 2: one-hop join expansion. Deliberately NOT transitive closure —
    # pulling in every table reachable via any chain of joins would defeat
    # the purpose of minimization. "Mandatory cross-reference join paths"
    # means the immediate join partners of a matched table.
    join_expanded: set[str] = set()
    for j in kb["joins"]:
        if j["from_table"] in directly_matched and j["to_table"] not in directly_matched:
            join_expanded.add(j["to_table"])
        if j["to_table"] in directly_matched and j["from_table"] not in directly_matched:
            join_expanded.add(j["from_table"])

    candidate_tables = directly_matched | join_expanded

    warnings: list[str] = []
    if not candidate_tables and kb["tables"]:
        candidate_tables = {t["table_name"] for t in kb["tables"]}
        warnings.append(
            "No table/column/business-rule keywords in the requirement "
            "matched the Knowledge Base for this report_id — falling back "
            "to the FULL knowledge base rather than guessing a subset."
        )

    tables = [t for t in kb["tables"] if t["table_name"] in candidate_tables]
    columns = [c for c in kb["columns"] if c["table_name"] in candidate_tables]
    joins = [
        j for j in kb["joins"]
        if j["from_table"] in candidate_tables and j["to_table"] in candidate_tables
    ]
    valid_values = [v for v in kb["valid_values"] if v["table_name"] in candidate_tables]
    business_rules = [
        r for r in kb["business_rules"]
        if r.get("related_table") in candidate_tables or r.get("related_table") is None
    ]

    reduced_counts = {
        "tables": len(tables),
        "columns": len(columns),
        "joins": len(joins),
        "valid_values": len(valid_values),
        "business_rules": len(business_rules),
    }
    reduction_ratio = {
        k: (round(reduced_counts[k] / full_counts[k], 3) if full_counts[k] else 1.0)
        for k in full_counts
    }

    return ContextSlice(
        report_id=report_id,
        requirement=requirement,
        candidate_tables=sorted(candidate_tables),
        tables=tables,
        columns=columns,
        joins=joins,
        valid_values=valid_values,
        business_rules=business_rules,
        directly_matched_tables=sorted(directly_matched),
        join_expanded_tables=sorted(join_expanded),
        full_kb_counts=full_counts,
        reduced_counts=reduced_counts,
        reduction_ratio=reduction_ratio,
        warnings=warnings,
    )


def minimize_context(db: Session, report_id: str, requirement: str) -> ContextSlice:
    # Deferred import: app.services.knowledge_base transitively imports the
    # ORM models (which require sqlalchemy at class-definition time), while
    # `_select_context` above is a pure function with no DB dependency at
    # all. Deferring this import keeps this module importable — and
    # `_select_context` directly unit-testable — even in environments
    # without sqlalchemy installed.
    from app.services.knowledge_base import get_knowledge_base_summary

    kb = get_knowledge_base_summary(db, report_id)
    return _select_context(kb, report_id, requirement)
