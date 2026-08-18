"""
Generator Agent — Phase 4.

Given a ScenarioIntent + its already-validated AST (from ast_builder.py —
never a raw/unvalidated intent), asks an LLM to write the human-readable
parts of the test scenario: the title refinement, Detailed Test Steps, and
Expected Results. Grounding matters here — the prompt explicitly hands the
LLM the validated AST (real table/column names only) so its prose can't
reference anything hallucinated, even though prose itself isn't checked
against the KB the way SQL structure is.

verification_sql is NEVER produced by the LLM — it comes from
sql_render.render_sql() on the already-validated AST (see pipeline.py).
This module only ever asks the LLM for the three free-text fields.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from app.agents.schemas import ScenarioIntent, ValidatedAST


class GeneratorParseError(Exception):
    """Raised when the LLM's response can't be parsed into scenario content."""


def build_generator_prompt(intent: ScenarioIntent, ast: ValidatedAST) -> str:
    where_desc = "; ".join(
        f"{w['column']} {w['op']} {w.get('value', '')}".strip() for w in ast.where
    ) or "(no filter conditions)"
    joins_desc = "; ".join(f"joined to {j['table']} ON {j['on']}" for j in ast.joins) or "(no joins)"

    return f"""You are a healthcare QA test documentation writer. Write clear,
professional test documentation for the following ALREADY-VALIDATED query
structure. Do not invent any table, column, or business detail beyond what
is given here.

Scenario title (proposed): {intent.title}
Rationale: {intent.rationale}
Category: {intent.category}
Table: {ast.from_table}
Columns involved: {', '.join(ast.select)}
Filter conditions: {where_desc}
Joins: {joins_desc}

Respond with ONLY a JSON object (no prose, no markdown fences) with exactly
this shape:
{{
  "test_scenario": "a concise, professional scenario title (refine the proposed title if needed)",
  "detailed_test_steps": "numbered step-by-step instructions for a QA analyst to execute this validation manually",
  "expected_results": "precise, unambiguous description of what a passing result looks like"
}}
"""


def _extract_json_object(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise GeneratorParseError(f"Could not extract a JSON object from LLM response: {raw[:300]}")


def parse_generator_response(raw: str) -> dict:
    data = _extract_json_object(raw)
    if not isinstance(data, dict):
        raise GeneratorParseError(f"Expected a JSON object, got: {type(data).__name__}")

    required = ("test_scenario", "detailed_test_steps", "expected_results")
    missing = [f for f in required if not str(data.get(f, "")).strip()]
    if missing:
        raise GeneratorParseError(f"LLM response missing required field(s): {missing}")

    return {f: str(data[f]).strip() for f in required}


def generate_scenario_content(
    intent: ScenarioIntent,
    ast: ValidatedAST,
    llm_call: Callable[[str], str],
) -> dict:
    if not ast.is_valid:
        raise ValueError(
            "generate_scenario_content() called on an invalid AST — the "
            "caller must filter these out before reaching the Generator. "
            f"Rejection reasons: {ast.rejection_reasons}"
        )
    prompt = build_generator_prompt(intent, ast)
    raw = llm_call(prompt)
    return parse_generator_response(raw)
