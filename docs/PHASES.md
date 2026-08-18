# Phase Tracker

| Phase | Scope | Status |
|---|---|---|
| 0 | Repo scaffold (backend/frontend skeleton, DB schema, config) | ✅ Delivered |
| 1 | Document ingestion: upload, RDD/LDM parsing, Knowledge Base storage | ✅ Delivered |
| 2 | Gatekeeper UI: upload flow + CR ID/Description confirmation card | ✅ Delivered |
| 3 | Context Minimizer (schema-linking) + FAISS/BM25 hybrid semantic cache | ✅ Delivered |
| 4 | Planning Agent + AST Builder + Generator (LangGraph/CrewAI + Ollama) | ✅ Delivered |
| 5 | Critic/Reflection loop + Compile-then-Execute SQL compiler | ✅ Delivered |
| 6 | Interactive Refinement Grid (HITL) UI | ✅ Delivered |
| 7 | Excel Compiler (openpyxl/pandas, 5-column spec) | ✅ Delivered |
| 8 | SharePoint sync + Email distribution | ✅ Delivered |
| 9 | RBAC, immutable audit logging, encryption, prompt-injection defenses | ✅ Delivered |
| 10 | LLM-as-judge eval pipeline, structlog telemetry, integration tests, docs | ✅ Delivered |

## Phase 1 delivery notes

What's included:
- `app/services/document_parser.py` — parses .xlsx/.csv/.docx/.pdf into
  structured records (tables, columns, joins, valid values, business rules).
  Classification is mutually exclusive per sheet/table to avoid
  double-counting. Free-form prose is NEVER auto-classified as a business
  rule — it's captured separately as an `UnstructuredNote` for human review.
- `app/services/knowledge_base.py` — persists parsed records, computes
  SHA-256 file hashes, and implements the cache-busting rule (a new file for
  an existing report_id with a different hash invalidates prior KB rows).
- `app/models/knowledge_base.py` — SQLAlchemy models for the KB tables.
- `app/api/ingestion.py` — real `/upload` (multipart, requires report_id)
  and `/knowledge-base/{report_id}` endpoints replacing the Phase 0 stubs.
- Frontend `IngestionPage.jsx` — collects Report ID / CR ID, uploads, and
  displays extraction counts, warnings, and cache-invalidation notices.
- `tests/test_document_parser.py` and `tests/test_knowledge_base.py` —
  pytest suites. **I ran the document_parser assertions manually against
  real fixture files in this sandbox (pandas/openpyxl/python-docx/
  pdfplumber were available) and all 8 passed.** `fastapi`, `sqlalchemy`,
  and `pytest` themselves are NOT installed in this sandbox (no network
  access), so the KB persistence tests and the live API are syntax-checked
  only — please run `pytest` locally to confirm those pass too.

## Phase 2 delivery notes

