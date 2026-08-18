"""
Planning Agent — Phase 4.

Given a minimized context slice (from context_minimizer.py) and a natural
language requirement, asks an LLM to propose a list of test scenario
INTENTS — not SQL, not final scenario text, just structured proposals of
what to test (title, category, target table/columns, filters). These
proposals are NOT trusted: every one is passed through ast_builder.py
before anything downstream treats it as real.

Per the spec's Semantic Cache design ("inject the match into the Planning
Agent's context window as a highly relevant Few-Shot Example" for a
partial cache hit), `few_shot_example` is an optional parameter here —
wired in by generation.py when semantic_cache.check_cache returns
"partial_hit".

The LLM call itself is injected as `llm_call: Callable[[str], str]` (see
services/ollama_client.py for the real implementation) so this entire
module is testable with a fake LLM returning canned JSON — no live Ollama
daemon required to verify prompt construction or response parsing.
"""

from __future__ import annotations

import json
import re
from typing import Callable, Optional

from app.agents.schemas import ScenarioIntent
from app.core.prompt_injection import sanitize_for_prompt_context

_VALID_CATEGORIES = {
    "valid_value_check", "null_check", "join_integrity",
    "format_check", "boundary_check", "duplicate_check",
}


class PlanningParseError(Exception):
    """Raised when the LLM's response can't be parsed into scenario intents."""


def build_planning_prompt(
    context_slice: dict,
    requirement: str,
    max_scenarios: int,
    few_shot_example: Optional[dict] = None,
) -> str:
    # Free-text fields below come from uploaded RDD/LDM content (Phase 1),
    # which may be a less-trusted source than whoever is running generation
    # right now — sanitize_for_prompt_context() neutralizes fence/tag
    # context-escape tricks without touching normal business language (see
    # core/prompt_injection.py's docstring for why this is sanitize-and-
    # continue rather than block-outright, unlike the user-supplied
    # `requirement` itself, which generation.py screens and REFUSES on
    # match before this function is ever called).
    tables_desc = "\n".join(
        f"- {t['table_name']}: {sanitize_for_prompt_context(t.get('description')) or '(no description)'}"
        for t in context_slice.get("tables", [])
    )
    columns_desc = "\n".join(
        f"- {c['table_name']}.{c['column_name']} ({sanitize_for_prompt_context(c.get('data_type')) or 'unknown type'}"
        f"{', ' + c['key_type'] if c.get('key_type') else ''})"
        for c in context_slice.get("columns", [])
    )
    joins_desc = "\n".join(
        f"- {j['from_table']}.{j['from_column']} = {j['to_table']}.{j['to_column']}"
        for j in context_slice.get("joins", [])
    ) or "(none)"
    valid_values_desc = "\n".join(
        f"- {v['table_name']}.{v['column_name']} = '{v['valid_value']}' ({sanitize_for_prompt_context(v.get('meaning')) or 'no meaning given'})"
        for v in context_slice.get("valid_values", [])
    ) or "(none)"
    rules_desc = "\n".join(
        f"- {sanitize_for_prompt_context(r.get('rule_text'))}" for r in context_slice.get("business_rules", [])
    ) or "(none)"

    few_shot_block = ""
    if few_shot_example:
        few_shot_block = (
            "\nA previous, similar requirement produced this scenario set "
            "(for reference/style only — do NOT copy table/column names from "
            "it if they don't appear in the schema below):\n"
            f"{json.dumps(few_shot_example.get('cached_payload', few_shot_example), indent=2)[:1500]}\n"
        )

    return f"""You are a healthcare QA test planning assistant. You may ONLY reference
tables and columns explicitly listed below — never invent a table, column,
or join that isn't listed. Anything you propose that isn't in this schema
will be automatically rejected.

VERIFIED SCHEMA (from the Knowledge Base for this report):

Tables:
{tables_desc}

Columns:
{columns_desc}

Verified joins:
{joins_desc}

Valid values:
{valid_values_desc}

Business rules:
{rules_desc}
{few_shot_block}
REQUIREMENT:
{requirement}

Propose up to {max_scenarios} distinct test scenarios covering this requirement.
Respond with ONLY a JSON array (no prose, no markdown fences) where each
element has exactly this shape:
{{
  "title": "short scenario title",
  "rationale": "why this scenario matters",
  "category": "one of: {', '.join(sorted(_VALID_CATEGORIES))}",
  "target_table": "table name from the schema above",
  "target_columns": ["column names from the schema above"],
  "filters": [{{"column": "...", "op": "=|!=|>|<|IS NULL|...", "value": "..."}}],
  "joins_needed": ["other table names from the schema above, if needed"]
}}
"""


def _extract_json_array(raw: str) -> list:
    """LLMs frequently wrap JSON in prose or markdown fences despite
    instructions. Extract the first top-level JSON array found."""
    raw = raw.strip()
    # Strip markdown code fences if present.
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise PlanningParseError(f"Could not extract a JSON array from LLM response: {raw[:300]}")


def parse_planning_response(raw: str) -> list[ScenarioIntent]:
    data = _extract_json_array(raw)
    if not isinstance(data, list):
        raise PlanningParseError(f"Expected a JSON array of scenario intents, got: {type(data).__name__}")

    intents: list[ScenarioIntent] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue  # skip malformed entries rather than failing the whole batch
        try:
            intents.append(ScenarioIntent(
                title=str(item.get("title", "")).strip() or f"Untitled scenario {i + 1}",
                rationale=str(item.get("rationale", "")).strip(),
                category=str(item.get("category", "")).strip() or "unspecified",
                target_table=str(item.get("target_table", "")).strip(),
                target_columns=[str(c) for c in item.get("target_columns", []) if c],
                filters=[f for f in item.get("filters", []) if isinstance(f, dict)],
                joins_needed=[str(t) for t in item.get("joins_needed", []) if t],
            ))
        except (TypeError, ValueError):
            continue  # malformed individual item — skip it, don't fail the batch

    return intents


def plan_scenarios(
    context_slice: dict,
    requirement: str,
    llm_call: Callable[[str], str],
    *,
    max_scenarios: int = 6,
    few_shot_example: Optional[dict] = None,
) -> list[ScenarioIntent]:
    prompt = build_planning_prompt(context_slice, requirement, max_scenarios, few_shot_example)
    raw = llm_call(prompt)
    return parse_planning_response(raw)[:max_scenarios]
