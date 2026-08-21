"""
Generation endpoints — Phase 5 completes the core pipeline; Phase 10 adds
structured telemetry and a non-gating LLM-as-Judge evaluation layer:

  Gatekeeper gate (Phase 2)
    -> Fast-Path Router (bypasses everything below on match)
    -> Context Minimizer (schema-linking reduce layer)
    -> Semantic Cache (hit / partial_hit / miss)
    -> [MISS or PARTIAL_HIT] Planning Agent -> AST Builder -> SQL Renderer
       -> Generator Agent  (Phase 4)
    -> Critic -> Reflection Loop  (Phase 5 — self-correction against the
       4-point Boolean checklist, bounded retries)
    -> [if score >= MIN_CACHEABLE_QUALITY_SCORE] cache the result
    -> [background, after the response is sent] LLM-as-Judge (Phase 10) —
       never gates or delays anything above

On PARTIAL_HIT, the cached entry is handed to the Planning Agent as a
few-shot example (per the Master System Prompt's semantic cache design),
not returned directly.

Every stage emits structured telemetry (app.core.telemetry) — agent state
transitions, semantic cache FAISS-distance/BM25 decisions, and per-stage
latency — per the Master System Prompt's Structured System Telemetry
requirement.

If the configured LLM backend (Ollama) isn't reachable, this returns a
clear HTTP 503 with actionable detail rather than a raw connection-error
stack trace — verified for real against a genuinely-unreachable daemon
during development (see docs/PHASES.md).
"""

from typing import List, Optional
import json

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import require_role, CurrentUser
from app.core.telemetry import log_stage, log_cache_decision, PipelineTimer, get_logger

_logger = get_logger(__name__)
from app.db.session import get_db
from app.services.gatekeeper import require_gatekeeper_confirmation, GatekeeperBlockedError
from app.services.knowledge_base import get_current_file_hash
from app.services.context_minimizer import minimize_context
from app.services.fast_path_router import try_fast_path
from app.services.semantic_cache import check_cache, store_result
from app.infrastructure.llm.llm_provider import get_llm_call, LLMUnavailableError
from app.agents.pipeline import run_pipeline
from app.agents.reflection_loop import run_reflection_loop
from app.services.refinement import add_generated_rows
from app.services.judge_service import get_latest_evaluation
from app.core.prompt_injection import scan_for_injection
from app.models.audit import AuditLogEntry
from app.models.job import BackgroundJob

router = APIRouter(prefix="/api/generation", tags=["generation"])


class TestScenario(BaseModel):
    sl_no: int
    test_scenario: str
    detailed_test_steps: str
    expected_results: str
    verification_sql: str


class GenerationRequest(BaseModel):
    report_id: str
    natural_language_requirement: str


class GenerationResponse(BaseModel):
    session_id: int
    report_id: str
    scenarios: List[TestScenario]
    cache_status: str  # "fast_path" | "hit" | "partial_hit" | "miss"
    quality_score: float
    context_slice: Optional[dict] = None
    cache_explanation: Optional[str] = None
    pipeline_warnings: List[str] = []
    critic_report: Optional[dict] = None
    reflection_log: List[str] = []


