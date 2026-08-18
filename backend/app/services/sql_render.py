"""
Deterministic AST -> ANSI SQL renderer — Phase 4 (draft) / Phase 5 (final).

Takes ONLY a ValidatedAST (already passed through ast_builder.py — never a
raw ScenarioIntent) and renders a generic, ready-to-run SELECT statement.
No LLM involved anywhere in this module — it's a pure, deterministic
formatter, which is exactly what the Master System Prompt's "Compile-then-
Execute" design requires: the SQL text itself is never the model's output,
only a mechanical rendering of an already-validated structure.

Phase 4 uses this to produce a draft/preview verification_sql for each
scenario. Phase 5's "SQL Compiler" pipeline stage (after the Critic /
Reflection Loop) is expected to call this exact same function on the
final, critic-approved AST — there is no reason for two different
renderers, so this module is written to be that shared, authoritative
implementation from day one.
"""

from __future__ import annotations

from app.agents.schemas import ValidatedAST


def render_sql(ast: ValidatedAST) -> str:
    if not ast.is_valid:
        raise ValueError(
            "render_sql() called on an invalid AST — this should never "
            "happen; the caller must check ast.is_valid first. "
            f"Rejection reasons: {ast.rejection_reasons}"
        )

    select_clause = ", ".join(ast.select)
    lines = [f"SELECT {select_clause}", f"FROM {ast.from_table}"]

    for j in ast.joins:
        lines.append(f"{j['join_type']} JOIN {j['table']} ON {j['on']}")

    if ast.where:
        conditions = []
        for w in ast.where:
            col_ref = w['column']
            op = w["op"]
            if op in ("IS NULL", "IS NOT NULL"):
                conditions.append(f"{col_ref} {op}")
            else:
                conditions.append(f"{col_ref} {op} {w['value']}")
        lines.append("WHERE " + " AND ".join(conditions))

    if ast.group_by:
        lines.append("GROUP BY " + ", ".join(ast.group_by))
        
    if getattr(ast, "having", None):
        conditions = []
        for w in ast.having:
            col_ref = w['column']
            op = w["op"]
            if op in ("IS NULL", "IS NOT NULL"):
                conditions.append(f"{col_ref} {op}")
            else:
                conditions.append(f"{col_ref} {op} {w['value']}")
        lines.append("HAVING " + " AND ".join(conditions))

    if ast.order_by:
        lines.append("ORDER BY " + ", ".join(ast.order_by))

    return "\n".join(lines) + ";"