What's included:
- `app/services/gatekeeper.py` — the real "strict blocking step":
  - `get_scope_summary` — pulls real KB extraction counts + prior CR ID/
    confirmation state for a report_id, for the UI to render.
  - `confirm_scope` — requires non-empty CR ID and CR Description, and
    requires the Knowledge Base to actually have structured content
    (refuses with the mandated "Insufficient metadata available..."
    message otherwise). Creates a `Session` row and an audit log entry.
  - `require_gatekeeper_confirmation` — **the actual gate.** Raises
    `GatekeeperBlockedError` unless a confirmed session exists for the
    report_id. This is now wired into `/api/generation/run` (still a
    stub for the generation logic itself, but the gate is real and
    returns HTTP 403 if scope hasn't been confirmed).
  - Closing the loop with Phase 1: `knowledge_base.invalidate_existing_kb`
    now also downgrades any `gatekeeper_confirmed` session back to
    `ingestion` status when a re-uploaded file changes the KB — so a
    stale confirmation can never silently authorize generation against
    metadata that no longer matches what was confirmed.
- `app/api/gatekeeper.py` — `GET /api/gatekeeper/scope/{report_id}` and
  `POST /api/gatekeeper/confirm`, replacing the Phase 0 stubs.
- Frontend: `WorkflowContext.jsx` (shares Report ID / CR ID across the
  wizard steps), updated `IngestionPage.jsx` (links to Gatekeeper once
  parsed), and a fully live `GatekeeperPage.jsx` — real scope summary,
  editable CR ID/Description, confirm button disabled until KB has
  content, confirmed-state view with a link to Step 3.
- `tests/test_gatekeeper.py` — 6 pytest cases covering scope summary
  accuracy, refusal without structured KB, refusal without CR
  Description, blocked-before-confirmation, allowed-after-confirmation,
  and the re-upload-downgrades-confirmation loop-closing case.

**Testing honesty check:** `sqlalchemy`, `fastapi`, and `pytest` are still
not installed in this sandbox (no network access), so
`test_gatekeeper.py` and `test_knowledge_base.py` are syntax-checked only,
not executed here. I traced the re-upload/downgrade test case by hand
against the actual `invalidate_existing_kb` implementation line-by-line
to confirm the logic holds, but please run `pytest` locally to get a real
pass/fail signal — that's the one test in this phase I'd most want
confirmed since it spans two services (knowledge_base + gatekeeper).
JSX files (`WorkflowContext.jsx`, `GatekeeperPage.jsx`, etc.) were
reviewed manually rather than transpiler-checked, since no JS bundler
could be installed offline either — run `npm run dev` locally to confirm
they render.

## Phase 3 delivery notes

What's included — the real pre-generation pipeline, wired into
`/api/generation/run` after the Phase 2 gate:

  Gatekeeper gate → **Fast-Path Router** → **Context Minimizer** →
  **Semantic Cache** → [Phase 4/5: Planning Agent — still a placeholder]

- `app/services/embeddings.py` — `HashingEmbedder`: a dependency-free,
  deterministic SHA-256 feature-hashing bag-of-words embedder. No model
  download, no network, no Ollama dependency required just to run the
  cache. Swapping in a real Ollama embedding model later is a drop-in
  change (same `.embed()` interface) — documented in the module itself.
- `app/services/bm25.py` — hand-rolled BM25-Okapi scorer (zero extra
  PyPI dependency for something this well-defined).
- `app/services/vector_index.py` — `NumpyFlatL2Index` (always available)
  with `FaissFlatL2Index` preferred automatically when `faiss-cpu` is
  installed — same interface, transparent fallback. Brute-force L2 is a
  deliberate, documented choice: lookups are always scoped to one
  `report_id` first via SQL, so candidate sets are small in practice.
- `app/services/cache_classification.py` — the pure hit/partial_hit/miss
  decision function (FAISS L2 thresholds from the Master System Prompt,
  0.15 / 0.30) **plus a clearly-labeled original extension**: a BM25
  hybrid "rescue" that upgrades a Miss to a Partial Hit when keyword
  overlap is very strong but the coarse hashing embedder placed it just
  outside the L2 thresholds. This is called out in the code as an
  addition beyond the base spec, not presented as if it were always there.
- `app/services/context_minimizer.py` — real schema-linking: direct
  keyword matches (table/column names, valid-value *meanings* like "card
  issued", business-rule text) plus **one-hop join expansion** (not
  transitive closure — deliberately, to keep the reduction meaningful).
  Hallucination-prevention posture: if nothing matches, it fails OPEN to
  the full Knowledge Base with a warning rather than guessing a subset.
- `app/services/semantic_cache.py` — ties the above together against the
  new `SemanticCacheEntry` model (`app/models/cache.py`, replacing the
  Phase 0 `CacheMetadata` stub that nothing used). Cache lookups are
  scoped to `(report_id, source_file_hash)`, so a re-uploaded/changed file
  naturally stops matching old entries even before physical deletion.
  `invalidate_cache_for_report` is now wired into the ingestion endpoint,
  closing the cache-busting loop promised in Phase 1's docstring.
- `app/services/fast_path_router.py` — a real (if intentionally small)
  rules engine: 3 regex-matched patterns (date/timestamp formatting,
  pagination, layout/header checks) that return genuine boilerplate test
  scenarios instantly, bypassing the Context Minimizer and Semantic Cache
  entirely. This produces real, non-stub output today for standard
  patterns, ahead of the Phase 4/5 LLM pipeline.

**A real bug found and fixed while verifying this phase:** the original
tokenizer treated underscores as part of a token, so a SNAKE_CASE column
name like `SWIPE_CARD_IND` tokenized to a single indivisible token and
would never lexically match natural-language phrasing like "swipe card
indicator" — silently defeating BM25 scoring and context-minimizer
keyword matching for exactly the realistic case this system exists to
handle (this is literally the example column name used in the Master
System Prompt's own Excel Scenario Output Specification). Fixed by
splitting tokens on underscore; verified with a regression test
(`test_bm25.py::test_underscored_query_matches_prose_document`) and a
dedicated tokenizer test.

**Testing honesty check:** unlike Phases 1/2, most of Phase 3's logic is
genuinely DB-independent by design (embeddings, BM25, vector index,
classification, and the core context-minimizer matching function all take
plain data, not ORM objects) — so I ran all of it for real in this sandbox
(numpy and scikit-learn are installed here; sqlalchemy/fastapi/pytest are
not). **32 test functions across 6 test files were actually executed and
passed**, including the realistic swipe-card-indicator scenario from the
spec's own example. `test_semantic_cache.py` (the persistence/integration
layer, which needs sqlalchemy) is syntax-checked only, but I independently
verified its two riskiest assumptions — that an identical prompt hits and
a genuinely unrelated prompt misses — by running the real embedder +
vector index + classifier together outside the DB layer, with the actual
configured `EMBEDDING_DIM=256`. `generation.py`'s end-to-end wiring
(gate → fast-path → minimizer → cache) was traced by hand rather than
executed. Please run `pytest` locally to confirm `test_semantic_cache.py`
and get full coverage confirmation.

## Phase 4 delivery notes

What's included — the real Planning Agent -> AST Builder -> Generator
pipeline, replacing the placeholder scenario on cache MISS/PARTIAL_HIT in
`/api/generation/run`:

  Semantic Cache (miss/partial_hit) → **Planning Agent** (LLM) →
  **[per proposed scenario] AST Builder** (deterministic) → **SQL Renderer**
  (deterministic) → **Generator Agent** (LLM) → assembled scenario

- `app/agents/schemas.py` — shared dataclasses (`ScenarioIntent`,
  `ValidatedAST`, `GeneratedScenario`) so ast_builder.py doesn't need to
  import planning_agent.py just to reference its output type.
- `app/agents/planning_agent.py` — asks the LLM to propose scenario
  intents from the minimized context + requirement. Robust JSON
  extraction handles markdown-fenced and prose-wrapped responses (both
  very common real LLM behaviors) rather than requiring perfect
  compliance. On PARTIAL_HIT, the cached entry is injected as a few-shot
  example per the Master System Prompt's semantic cache design — this
  wires up something Phase 3 had described but nothing consumed yet.
- `app/agents/ast_builder.py` — **the core hallucination-prevention gate**
  for this phase: validates every LLM-proposed table/column/join against
  the actual Knowledge Base (case-insensitive name normalization is
  allowed; anything beyond that is rejected outright, with explicit
  reasons). A documented, real scope limit: `target_columns`/`filters`
  only validate against the primary `target_table`, not joined tables —
  called out as a concrete Phase 5 refinement, not hidden.
- `app/services/sql_render.py` — deterministic AST → ANSI SQL renderer,
  zero LLM involvement, written to be reused as-is by Phase 5's SQL
  Compiler pipeline stage rather than duplicated later.
- `app/agents/generator_agent.py` — LLM-backed scenario prose (title/
  steps/expected results), grounded in the validated AST only.
  `verification_sql` is never LLM output — always `sql_render.render_sql()`
  on the validated AST.
- `app/agents/pipeline.py` — orchestrates the above as plain sequential
  Python (see below for why, not LangGraph/CrewAI). A scenario that fails
  AST validation is dropped with a warning and **never reaches the
  Generator Agent** — structurally enforced, not just convention.
- `app/agents/langgraph_pipeline.py` — the same pipeline wrapped as a
  2-node LangGraph `StateGraph`, to satisfy the stack's agentic-framework
  requirement. Import deferred so the module loads without langgraph
  installed. **Not run in this sandbox** (no network to install
  langgraph) — syntax-checked only. If you run this with langgraph
  installed, please verify it produces identical output to
  `pipeline.run_pipeline()` before relying on it.
- `app/services/ollama_client.py` — the real local-inference LLM backend
  (Technology Policy A: local, free, no paid APIs). Raises a clean
  `OllamaUnavailableError` rather than a raw connection stack trace;
  `generation.py` catches this and returns HTTP 503 with actionable
  detail instead of a 500.

**Why plain Python instead of LangGraph/CrewAI for the actual wiring:**
this sandbox has no network access to install either framework, so
routing the real pipeline through one would mean shipping entirely
untested orchestration code. Instead, `pipeline.py` is plain, composable
functions (independently tested), with `langgraph_pipeline.py` as an
optional wrapper around the *exact same* functions for teams that want
LangGraph's tracing/checkpointing. This is a disclosed tradeoff, not a
silent scope cut.

**Testing honesty check:** Phase 4's LLM-calling functions are all built
around `Callable[[str], str]` dependency injection specifically so they're
testable without a live LLM. **28 test functions across 5 files were
actually executed and passed** in this sandbox, including:
- the critical hallucination-prevention path: a batch with one valid and
  one hallucinated scenario proposal, confirming the hallucinated one is
  dropped *before* it ever reaches the Generator Agent (verified via call
  counting — exactly 2 LLM calls, not 3);
- realistic messy-LLM-output handling (markdown-fenced JSON, prose-wrapped
  JSON, malformed individual items in an otherwise-valid batch).

`ollama_client.py`'s connection-failure handling was verified against a
**genuinely unreachable** local daemon (there is no Ollama running in this
sandbox) — this is a real integration test of the failure path, not a
mock. `test_ollama_client.py` as committed uses `pytest`'s `monkeypatch`
(needs `pytest` + `pydantic-settings` installed, which this sandbox
doesn't have); I verified the equivalent behavior manually here by
stubbing `app.core.config` directly. `generation.py`'s end-to-end HTTP
wiring (503 handling, few-shot injection on partial_hit, sl_no assignment)
was traced by hand rather than executed — please run `pytest` and a real
`uvicorn` server locally (with or without Ollama running) to confirm both
the success and the 503-on-unavailable paths.

## Phase 5 delivery notes

What's included — the Critic + Reflection Loop, completing the Compile-
then-Execute pipeline and finally closing a promise made back in Phase 3:

  Generator output (Phase 4) → **Critic** (4-point Boolean checklist) →
  if any item fails → **Reflection Loop** (bounded self-correction) →
  final scenarios → **cache, but only if the Critic actually passed**

- `app/agents/critic.py` — implements the Master System Prompt's 4-point
  checklist verbatim (business rules covered / SQL uses only verified
  columns / no duplicate scenarios / edge cases covered). **Deliberately
  fully deterministic, not LLM-based** — the module docstring explains why:
  every one of these four items is something a rule-based check can answer
  more reliably and auditably than an LLM grading its own (or a sibling
  agent's) output, which matters in a HIPAA-adjacent context. Reuses the
  Phase 3 hashing embedder for near-duplicate-title detection and reuses
  `GeneratedScenario.referenced_tables/referenced_columns` (added to
  `schemas.py` this phase) rather than re-parsing SQL text back into
  structure — parsing SQL to re-derive what it references is exactly the
  fragile pattern this architecture avoids elsewhere.
- `app/agents/reflection_loop.py` — bounded self-correction with two
  distinct repair strategies depending on *which* checklist item failed:
  coverage gaps get a targeted re-ask to the Planning Agent with the
  specific missing business rule spelled out in the prompt (not a vague
  "try again"); exact-duplicate SQL gets deterministically deduplicated
  with **zero additional LLM calls**. An unfixable failure (`sql_schema_valid`
  — which should be structurally impossible per Phase 4's guarantees) is
  treated as a hard stop, not an infinite retry. An early-stop-on-no-
  progress guard prevents burning iterations repeating an identical failed
  attempt.
- `app/agents/pipeline.py` — refactored to extract
  `build_scenario_from_intent()` as a reusable helper, so the reflection
  loop's gap-filling step runs through the *exact same* AST-Builder→SQL-
  Render→Generator sequence as the main pipeline rather than a
  hand-duplicated copy that could drift out of sync.
- `app/api/generation.py` — wires Critic + Reflection Loop in after
  Generator output, and **only now calls `semantic_cache.store_result()`**
  — the thing Phase 3/4 explicitly deferred ("Real Phase 4/5 output (post
  Critic/Reflection Loop) is the first thing genuinely worth caching").
  `quality_score` in the API response is now the real Critic score, not a
  placeholder. **A real bug was caught and fixed while wiring this up:**
  the original draft cached `GeneratedScenario.to_dict()`, which has no
  `sl_no` field and carries internal bookkeeping fields (`ast_valid`,
  `referenced_tables`, etc.) that don't belong in the cache. Since cache
  hits reconstruct scenarios via `TestScenario(**s)` — which *requires*
  `sl_no` — every future hit against such an entry would have crashed with
  a Pydantic validation error instead of serving the cached result. Fixed
  to cache the already-built `TestScenario` shape instead.

**Testing honesty check:** this phase's logic is almost entirely
DB-independent by design (same reasoning as Phase 3/4), so I ran it for
real. **11 new test functions across 2 files, plus the full existing
79-test DB-independent regression suite, all passed** in this sandbox
after the `pipeline.py` refactor and `schemas.py` extension — nothing
broke. Notable things actually verified, not just asserted:
- the reflection loop closing a genuine two-rule coverage gap in exactly 1
  iteration, confirmed via a fake LLM that legitimately can't satisfy the
  critic until the gap-fill call happens;
- exact-duplicate dedup requiring **zero** LLM calls (enforced via a fake
  LLM that raises `AssertionError` if invoked at all);
- an unrecoverable gap (LLM keeps proposing a hallucinated column)
  terminating within `max_iterations` rather than looping forever;
- one dead-end during development where my own test fixture (not the
  reflection loop) was buggy — a fake LLM returning identical generator
  text for two different scenarios triggered the critic's near-duplicate-
  title check correctly, which looked like a failure until I traced it
  back to the test, not the code.

`generation.py`'s end-to-end HTTP wiring (the new `store_result()` call,
`critic_report`/`reflection_log` fields in the response) was traced by
hand rather than executed, consistent with every prior phase's API-layer
caveat — please run `pytest` and a real server locally to confirm.

## Phase 6 delivery notes

What's included — the Interactive Refinement Grid (Step 3), the first
phase that's primarily frontend, backed by real audit-logged persistence:

- `app/models/refinement.py` — `RefinementRow`: one row per scenario in a
  session's grid, with a frozen `original_snapshot_json` captured at
  creation time. Every subsequent edit diffs against the row's *current*
  value (so a second edit's "old value" is the first edit's result, not
  the AI original) while `original_ai_value` in the audit log always
  refers back to the frozen snapshot — this is what lets the audit trail
  distinguish "still matches the AI original" from "already edited once,
  edited again."
- `app/services/refinement.py` — grid CRUD (`add_generated_rows`,
  `add_manual_row`, `get_grid`, `update_row`, `delete_row`). Every edit or
  removal writes an `AuditLogEntry` (`HUMAN_OVERRIDE`,
  `MANUAL_SCENARIO_ADDED`, `SCENARIO_REMOVED`) — one entry per *changed
  field*, not a vague "row was edited," per the Master System Prompt's
  audit requirement. Manually-authored rows deliberately skip AST
  validation: a human typing their own scenario is directly accountable
  for it, the same as if they'd written it with no tool at all.
- `app/api/refinement.py` — `GET/{session_id}`, `POST/{session_id}/rows`,
  `PATCH/{session_id}/rows/{row_id}`, `DELETE/{session_id}/rows/{row_id}`.
- `app/api/generation.py` — every successful generation path (fast-path,
  cache hit, and the full pipeline) now also appends its scenarios into
  the session's grid via `add_generated_rows`, so Step 3 actually
  accumulates real output across however many requirements a tester runs
  in one session, rather than being disconnected from Steps 1/2/4.
- **A small but real gap closed along the way:** `GatekeeperConfirmResponse`
  already returned `session_id`, but `ScopeSummaryResponse` (used to
  restore state on page reload) didn't — so refreshing the browser after
  confirming would have shown "confirmed" with no way to reach the grid.
  Added `session_id` to the scope summary too.
- Frontend: `WorkflowContext` now tracks `sessionId` (set on confirm and
  recovered from the scope summary on reload). `RefinementPage.jsx` ties
  together a requirement input (calls `/api/generation/run` and shows
  cache status / critic pass/fail / pipeline warnings), a live editable
  grid (`RefinementGridRow.jsx` — per-field textareas, dirty-tracking save
  button, delete with confirmation, source badges for AI/Edited/Manual),
  and `AddManualRowForm.jsx` for tester-authored scenarios.

**Testing honesty check:** `refinement.py`'s logic is entirely
DB-dependent (every operation reads/writes `RefinementRow`/
`AuditLogEntry`), so — consistent with `test_knowledge_base.py`/
`test_gatekeeper.py`/`test_semantic_cache.py` in earlier phases —
`test_refinement.py` is syntax-checked only in this sandbox, not executed
(no `sqlalchemy` here). I hand-traced the two riskiest cases line-by-line
against the actual implementation before committing them: (1) editing a
row twice, confirming the second edit's audit log shows `old_value` as the
*first* edit's result while `original_ai_value` still points at the
untouched original snapshot; (2) editing a field back to its original
value logging nothing at all (no-op edits shouldn't pollute the audit
trail). The full 79-test DB-independent regression suite from Phases 3-5
was re-run after these changes and stayed green — nothing broke.

**One more catch from this session's review pass:** while auditing
`generation.py`'s three `add_generated_rows()` call sites for consistency,
I initially "tidied up" the full-pipeline call site to pass the same
`TestScenario`-shaped dicts as the other two call sites. That would have
been a real regression — `TestScenario` has no `category` field, so it
would have silently dropped category info (`valid_value_check`,
`null_check`, etc.) that `GeneratedScenario.to_dict()` correctly carries
and that `RefinementRow`/the grid actually store and display. Caught it by
checking the Pydantic model's fields before trusting the "cleanup," and
reverted to the original (correct) code with a comment explaining why the
three call sites intentionally use different input shapes.

JSX files (`RefinementGridRow.jsx`, `AddManualRowForm.jsx`,
`RefinementPage.jsx`, plus the modified `WorkflowContext.jsx` and
`GatekeeperPage.jsx`) were checked for balanced brackets/braces/parens
programmatically and reviewed by hand — no bundler was available offline
to actually transpile them. One real thing caught this way: I'd used
`UserPen` as a lucide-react icon name, which may not exist in the pinned
package version, and swapped it for the long-established `User` icon
before it could break the build. Please run `npm run dev` locally to
confirm the grid renders and behaves as described — this is the first
phase where a broken frontend build would be silent to me but very much
not silent to you.

## Phase 7 delivery notes

What's included — the Excel Compiler, turning a session's finalized
Refinement Grid into the downloadable .xlsx artifact:

- `app/services/excel_compiler.py` — `build_workbook()` is a pure
  function (rows/metadata in, openpyxl `Workbook` out, zero DB/filesystem
  access), producing the spec's exact 5 required columns (SL#, Test
  Scenario, Detailed Test Steps, Expected Results, Verification SQL) plus
  a disclosed, justified 6th "Source" column (AI Generated / AI + Edited /
  Manual) serving the Explainability requirement. A separate "Cover" sheet
  carries Report ID / CR ID / CR Description / generation timestamp / a
  source-document traceability table (filename + SHA-256 + upload time),
  reusing the same integrity-hash pattern from Phase 1/3.
- `app/services/export_service.py` — wires the pure compiler to real
  session/grid/source-document data, disk persistence under
  `EXPORT_DIR`, SHA-256 hashing of the generated file, and an `EXPORT`
  audit log entry. Kept as a separate module specifically so
  `excel_compiler.py` stays testable without sqlalchemy.
- `app/models/export.py` — `ExportRecord`, tracking every generated
  workbook so `GET /api/export/{session_id}/download` can serve "the
  latest export" without scanning the filesystem, and so Phase 8's
  SharePoint sync has a natural column to add to (`sharepoint_url`)
  rather than a new table.
- `app/api/export.py` — real `POST /api/export/finalize` and
  `GET /api/export/{session_id}/download` (streams the file via
  `FileResponse`), replacing the Phase 0 stub.
- **Frontend gap closed this session:** the backend above was already
  fully built and wired (including `api.js`'s `finalizeExport`/
  `getExportDownloadUrl`) when I checked, but `ExportPage.jsx` itself was
  still the Phase 0 placeholder — three static "not yet implemented"
  cards with no logic. Built the real page: fetches the session's grid on
  load, shows a live scenario count, a "Generate Excel workbook" button
  wired to `finalizeExport`, and a real download link/button once export
  succeeds. SharePoint/Email cards remain visually present but dimmed and
  explicitly labeled Phase 8, rather than removed, so the 4-card layout
  stays stable across phases.

**Testing honesty check:** `excel_compiler.py` is DB-free by design, so I
ran its test suite for real — **9 test functions, all passing**, including
a genuine save-to-disk-and-reload round-trip through `openpyxl` (not just
in-memory `Workbook` object inspection) to confirm the output is actually
a valid, re-openable .xlsx file. `export_service.py`'s tests need
sqlalchemy (unavailable here) so `test_export_service.py` is syntax-
checked only, consistent with every other DB-dependent service in this
project; I did read it against the actual `export_service.py`
implementation line-by-line and the fixtures correctly use
`monkeypatch`+`tmp_path` to redirect `EXPORT_DIR` rather than writing to a
real path. The full 88-test DB-independent regression suite (Phases 3-7)
was re-run after the frontend changes and stayed green. `ExportPage.jsx`
was checked for balanced brackets/braces/parens programmatically (all
zero) and reviewed by hand — please run `npm run dev` to confirm it
actually renders and the download works end-to-end, same caveat as
Phase 6.

## Phase 8 delivery notes

What's included — SharePoint sync and email distribution, layered onto
the already-successful Excel export from Phase 7 with **partial-success
semantics**: a SharePoint or SMTP failure never makes an otherwise-fine
export look failed, and each outcome gets its own distinct audit event
(`SHAREPOINT_SYNC`/`SHAREPOINT_SYNC_FAILED`, `EMAIL_SENT`/`EMAIL_FAILED`).

- `app/services/sharepoint_client.py` — uploads to a SharePoint document
  library via the standard Microsoft Graph app-only (client credentials)
  OAuth flow: resolve site → resolve default drive → PUT the file content
  (small-file endpoint; correctly noted as insufficient for >4MB, which
  this app's spreadsheet exports will never hit). Every failure mode —
  missing credentials, unreachable host, a bad site URL, a non-2xx Graph
  response — raises one exception type (`SharePointSyncError`) with an
  actionable message, mirroring `ollama_client.py`'s pattern from Phase 4.
- `app/services/email_service.py` — HTML email via stdlib `smtplib`/
  `email`, zero extra dependency, so no mail server API key is ever
  required. `build_export_email()` is a pure function; notably, it
  renders "N/A" rather than fabricating a quality score when the caller
  doesn't have one for this session (a session's grid can span multiple
  generations with different Critic scores, plus manually-added rows with
  no score at all — the docstring explains why no single honest
  aggregate exists to compute server-side).
- `app/models/export.py` — extended (not replaced) with `sharepoint_url`
  and `email_sent_to`, exactly as Phase 7's docstring had already
  earmarked, rather than inventing a new table.
- `app/api/export.py` — `POST /api/export/finalize` now accepts
  `sync_to_sharepoint`/`email_distribution_list`/`quality_score` and
  performs Excel generation → best-effort SharePoint sync → best-effort
  email, all in one call, with per-step success/failure surfaced
  separately in the response.

**What's genuinely testable here vs. not, and why:** neither a real
Microsoft 365 tenant nor a real SMTP server is reachable from this
sandbox — that was expected going into this phase (flagged back at the
Phase 0 feasibility estimate as the phase most likely to need your live
credentials). What I could and did verify for real:
- **16 new tests, all executed and passing** (7 SharePoint + 9 email).
- Pure logic: SharePoint upload URL construction; HTML email subject/body
  rendering including the N/A-not-fabricated and "Not synced" cases.
- **Real connection-failure handling** against genuinely unreachable
  addresses — `http://localhost:1` for Graph, `localhost:1` for SMTP —
  the same technique proven out for `ollama_client.py` in Phase 4.
- **Real "not configured" refusals** — SharePoint/SMTP credentials are
  genuinely empty in this sandbox's `.env`, so testing "refuses cleanly
  with no credentials configured" isn't a simulation here, it's the actual
  current state.

What I could NOT verify and want to be direct about: a real Graph API
token acquisition, a real file actually landing in a SharePoint library, a
real authenticated SMTP send, and `msal`'s actual behavior (not installed,
no network to install it — the import is deferred so the module still
loads without it). **Please test this phase against your actual tenant
and mail server before trusting it in production** — this is the one
phase in the whole build where "the code is well-structured and the
failure paths are proven" is meaningfully weaker evidence than usual,
because the happy path itself is entirely unverified.

## Phase 10 delivery notes

**Note on sequencing:** at the user's request, this phase was built before
Phase 9 (RBAC, immutable audit enforcement, encryption, prompt-injection
defenses) — which has since been delivered too (see the Phase 9 section
below). Nothing in Phase 10 depended on Phase 9, so building it out of
order was safe; Phase 9's endpoints now require authentication, which is
layered on top of everything Phase 10 built without changing any of its
internal logic.

What's included:

- `app/core/telemetry.py` — structured JSON telemetry per the Master
  System Prompt's requirement (agent state transitions, FAISS-distance/
  BM25 cache-decision scores, per-stage pipeline latency). Same
  prefer-the-named-dependency-fall-back-to-equivalent pattern already
  established for FAISS (Phase 3) and LangGraph (Phase 4): `structlog`
  isn't installed in this sandbox, so a dependency-free stdlib-`logging`
  equivalent is what's actually exercised here, with an identical JSON
  shape either way. **A real bug was caught and fixed while building
  this, and the module's own docstring says so:** the fallback logger's
  name wasn't namespaced consistently, so stdlib logging's dotted-name
  propagation meant log lines silently never reached the configured
  handler — caught immediately by testing right after writing it, not
  left for later discovery.
