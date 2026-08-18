"""
LangGraph wrapper — Phase 4 (optional).

The Master System Prompt's open-source stack calls for an agentic
framework (LangGraph, CrewAI, or AutoGen). pipeline.py implements the
actual Planning Agent -> AST Builder -> Generator sequence as plain
Python specifically so it can be wrapped in a LangGraph StateGraph without
changing any underlying logic — each pipeline stage becomes one graph
node here.

Disclosed limitation: this sandbox has no network access to install
`langgraph`, so this module has been syntax-checked only, never actually
run. The import is deferred into `run_pipeline_via_langgraph()` itself
(not at module level) specifically so that importing this file doesn't
fail in an environment without langgraph installed — callers should
prefer `pipeline.run_pipeline()` directly unless they specifically want
the graph-based execution (e.g. for LangGraph's checkpointing/tracing
features), and should catch ImportError as a signal to fall back.

If/when this runs somewhere with langgraph installed, please verify it
produces IDENTICAL output to pipeline.run_pipeline() on the same inputs
before relying on it — that's the one thing I could not confirm here.
"""

from __future__ import annotations

from typing import Callable, Optional, TypedDict


class _PipelineState(TypedDict, total=False):
    context_slice: dict
    requirement: str
    llm_call: Callable[[str], str]
    max_scenarios: int
    few_shot_example: Optional[dict]
    scenarios: list
    warnings: list


def run_pipeline_via_langgraph(
    context_slice: dict,
    requirement: str,
    llm_call: Callable[[str], str],
    *,
    max_scenarios: int = 6,
    few_shot_example: Optional[dict] = None,
):
    """
    Same signature and return shape as pipeline.run_pipeline(). Builds a
    trivial 2-node linear StateGraph (plan -> build_and_generate) purely to
    satisfy the agentic-framework stack requirement; the actual logic in
    each node is a thin call into the already-tested functions in
    planning_agent.py / ast_builder.py / sql_render.py / generator_agent.py
    — this wrapper adds no new business logic of its own, by design, to
    minimize what's running untested.
    """
    try:
        from langgraph.graph import StateGraph, END
    except ImportError as e:
        raise ImportError(
            "langgraph is not installed. Use app.agents.pipeline.run_pipeline() "
            "directly instead, or `pip install langgraph`."
        ) from e

    from app.agents.ast_builder import build_ast
    from app.agents.generator_agent import generate_scenario_content, GeneratorParseError
    from app.agents.planning_agent import plan_scenarios, PlanningParseError
    from app.agents.schemas import GeneratedScenario
    from app.services.sql_render import render_sql

    def plan_node(state: _PipelineState) -> _PipelineState:
        try:
            intents = plan_scenarios(
                state["context_slice"], state["requirement"], state["llm_call"],
                max_scenarios=state["max_scenarios"],
                few_shot_example=state.get("few_shot_example"),
            )
        except PlanningParseError as e:
            return {**state, "scenarios": [], "warnings": [f"Planning Agent failed: {e}"], "_intents": []}
        return {**state, "_intents": intents, "warnings": []}

    def build_and_generate_node(state: _PipelineState) -> _PipelineState:
        intents = state.get("_intents", [])
        warnings = list(state.get("warnings", []))
        scenarios = []

        for intent in intents:
            ast = build_ast(intent, state["context_slice"])
            if not ast.is_valid:
                warnings.append(
                    f"Scenario '{intent.title}' dropped — failed AST validation: "
                    + "; ".join(ast.rejection_reasons)
                )
                continue
            sql = render_sql(ast)
            try:
                content = generate_scenario_content(intent, ast, state["llm_call"])
            except GeneratorParseError as e:
                warnings.append(f"Scenario '{intent.title}' dropped — Generator Agent failed: {e}")
                continue
            scenarios.append(GeneratedScenario(
                test_scenario=content["test_scenario"],
                detailed_test_steps=content["detailed_test_steps"],
                expected_results=content["expected_results"],
                verification_sql=sql,
                category=intent.category,
                ast_valid=True,
            ))

        return {**state, "scenarios": scenarios, "warnings": warnings}

    graph = StateGraph(_PipelineState)
    graph.add_node("plan", plan_node)
    graph.add_node("build_and_generate", build_and_generate_node)
    graph.set_entry_point("plan")
    graph.add_edge("plan", "build_and_generate")
    graph.add_edge("build_and_generate", END)
    compiled = graph.compile()

    result = compiled.invoke({
        "context_slice": context_slice,
        "requirement": requirement,
        "llm_call": llm_call,
        "max_scenarios": max_scenarios,
        "few_shot_example": few_shot_example,
    })
    return result["scenarios"], result["warnings"]
