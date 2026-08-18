"""
Reflection Loop — Phase 5.

Implements the Master System Prompt's self-correction loop: "If any
checklist item fails, the state resets and loops back to the Generator
with explicit error logs for automated self-healing before reaching the
interface."

Two distinct failure modes get two distinct repair strategies, because
"loop back to the Generator" isn't equally right for both:

1. Coverage gaps (business_rules_covered / edge_cases_covered failing) —
   the EXISTING scenarios aren't wrong, there just aren't enough of them.
   The fix is asking the Planning Agent for MORE scenarios targeting
   specifically what's missing, with the gap spelled out explicitly in the
   prompt — not regenerating text for scenarios that were already fine.

2. Mechanical defects (no_duplicate_scenarios failing on exact-duplicate
   SQL) — deterministically dedupe rather than spend an LLM call asking it
   to notice its own duplicate.

sql_schema_valid failing would mean a scenario with ast_valid=False
reached the Critic, which should be structurally impossible per
pipeline.py's design (see critic.py's docstring) — that's a pipeline bug,
not something a reflection loop can fix by asking the LLM to try again, so
it's treated as a hard stop rather than an infinite retry.

Bounded by max_iterations so a persistently-uncoverable gap (e.g. the LLM
just can't produce a scenario for an oddly-worded business rule) fails
loud with a clear log rather than looping forever.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.agents.critic import evaluate, CriticReport
from app.agents.pipeline import build_scenario_from_intent
from app.agents.planning_agent import plan_scenarios, PlanningParseError
from app.agents.schemas import GeneratedScenario


@dataclass
class ReflectionResult:
    scenarios: list[GeneratedScenario]
    critic_report: CriticReport
    iterations_used: int
    reflection_log: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "critic_report": self.critic_report.to_dict(),
            "iterations_used": self.iterations_used,
            "reflection_log": self.reflection_log,
        }


def _dedupe_exact_sql(scenarios: list[GeneratedScenario]) -> tuple[list[GeneratedScenario], list[str]]:
    seen: set[str] = set()
    kept: list[GeneratedScenario] = []
    log: list[str] = []
    for s in scenarios:
        normalized = " ".join(s.verification_sql.lower().split())
        if normalized in seen:
            log.append(
                f"Dropped duplicate scenario '{s.test_scenario}' "
                f"(identical verification SQL to an earlier scenario)."
            )
            continue
        seen.add(normalized)
        kept.append(s)
    return kept, log


def _extract_uncovered_rule_texts(issues: list[str]) -> list[str]:
    texts = []
    for issue in issues:
        if issue.startswith("Business rule not covered") and '"' in issue:
            texts.append(issue.split('"')[1])
    return texts


def _build_gap_requirement(
    original_requirement: str,
    uncovered_rule_texts: list[str],
    needs_edge_case: bool,
) -> str:
    gap_desc = "\n".join(f"- {r}" for r in uncovered_rule_texts) or "(none specifically listed)"
    edge_hint = (
        "\nAlso propose at least one scenario in category 'null_check', "
        "'boundary_check', or 'duplicate_check' if none is already present."
        if needs_edge_case else ""
    )
    return (
        f"{original_requirement}\n\n"
        f"ADDITIONAL INSTRUCTION: a prior pass over this same requirement "
        f"did NOT adequately cover the following verified business rule(s) "
        f"— propose scenario(s) that specifically address them, using only "
        f"tables/columns from the schema above:\n{gap_desc}{edge_hint}"
    )


def run_reflection_loop(
    scenarios: list[GeneratedScenario],
    context_slice: dict,
    requirement: str,
    llm_call: Callable[[str], str],
    *,
    max_iterations: int = 2,
    max_scenarios: int = 6,
) -> ReflectionResult:
    log: list[str] = []
    current = list(scenarios)
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        report = evaluate(current, context_slice)
        log.append(f"Iteration {iteration}: critic score {report.score} (passed={report.passed}).")

        if report.passed:
            return ReflectionResult(
                scenarios=current, critic_report=report,
                iterations_used=iteration - 1, reflection_log=log,
            )

        if not report.checklist.get("sql_schema_valid", True):
            log.append(
                "sql_schema_valid failed — this indicates a pipeline bug "
                "upstream (a scenario with ast_valid=False should never "
                "reach the Critic), not something reflection can fix by "
                "retrying. Stopping without further iterations."
            )
            break

        made_progress = False

        # Step 1: mechanically fix what's mechanically fixable.
        if not report.checklist.get("no_duplicate_scenarios", True):
            before = len(current)
            current, dedupe_log = _dedupe_exact_sql(current)
            log.extend(dedupe_log)
            made_progress = made_progress or (len(current) < before)

        # Step 2: if coverage is still short and there's room, ask the
        # Planning Agent for more, with the specific gap spelled out.
        needs_more_rules = not report.checklist.get("business_rules_covered", True)
        needs_edge_case = not report.checklist.get("edge_cases_covered", True)

        if (needs_more_rules or needs_edge_case) and len(current) < max_scenarios:
            gap_requirement = _build_gap_requirement(
                requirement,
                _extract_uncovered_rule_texts(report.issues),
                needs_edge_case,
            )
            try:
                new_intents = plan_scenarios(
                    context_slice, gap_requirement, llm_call,
                    max_scenarios=max_scenarios - len(current),
                )
            except PlanningParseError as e:
                log.append(f"Gap-filling Planning Agent call failed: {e}")
                new_intents = []

            for intent in new_intents:
                scenario, warning = build_scenario_from_intent(intent, context_slice, llm_call)
                if scenario is not None:
                    current.append(scenario)
                    log.append(f"Gap-fill scenario added: '{scenario.test_scenario}'.")
                    made_progress = True
                else:
                    log.append(f"Gap-fill attempt dropped: {warning}")

        if not made_progress:
            log.append(
                "No progress made this iteration (no duplicates to remove, "
                "no new scenarios successfully added) — stopping early "
                "rather than repeating an identical failed iteration."
            )
            break

    final_report = evaluate(current, context_slice)
    log.append(
        f"Reflection loop ended after {min(iteration, max_iterations)} "
        f"iteration(s) — final critic score {final_report.score} "
        f"(passed={final_report.passed})."
    )
    return ReflectionResult(
        scenarios=current, critic_report=final_report,
        iterations_used=iteration, reflection_log=log,
    )