- `app/agents/llm_judge.py` + `app/services/judge_service.py` +
  `app/models/evaluation.py` — the LLM-as-Judge evaluation pipeline,
  scoring Completeness / Hallucination Prevention / Schema Adherence per
  the spec. **Deliberately positioned as complementary to, not a
  duplicate of, Phase 5's Critic** — the docstring maps each of the
  three LLM-judge dimensions to the deterministic check that already
  covers it, and explains why this layer never gates generation or
  export: an LLM grading its own sibling agent's output should not be
  able to override a deterministic, auditable decision. Runs via FastAPI
  `BackgroundTasks` — genuinely non-blocking, not just labeled
  "asynchronous." A `None` result (empty batch, parse failure, or LLM
  unavailable) is carefully distinguished from a zero score everywhere,
  including in the API response shape, so a dashboard consuming this can
  never mistake "no data yet" for "scored badly."
- `app/api/generation.py` — instrumented end-to-end with telemetry calls
  and the background judge task; also introduces
  `MIN_CACHEABLE_QUALITY_SCORE` (default 0.75) as a disclosed refinement
  to Phase 5's caching gate — a batch scoring 3-of-4 on the Critic
  checklist is now cached as a genuinely useful result rather than
  requiring a perfect pass, with the reasoning stated inline in the code.
  New `GET /api/generation/{session_id}/judge-evaluation` endpoint.
