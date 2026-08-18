# agents/

Multi-agent pipeline: Planning Agent -> AST Builder -> Generator (Phase 4)
-> Critic -> Reflection Loop (Phase 5) -> LLM-as-Judge (Phase 10,
non-gating). All phases on the original roadmap delivered except Phase 9
(RBAC/security hardening — not yet started, skipped ahead to Phase 10 at
user's request).

Delivered:
- schemas.py (Phase 4/5) - shared dataclasses: ScenarioIntent (LLM
  proposal, untrusted), ValidatedAST (post-ast_builder, KB-grounded),
  GeneratedScenario (final output, now also carries referenced_tables/
  referenced_columns so the Critic can check schema adherence without
  re-parsing SQL text).
- planning_agent.py (Phase 4) - LLM-backed: proposes scenario intents from
  a context slice + requirement. Robust JSON extraction (handles markdown
  fences and prose-wrapping).
- ast_builder.py (Phase 4) - deterministic hallucination-prevention gate:
  validates every proposed table/column/join against the actual Knowledge
  Base before anything downstream trusts it.
- generator_agent.py (Phase 4) - LLM-backed: writes human-readable
  scenario text, grounded in the validated AST only.
- pipeline.py (Phase 4/5) - orchestrates Planning -> AST Builder -> SQL
  Render -> Generator as plain sequential Python. Exposes
  `build_scenario_from_intent()` as a reusable single-intent helper,
  refactored out in Phase 5 specifically so reflection_loop.py's gap-filling
  step reuses the exact same logic instead of duplicating it.
- critic.py (Phase 5) - the Master System Prompt's 4-point Boolean
  checklist, implemented as fully DETERMINISTIC checks (not LLM-based) —
  see the module docstring for why that's a deliberate choice, not a
  scope cut. Reuses the Phase 3 hashing embedder for near-duplicate-title
  detection rather than reinventing similarity scoring.
- reflection_loop.py (Phase 5) - self-correction loop. Two distinct repair
  strategies depending on WHICH checklist item failed: coverage gaps get a
  targeted re-ask to the Planning Agent (with the specific missing rule
  spelled out in the prompt); mechanical defects (exact-duplicate SQL) get
  fixed deterministically with zero extra LLM calls. Bounded by
  max_iterations with an early-stop-on-no-progress guard.
- langgraph_pipeline.py (Phase 4, optional) - the Planning->AST->Generator
  slice wrapped as a 2-node LangGraph StateGraph. Import deferred so the
  module loads fine without langgraph installed. NOT executable in this
  sandbox (no network to install langgraph) — syntax-checked only. Not yet
  extended to include Critic/Reflection Loop nodes.
- llm_judge.py (Phase 10) - LLM-as-Judge evaluation (Completeness/
  Hallucination Prevention/Schema Adherence), deliberately complementary
  to (not a duplicate of) critic.py's deterministic checks — see its
  docstring for the explicit mapping and the reasoning for why this layer
  never gates anything. Runs via FastAPI BackgroundTasks, persisted by
  services/judge_service.py. A missing/failed evaluation is always `None`,
  never a fabricated zero score.

Every LLM call in planning_agent.py / generator_agent.py is injected as a
plain `Callable[[str], str]` rather than calling ollama_client.py directly
— this is what makes the whole pipeline (including reflection_loop.py)
unit-testable with a fake LLM, no live Ollama daemon required. See
docs/PHASES.md for what was actually run vs. syntax-checked in this
sandbox.
