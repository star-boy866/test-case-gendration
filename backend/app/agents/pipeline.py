"""
Pipeline orchestrator — Phase 4.

Wires the full generation sequence for a single request:

  Planning Agent (LLM) -> [per proposed scenario intent] ->
    AST Builder (deterministic validation against the KB) ->
      if invalid: DROP the scenario, keep the rejection reason as a warning
      if valid:  SQL Renderer (deterministic) -> Generator Agent (LLM) ->
                 assembled GeneratedScenario

This is implemented as plain, sequential Python — not a LangGraph/CrewAI
graph — despite the Master System Prompt listing those frameworks in the
open-source stack. That's a deliberate, disclosed choice: this sandbox has
no network access to install langgraph or crewai, so wiring this pipeline
through either would be entirely untestable here. The pipeline is written
as small, composable functions specifically so it CAN be wrapped in a
LangGraph StateGraph later (each function becomes one node) without
changing any of the underlying logic — see agents/langgraph_pipeline.py
for that optional wrapper, which degrades to calling this module directly
if langgraph isn't installed.

Hallucination prevention is enforced structurally, not just by convention:
a scenario intent that fails AST validation NEVER reaches the Generator
Agent — there is no code path where unvalidated table/column references
become scenario text or SQL.
"""

from __future__ import annotations

from typing import Callable, Optional

from app.agents.ast_builder import build_ast
from app.agents.generator_agent import generate_scenario_content, GeneratorParseError
from app.agents.planning_agent import plan_scenarios, PlanningParseError
from app.agents.schemas import GeneratedScenario
from app.services.sql_render import render_sql


def build_scenario_from_intent(
    intent,
    context_slice: dict,
    llm_call: Callable[[str], str],
):
    """
    Runs one ScenarioIntent through AST Builder -> SQL Renderer -> Generator
    Agent. Returns (GeneratedScenario, None) on success, or (None,
    warning_message) if the intent was dropped at any stage.

    Extracted out of run_pipeline()'s loop body so reflection_loop.py's
    gap-filling step can build additional scenarios the exact same way,
    rather than re-implementing (and risking drift from) this sequence.
    """
    ast = build_ast(intent, context_slice)

    if not ast.is_valid:
        return None, (
            f"Scenario '{intent.title}' dropped — failed AST validation: "
            + "; ".join(ast.rejection_reasons)
        )

    try:
        sql = render_sql(ast)
    except ValueError as e:
        # Should be unreachable (render_sql only raises on is_valid=False,
        # which we already checked), but never let a rendering bug crash
        # the whole batch — drop just this scenario with a clear warning.
        return None, f"Scenario '{intent.title}' dropped — SQL rendering error: {e}"

    try:
        content = generate_scenario_content(intent, ast, llm_call)
    except GeneratorParseError as e:
        return None, f"Scenario '{intent.title}' dropped — Generator Agent failed: {e}"

    referenced_tables = sorted({ast.from_table.split()[0], *(j["table"].split()[0] for j in ast.joins)})
    referenced_columns = sorted({
        col for col in ast.select
    } | {
        w['column'] for w in ast.where
    })

    return GeneratedScenario(
        test_scenario=content["test_scenario"],
        detailed_test_steps=content["detailed_test_steps"],
        expected_results=content["expected_results"],
        verification_sql=sql,
        category=intent.category,
        ast_valid=True,
        referenced_tables=referenced_tables,
        referenced_columns=referenced_columns,
        validation_warnings=[],
    ), None


def run_pipeline(
    context_slice: dict,
    requirement: str,
    llm_call: Callable[[str], str],
    *,
    max_scenarios: int = 6,
    few_shot_example: Optional[dict] = None,
) -> tuple[list[GeneratedScenario], list[str]]:
    """
    Returns (scenarios, pipeline_warnings). `pipeline_warnings` includes
    every AST rejection reason and every Generator parse failure — nothing
    fails silently, but a single bad LLM proposal never takes down the
    whole batch.
    """
    warnings: list[str] = []

    try:
        intents = plan_scenarios(
            context_slice, requirement, llm_call,
            max_scenarios=max_scenarios, few_shot_example=few_shot_example,
        )
    except PlanningParseError as e:
        return [], [f"Planning Agent failed: {e}"]

    if not intents:
        return [], ["Planning Agent proposed zero scenarios for this requirement."]

    scenarios: list[GeneratedScenario] = []

    for intent in intents:
        scenario, warning = build_scenario_from_intent(intent, context_slice, llm_call)
        if scenario is not None:
            scenarios.append(scenario)
        else:
            warnings.append(warning)

    return scenarios, warnings