- **Frontend gap closed this session:** the backend above was fully built
  when I checked, but nothing in the frontend called the new judge-
  evaluation endpoint. Added `getJudgeEvaluation()` to `api.js` and a
  polling+display card to `RefinementPage.jsx` (polls briefly after a
  full-pipeline generation call, gives up quietly if the background task
  never completes — consistent with the "supplementary, never blocking"
  design). Used an icon already proven to exist elsewhere in this
  codebase (`Sparkles`) rather than an unverified new lucide-react name.
- Wrote the two missing test files: `test_judge_service.py` and (earlier
  in this audit) confirmed `test_llm_judge.py` and `test_telemetry.py`
  were already present and correct.

**Testing honesty check:** telemetry and LLM-judge logic are both
DB-independent by design (same reasoning as Phases 3-5), so I ran them for
real. **11 test functions across `test_llm_judge.py` and
`test_telemetry.py`, all executed and passing** — including genuinely
capturing real JSON log output via a `StringIO` handler attached to the
actual logger (not just checking functions ran without raising), and
confirming the `None`-not-zero semantics for every LLM-judge failure mode
(empty batch, backend failure, malformed response). `test_judge_service.py`
(new, written this session) covers `get_latest_evaluation()` for real
against an in-memory DB, but **honestly documents a real gap**:
`evaluate_and_store()` itself isn't tested, because it deliberately opens
its own `SessionLocal()` rather than accepting an injectable session
(correct design for a `BackgroundTasks` callback, but awkward to point at
a test DB) — flagged as a concrete refactoring opportunity rather than
silently skipped. `generation.py`'s new instrumentation and the
`judge-evaluation` endpoint were traced by hand, not executed. Frontend
polling logic was checked for balanced syntax programmatically; please
run `npm run dev` and generate a scenario via the full pipeline (not
fast-path) to confirm the async review card actually appears after a few
seconds.

