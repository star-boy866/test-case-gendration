# services/

Business logic lives here, separated from API route handlers.

Delivered:
- document_parser.py (Phase 1) - RDD/LDM parsing into structured metadata.
- knowledge_base.py (Phase 1) - Knowledge Base storage/retrieval, cache-busting.
- gatekeeper.py (Phase 2) - strict blocking step (scope confirmation + gate).
- embeddings.py (Phase 3) - dependency-free hashing-trick text embedder.
- bm25.py (Phase 3) - dependency-free BM25 lexical scorer.
- vector_index.py (Phase 3) - FAISS-or-numpy-fallback L2 nearest-neighbor index.
- cache_classification.py (Phase 3) - pure hit/partial_hit/miss decision logic
  (FAISS L2 thresholds + BM25 hybrid rescue).
- context_minimizer.py (Phase 3) - schema-linking / reduce layer.
- semantic_cache.py (Phase 3) - ties embeddings + vector_index + bm25 +
  cache_classification + SemanticCacheEntry into the Local Semantic Cache Layer.
- ollama_client.py (Phase 4) - real Ollama HTTP client (default_llm_call);
  every agent depends on a plain Callable[[str], str], not this module
  directly, so agents are testable without a live Ollama daemon.
- sql_render.py (Phase 4) - deterministic AST -> ANSI SQL renderer. No LLM
  involved; shared as-is with Phase 5's SQL Compiler pipeline stage.
- refinement.py (Phase 6) - backs the Interactive Refinement Grid: grid
  CRUD, plus the override-diffing/audit-logging that makes every human
  edit to an AI-generated scenario traceable back to its original value.
- excel_compiler.py (Phase 7) - pure function (rows/metadata in, openpyxl
  Workbook out, no DB/filesystem access) building the 5-column Excel
  Scenario Output spec plus a traceability Cover sheet. Tested for real in
  this sandbox (openpyxl available, sqlalchemy not) including a genuine
  save/reload file round-trip.
- export_service.py (Phase 7, extended Phase 8) - wires excel_compiler.py
  to real session/grid/source-document data, disk persistence, SHA-256
  hashing, and audit logging. `sync_and_notify()` (Phase 8) best-effort
  uploads to SharePoint and/or emails a distribution list with
  partial-success semantics — a SharePoint/SMTP failure never makes an
  otherwise-successful Excel export look failed.
- sharepoint_client.py (Phase 8) - Microsoft Graph API upload via the
  standard app-only (client credentials) OAuth flow. Pure URL-building and
  real connection-failure handling are tested in this sandbox; real
  auth/upload needs a live Microsoft 365 tenant and `msal` installed.
- email_service.py (Phase 8) - HTML email notification via stdlib
  `smtplib`/`email` (zero extra dependency). Pure email-building and real
  connection-failure handling are tested in this sandbox; real SMTP
  auth/delivery needs an actual mail server.
- judge_service.py (Phase 10) - persists LLM-as-Judge results (see
  agents/llm_judge.py) via FastAPI BackgroundTasks. Opens its own DB
  session rather than reusing the request's, since a background task
  runs after the request-scoped session may already be closed — a real,
  easy-to-miss FastAPI detail, called out explicitly in its docstring.
- malware_scan.py (Phase 9) - two-tier file scanning on every upload:
  structural validation (stdlib zipfile, always runs — catches renamed
  executables and zip bombs) + optional ClamAV (raw clamd socket
  protocol, zero extra dependency). Fully tested against real Phase 1
  fixtures plus deliberately crafted attack files (disguised executable,
  fake PDF, zip bomb) — see docs/PHASES.md Phase 9 notes.

Planned modules: none remaining from the original 8-phase roadmap or
Phase 10. See app/core/README.md for Phase 9's security modules
(rbac.py, security.py, encryption.py, immutable_audit.py,
prompt_injection.py all live in core/, not here, since they're
cross-cutting infrastructure rather than one workflow stage's business
logic).

Note: fast_path_router.py currently lives in this directory rather than
agents/ — it's a pure rules engine with no agent/LLM orchestration, so it
fit services/ better than agents/ once actually written. agents/ remains
reserved for the Phase 4/5 LangGraph/CrewAI orchestration itself.
