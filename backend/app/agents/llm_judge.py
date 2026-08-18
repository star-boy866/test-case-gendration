"""
LLM-as-a-Judge Evaluation Pipeline — Phase 10.

The Master System Prompt (section 6) asks for "asynchronous evaluator
sub-agents" scoring generated scenarios for Completeness, Hallucination
Prevention, and Schema Adherence. This is DELIBERATELY separate from
Phase 5's Critic (app/agents/critic.py), which already checks exactly
these three concerns — but deterministically, not via LLM:

  - Schema Adherence:      critic.py's sql_schema_valid check (ast_valid)
  - Hallucination Prevention: enforced structurally by ast_builder.py —
                              a hallucinated scenario never reaches this
                              point at all
  - Completeness:          critic.py's business_rules_covered /
                              edge_cases_covered checks

Given that overlap, this module is NOT a second gate and NEVER blocks
generation or export — it would be actively harmful for an LLM grading
its own sibling agent's output to be able to override a deterministic,
auditable check. Instead, this is a genuinely complementary layer for the
one thing the deterministic Critic structurally cannot judge: whether the
scenario TEXT itself (not just its structure) reads as complete,
professional QA documentation a human would actually trust — a
qualitative judgment deterministic rules aren't well-suited to.

Runs "asynchronously" in the practical sense the spec means: AFTER the
Critic/Reflection Loop has already decided pass/fail and the response has
already been prepared, via FastAPI's BackgroundTasks (see api/generation.py)
so it never adds latency to the user-facing request. Results are stored
for audit/reporting, not consumed by any gating logic.

Same Callable[[str], str] LLM injection pattern as Phase 4/5 — fully
testable with a fake LLM, no live Ollama daemon required.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Optional


class JudgeParseError(Exception):
    """Raised when the LLM judge's response can't be parsed into scores."""


@dataclass
class JudgeScore:
    completeness: float          # 0.0-1.0
    hallucination_prevention: float  # 0.0-1.0 (1.0 = no hallucination concerns)
    schema_adherence: float      # 0.0-1.0
    rationale: str
    warnings: list = field(default_factory=list)

    @property
    def overall(self) -> float:
        return round((self.completeness + self.hallucination_prevention + self.schema_adherence) / 3, 3)

    def to_dict(self) -> dict:
        return {
            "completeness": self.completeness,
            "hallucination_prevention": self.hallucination_prevention,
            "schema_adherence": self.schema_adherence,
            "overall": self.overall,
            "rationale": self.rationale,
            "warnings": self.warnings,
        }


def build_judge_prompt(scenarios: list, context_slice: dict, requirement: str) -> str:
    scenarios_desc = "\n\n".join(
        f"Scenario {i + 1}: {s.get('test_scenario', '')}\n"
        f"Steps: {s.get('detailed_test_steps', '')}\n"
        f"Expected: {s.get('expected_results', '')}\n"
        f"SQL: {s.get('verification_sql', '')}"
        for i, s in enumerate(scenarios)
    )
    known_tables = ", ".join(context_slice.get("candidate_tables", [])) or "(none)"

    return f"""You are a senior QA reviewer for a healthcare SIT/QA test suite.
Score the following generated test scenarios against this original
requirement, using ONLY the information given — do not assume anything
about tables/columns beyond what's listed.

REQUIREMENT:
{requirement}

VERIFIED TABLES IN SCOPE: {known_tables}

GENERATED SCENARIOS:
{scenarios_desc}

Score three dimensions from 0.0 (poor) to 1.0 (excellent):
- completeness: do these scenarios, taken together, thoroughly address the requirement?
- hallucination_prevention: does the scenario TEXT (not the SQL, which is
  separately validated) make any claim about data/behavior that isn't
  supported by the requirement or the verified tables listed above?
  1.0 = no unsupported claims found.
- schema_adherence: do the scenario descriptions stay consistent with the
  verified tables listed above (never mentioning a table not listed)?

Respond with ONLY a JSON object (no prose, no markdown fences):
{{
  "completeness": 0.0-1.0,
  "hallucination_prevention": 0.0-1.0,
  "schema_adherence": 0.0-1.0,
  "rationale": "1-3 sentences explaining the scores",
  "warnings": ["any specific concerns worth a human's attention, or empty list"]
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
    raise JudgeParseError(f"Could not extract a JSON object from judge response: {raw[:300]}")


def _clamp01(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v))


def parse_judge_response(raw: str) -> JudgeScore:
    data = _extract_json_object(raw)
    if not isinstance(data, dict):
        raise JudgeParseError(f"Expected a JSON object, got: {type(data).__name__}")

    return JudgeScore(
        completeness=_clamp01(data.get("completeness", 0.0)),
        hallucination_prevention=_clamp01(data.get("hallucination_prevention", 0.0)),
        schema_adherence=_clamp01(data.get("schema_adherence", 0.0)),
        rationale=str(data.get("rationale", "")).strip(),
        warnings=[str(w) for w in data.get("warnings", []) if w],
    )


def run_llm_judge(
    scenarios: list,
    context_slice: dict,
    requirement: str,
    llm_call: Callable[[str], str],
) -> Optional[JudgeScore]:
    """
    Returns None (not a low score) if the batch is empty or the LLM call
    itself fails — a missing/failed judge evaluation should read as "no
    data available" in any dashboard consuming this, never as "scored
    zero," which would be misleading and could look like a real quality
    problem when it's actually just this optional layer being unavailable.
    """
    if not scenarios:
        return None

    prompt = build_judge_prompt(scenarios, context_slice, requirement)
    try:
        raw = llm_call(prompt)
        return parse_judge_response(raw)
    except JudgeParseError:
        return None
    except Exception:
        # Any LLM backend failure (e.g. OllamaUnavailableError) — this is a
        # non-gating, best-effort layer, so swallow it here rather than
        # letting a judge failure look like a pipeline failure. The caller
        # (generation.py, via BackgroundTasks) has nothing to report errors
        # TO at this point anyway, since the user-facing response already
        # went out.
        return None