@router.post("/run", response_model=GenerationResponse)
def run_generation(
    payload: GenerationRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    try:
        session = require_gatekeeper_confirmation(db, payload.report_id)
    except GatekeeperBlockedError as e:
        raise HTTPException(status_code=403, detail=str(e))

    requirement = payload.natural_language_requirement

    # --- Stage 0: Prompt-injection scan (Phase 9) ---------------------------
    # Direct user input is the highest-risk untrusted-text entry point (see
    # core/prompt_injection.py's docstring) — fail closed here, since
    # refusing is cheap and the user can simply rephrase. KB-derived text
    # (table/column descriptions, business rules) is lower-trust but not
    # user-facing in the same way, so that gets the lighter-touch
    # sanitize-and-continue treatment inside planning_agent.py instead.
    injection_scan = scan_for_injection(requirement)
    if injection_scan.is_suspicious:
        db.add(AuditLogEntry(
            user_id=current_user.username,
            session_id=int(session.id),
            event_type="PROMPT_INJECTION_BLOCKED",
            detail=json.dumps({
                "report_id": payload.report_id,
                "matched_patterns": injection_scan.matched_patterns,
            }),
        ))
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=(
                "This requirement text was blocked by prompt-injection "
                "screening (matched pattern(s): "
                f"{', '.join(injection_scan.matched_patterns)}). Please "
                "rephrase your requirement using plain business language."
            ),
        )

    # --- Stage 1: Fast-Path Router --------------------------------------
    with PipelineTimer("fast_path_router", report_id=payload.report_id):
        fast_path = try_fast_path(requirement)

    if fast_path is not None:
        log_stage("fast_path_router", report_id=payload.report_id, matched_rule=fast_path.matched_rule)
        scenario = TestScenario(
            sl_no=1,
            test_scenario=fast_path.test_scenario,
            detailed_test_steps=fast_path.detailed_test_steps,
            expected_results=fast_path.expected_results,
            verification_sql=fast_path.verification_sql,
        )
        add_generated_rows(
            db, session_id=int(str(session.id)), report_id=payload.report_id,
            requirement_text=requirement, scenarios=[scenario.model_dump()],
        )
        return GenerationResponse(
            session_id=int(str(session.id)),
            report_id=payload.report_id,
            scenarios=[scenario],
            cache_status="fast_path",
            quality_score=1.0,
            context_slice=None,
            cache_explanation=f"Matched fast-path rule '{fast_path.matched_rule}' — bypassed context minimizer and semantic cache.",
        )

    # --- Stage 2: Context Minimizer --------------------------------------
    with PipelineTimer("context_minimizer", report_id=payload.report_id):
        context_slice = minimize_context(db, payload.report_id, requirement)
    context_slice_dict = context_slice.to_dict()
    log_stage(
        "context_minimizer", report_id=payload.report_id,
        tables_selected=len(context_slice_dict.get("candidate_tables", [])),
    )

    # --- Stage 3: Semantic Cache -------------------------------------------
    file_hash = get_current_file_hash(db, payload.report_id)
    with PipelineTimer("semantic_cache", report_id=payload.report_id):
        cache_result = check_cache(
            db,
            report_id=payload.report_id,
            source_file_hash=file_hash or "",
            prompt_text=requirement,
        )
    log_cache_decision(
        payload.report_id,
        status=cache_result["status"],
        distance=cache_result.get("distance"),
        bm25_score=cache_result.get("bm25_score"),
        bm25_rescued=cache_result.get("bm25_rescued", False),
    )

    if cache_result["status"] == "hit":
        cached = cache_result["cached_entry"]
        scenarios = [TestScenario(**s) for s in cached["cached_payload"]]
        add_generated_rows(
            db, session_id=int(str(session.id)), report_id=payload.report_id,
            requirement_text=requirement, scenarios=[s.model_dump() for s in scenarios],
        )
        return GenerationResponse(
            session_id=int(str(session.id)),
            report_id=payload.report_id,
            scenarios=scenarios,
            cache_status="hit",
            quality_score=cached["quality_score"] or 0.0,
            context_slice=context_slice_dict,
            cache_explanation=cache_result["explanation"],
        )

    # --- Stage 4: Planning Agent -> AST Builder -> Generator (Phase 4) -------
    # partial_hit: the cached entry is injected as a few-shot example rather
    # than returned directly, per the Master System Prompt's cache design.
    few_shot = cache_result["cached_entry"] if cache_result["status"] == "partial_hit" else None

    try:
        with PipelineTimer("planning_ast_generator", report_id=payload.report_id) as pipeline_timer:
            generated, pipeline_warnings = run_pipeline(
                context_slice_dict,
                requirement,
                get_llm_call(),
                max_scenarios=settings.MAX_SCENARIOS_PER_REQUEST,
                few_shot_example=few_shot,
            )
        log_stage("planning_ast_generator", report_id=payload.report_id, scenarios_produced=len(generated))

        # --- Stage 5: Critic -> Reflection Loop (Phase 5) ---------------------
        with PipelineTimer("critic_reflection_loop", report_id=payload.report_id):
            reflection = run_reflection_loop(
                generated,
                context_slice_dict,
                requirement,
                get_llm_call(),
                max_iterations=settings.MAX_REFLECTION_ITERATIONS,
                max_scenarios=settings.MAX_SCENARIOS_PER_REQUEST,
            )
        log_stage(
            "critic_reflection_loop", report_id=payload.report_id,
            critic_score=reflection.critic_report.score,
            critic_passed=reflection.critic_report.passed,
            iterations_used=reflection.iterations_used,
        )
    except LLMUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"The local LLM backend is unavailable, so generation "
                f"cannot proceed: {e} Fast-path scenarios and cached "
                f"results still work without it."
            ),
        )

    final_scenarios = reflection.scenarios
    pipeline_warnings = pipeline_warnings + reflection.reflection_log

    scenarios = [
        TestScenario(
            sl_no=i + 1,
            test_scenario=s.test_scenario,
            detailed_test_steps=s.detailed_test_steps,
            expected_results=s.expected_results,
            verification_sql=s.verification_sql,
        )
        for i, s in enumerate(final_scenarios)
    ]

    if not scenarios:
        scenarios = [TestScenario(
            sl_no=1,
            test_scenario="[No scenarios generated]",
            detailed_test_steps="The Planning Agent's proposals could not be "
                                 "validated against the Knowledge Base for this "
                                 "report, even after the reflection loop — see "
                                 "pipeline_warnings for details.",
            expected_results="N/A",
            verification_sql="-- no verified query could be constructed",
        )]
    else:
        # Only push real, non-placeholder scenarios into the Refinement
        # Grid — a "[No scenarios generated]" row would just be clutter a
        # tester has to notice and delete manually.
        #
        # Deliberately uses final_scenarios (GeneratedScenario.to_dict()),
        # NOT the `scenarios` list built above — TestScenario has no
        # `category` field, so building from `scenarios` would silently
        # drop category info that add_generated_rows/RefinementRow actually
        # store and the grid displays. (Caught this exact mistake while
        # trying to "tidy up" this call site — see docs/PHASES.md Phase 6
        # notes.) add_generated_rows doesn't need sl_no, so the mismatch
        # with the other two call sites' input shape is harmless.
        add_generated_rows(
            db, session_id=int(str(session.id)), report_id=payload.report_id,
            requirement_text=requirement,
            scenarios=[s.to_dict() for s in final_scenarios],
        )

    # This is the first point in the pipeline where output is genuinely
    # "successfully compiled" in the sense the Master System Prompt's cache
    # design means. Gated on MIN_CACHEABLE_QUALITY_SCORE (default 0.75,
    # i.e. at least 3 of the Critic's 4 checklist items) rather than a
    # perfect critic_report.passed (which requires all 4) — a batch that's
    # 3-for-4 is still a genuinely useful result worth reusing, not a
    # stuck imperfect one. A batch below the threshold is returned to the
    # user (with pipeline_warnings explaining why) but never cached, so a
    # future similar request gets a fresh attempt instead of a permanently
    # stuck poor result.
    #
    # IMPORTANT: cache the TestScenario shape (sl_no + the 4 Excel-spec
    # fields), NOT GeneratedScenario.to_dict() — a future cache HIT
    # reconstructs scenarios via TestScenario(**s), which requires sl_no
    # and doesn't have (or want) GeneratedScenario's internal bookkeeping
    # fields like referenced_tables/ast_valid. Storing the wrong shape here
    # would make every future hit against this entry crash with a Pydantic
    # validation error instead of serving the cached result.
    if reflection.critic_report.score >= settings.MIN_CACHEABLE_QUALITY_SCORE and final_scenarios:
        store_result(
            db,
            report_id=payload.report_id,
            source_file_hash=file_hash or "",
            prompt_text=requirement,
            scenarios=[s.model_dump() for s in scenarios],
            quality_score=reflection.critic_report.score,
        )

    # --- Phase 10: LLM-as-Judge, scheduled AFTER the response is prepared ---
    # Non-gating, best-effort, and genuinely asynchronous in the practical
    # sense: it runs after this function returns and the user already has
    # their result, via FastAPI's BackgroundTasks. See llm_judge.py's
    # docstring for why this never influences quality_score/critic_report
    # above — it's a separate, complementary evaluation surfaced later via
    # GET /api/generation/{session_id}/judge-evaluation, not baked into
    # this response.
    if final_scenarios:
        from app.services.job_service import JobService
        from app.services.outbox_service import OutboxService
        from app.tasks.judge_task import execute_judge

        job_payload = json.dumps({
            "session_id": int(str(session.id)),
            "report_id": payload.report_id,
            "scenarios": [s.to_dict() for s in final_scenarios],
            "context_slice": context_slice_dict,
            "requirement": requirement,
        })
        
        # Transactional Outbox Pattern
        job = JobService.create_job(
            db=db,
            job_type="EVALUATE_JUDGE",
            requested_by=current_user.username,
            correlation_id=payload.report_id,
            idempotency_key=f"judge_{session.id}_{payload.report_id}",
            payload_reference=job_payload
        )
        
        outbox_event = OutboxService.create_event(
            db=db,
            event_type="CELERY_TASK_ENQUEUE",
            aggregate_type="BackgroundJob",
            aggregate_id=str(job.job_id),
            payload_reference=json.dumps({"task": "execute_judge", "job_id": str(job.job_id)})
        )
        
        db.commit()
        
        # Fire and forget. The outbox processor handles retries if this fails.
        try:
            execute_judge.delay(outbox_id=str(outbox_event.outbox_id), job_id=str(job.job_id))
        except Exception as e:
            _logger.error("redis_unavailable_during_enqueue", error=str(e))
            # Outbox ensures this isn't permanently lost


    return GenerationResponse(
        session_id=int(str(session.id)),
        report_id=payload.report_id,
        scenarios=scenarios,
        cache_status=cache_result["status"],
        quality_score=reflection.critic_report.score,
        context_slice=context_slice_dict,
        cache_explanation=cache_result["explanation"],
        pipeline_warnings=pipeline_warnings,
        critic_report=reflection.critic_report.to_dict(),
        reflection_log=reflection.reflection_log,
    )


@router.get("/{session_id}/judge-evaluation")
def get_judge_evaluation(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("tester")),
):
    """
    Best-effort: returns null fields (not a 404) if the background
    evaluation hasn't completed yet, was never scheduled (fast-path/cache
    hit skip it), or the LLM backend was unavailable when it ran — see
    llm_judge.py's docstring for why "no data" must never be confused with
    "scored zero."
    """
    record = get_latest_evaluation(db, session_id)
    if record is None:
        return {
            "session_id": session_id,
            "available": False,
            "completeness": None,
            "hallucination_prevention": None,
            "schema_adherence": None,
            "overall": None,
            "rationale": None,
            "warnings": [],
        }

    return {
        "session_id": session_id,
        "available": True,
        "completeness": record.completeness,
        "hallucination_prevention": record.hallucination_prevention,
        "schema_adherence": record.schema_adherence,
        "overall": record.overall,
        "rationale": record.rationale,
        "warnings": json.loads(record.warnings) if record.warnings else [],
    }