## Phase 9 delivery notes

Built after Phase 10 at the user's explicit request. This phase involved
the most substantial gap-closing of any phase so far: the security
*infrastructure* (auth, RBAC, encryption, immutable audit, prompt-
injection defenses, malware scanning) was already fully built and
individually solid when I checked, but **none of it was actually wired
into the real API endpoints** — every workflow action (upload, confirm
scope, generate, refine, export) was still completely unauthenticated,
and every "who did this" field (`uploaded_by`, `confirmed_by`,
`exported_by`, `added_by`, `edited_by`, `removed_by`) was still
client-supplied free text with zero verification behind it. That gap
would have made the entire audit trail this project has built since
Phase 1 fundamentally spoofable — the most important thing to fix in this
phase, and where most of this session's actual work went.

**What was already correctly built (audited, not rewritten):**
- `core/security.py` — PBKDF2-HMAC-SHA256 password hashing (stdlib,
  NIST-approved, zero new dependency) + JWT via `pyjwt`.
- `core/rbac.py` — three roles (tester/approver/admin), hierarchical, with
  a genuinely important detail: role comes from the DB at request time,
  not the token's claim, so a mid-session demotion takes effect
  immediately rather than waiting for token expiry.
- `core/encryption.py` — real AES-256-GCM (not Fernet's AES-128) via the
  `cryptography` library, refusing to run with no key configured rather
  than falling back to an insecure default.
- `core/immutable_audit.py` — two independent layers: SQLAlchemy
  event-listener guards blocking any ORM-level UPDATE/DELETE on audit
  rows, plus a SHA-256 hash chain making tampering that bypasses the ORM
  entirely (e.g. a raw `sqlite3` edit) detectable via
  `verify_audit_chain()`.
- `core/prompt_injection.py` — deterministic pattern-based detection
  (explicitly not LLM-based, with clear reasoning why), correctly
  positioned as defense-in-depth on top of the structural defense
  (ast_builder.py) that's existed since Phase 4, not a replacement for it.
- `app/services/malware_scan.py` — two-tier upload scanning: structural
  validation (stdlib `zipfile`, catches renamed executables and zip
  bombs) always runs; ClamAV (raw `clamd` socket protocol, zero extra
  dependency) is optional and clearly distinguishes "verified clean" from
  "not actually checked."
- Frontend: a complete login/bootstrap flow, token storage +
  axios-interceptor auth header injection, a Users admin page, and a
  genuinely subtle catch already made before I arrived — the Phase 7/8
  plain `<a href>` download link would silently stop working under auth
  (browser navigation doesn't carry the interceptor's header), so it was
  switched to a blob-fetch-and-save approach.

**What I fixed this session — wiring the infrastructure into real
enforcement:**
- Added `require_role(...)` to every workflow endpoint:
  `ingestion.upload`/`knowledge-base` (tester), `gatekeeper.confirm`
  (**approver** — this is the one that matters most: Gatekeeper
  confirmation is supposed to be a genuine second-person sign-off, which
  was previously fictional since anyone could type any name into
  `confirmed_by`), `generation.run`/`judge-evaluation` (tester),
  `refinement.*` (tester), `export.finalize`/`download` (approver for
  finalize, tester for download).
- Replaced every client-supplied identity field
  (`uploaded_by`/`confirmed_by`/`exported_by`/`added_by`/`edited_by`/
  `removed_by`) with `current_user.username` from the verified JWT —
  removed the now-meaningless fields from the request schemas entirely
  rather than leaving them as dead, misleading parameters.
- Wired `scan_for_injection()` into `generation.run` (blocks direct user
  input matching known attack patterns, HTTP 400, audited) and
  `sanitize_for_prompt_context()` into `planning_agent.py`'s prompt
  templating (neutralizes fence/tag escape tricks in lower-trust
  KB-derived text).
- Confirmed `main.py` already correctly calls
  `register_immutability_guards()` once at startup and includes the auth
  router; added "malware scanning" to its phase label, which was missing.
- **Caught a real inconsistency in `export_service.py`:** `email_sent_to`
  was correctly AES-256-GCM encrypted as genuine PII, but the same raw
  recipient addresses were then logged in cleartext in the `EMAIL_SENT`/
  `EMAIL_FAILED` audit entries' `detail` field two lines later — silently
  defeating the encryption. Fixed to log a recipient *count* in the audit
  trail instead, consistent with the encryption's own stated rationale.

**Testing honesty check — this phase had unusually strong test coverage**
because, contrary to the pattern in every other phase, several of the key
dependencies are genuinely installed in this sandbox: `pyjwt` and
`cryptography` are both real and working here, not just planned. **46 test
functions across 6 files were actually executed and passed**, including:
- real JWT tampering/expiry rejection (not mocked — actual signature
  verification failing against an actually-tampered token);
- real AES-256-GCM tamper detection via the GCM authentication tag (not a
  plain round-trip check — an actually-corrupted ciphertext actually
  fails to decrypt);
- real zip-bomb detection against an actual 50MB-inflating crafted file,
  and real malware-signature rejection against files starting with actual
  PE/ELF/shebang bytes;
- the prompt-injection scanner tested for zero false positives against
  legitimate business language containing trigger-adjacent words
  ("system access permissions") alongside catching all crafted attack
  strings;
- the pure hash-chain computation (tamper detection, chain linkage)
  verified correct, though the SQLAlchemy event-listener registration
  itself needs sqlalchemy (unavailable here) to exercise end-to-end.

What's still untested: the FastAPI-dependency plumbing itself
(`get_current_user`/`require_role` as actual request-handling code, not
just the pure `has_at_least()` logic they call) needs a live server and
DB, consistent with every other FastAPI-layer check in this project —
please run `pytest` plus a real end-to-end login → upload → confirm →
generate → export flow to confirm the RBAC wiring behaves as designed.
The ClamAV integration is structurally reviewed but has never talked to a
real `clamd` daemon.

**Where this leaves the project:** all 10 phases from the original
roadmap are now delivered. The most important remaining gap for a
genuinely production HIPAA-adjacent deployment is the same one flagged
back in Phase 8: SharePoint sync and email haven't been tested against a
real Microsoft 365 tenant or mail server. TLS in transit is deliberately
NOT implemented in application code (see `core/encryption.py`'s
docstring) — that's a reverse-proxy/ASGI-server deployment concern
(`uvicorn --ssl-keyfile/--ssl-certfile`, or nginx/Caddy in front), and
pretending otherwise in Python code would be a worse security posture
than using battle-tested infrastructure for it.

## Notes on testability outside this environment

Phases 8 and 9 involve live SharePoint tenants, real SMTP/Graph credentials,
and production security hardening. I can write the code and integration
points, but you'll need to supply credentials and test those pieces in your
own environment — this sandbox has no network access.

Phases 3-5 (the actual agentic RAG + SQL AST + reflection loop) are the
highest-complexity phases and will likely take multiple sessions each.
