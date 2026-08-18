# Healthcare NL-to-Test-Case Generation AI Agent

Enterprise, zero-trust, open-source platform that converts natural language
requirements and Report Design Documents (RDDs) into SIT/QA test scenarios
for healthcare data systems — **without any direct database access**.

This repo is being built in phases. See `docs/PHASES.md` for the full
roadmap, current status, and per-phase delivery notes.

## Current status: all 10 original roadmap phases delivered

- **Phase 0 — Scaffold:** FastAPI backend + React/Vite/Tailwind frontend,
  SQLite schema, config.
- **Phase 1 — Ingestion & Knowledge Base:** real parsing of .xlsx/.csv/
  .docx/.pdf RDDs/LDMs into structured tables/columns/joins/valid-values/
  business-rules, with strict hallucination prevention and SHA-256-based
  cache-busting.
- **Phase 2 — Gatekeeper (strict blocking step):** human confirmation of
  CR ID / CR Description / Report ID against real extracted scope, with a
  real enforcement gate on `/api/generation/run`.
- **Phase 3 — Context Minimizer + semantic cache:** real schema-linking,
  a FAISS-or-numpy-fallback semantic cache with a BM25 hybrid rescue
  signal, and a Fast-Path Router for instant boilerplate scenarios.
- **Phase 4 — Planning Agent + AST Builder + Generator:** real LLM-backed
  test scenario generation (Ollama, local inference only), with every
  proposed table/column/join validated against the Knowledge Base before
  it can become SQL or scenario text.
- **Phase 5 — Critic + Reflection Loop:** a deterministic 4-point Boolean
  checklist evaluates every generated batch, with bounded, targeted
  self-correction. Only Critic-approved output gets cached.
- **Phase 6 — Interactive Refinement Grid (HITL):** Step 3 is now fully
  live — generate scenarios from a requirement, edit any field inline,
  add manual scenarios, or remove rows, all backed by a real database and
  a per-field audit trail. Every human override is logged against the
  scenario's original AI-generated value, never silently overwritten.
- **Phase 7 — Excel Compiler:** Step 4 now compiles the Refinement Grid
  into a real, downloadable .xlsx workbook — the 5 required columns plus
  a Cover sheet with Report ID/CR ID/source-document traceability.
  Generate → download works end-to-end from the browser.
- **Phase 8 — SharePoint Sync + Email Distribution:** Step 4 can now
  optionally push the workbook to a SharePoint document library
  (Microsoft Graph, app-only auth) and email an HTML summary to a
  distribution list. Partial-success semantics — a SharePoint or SMTP
  failure never makes an otherwise-successful export look failed, and
  every outcome (success or failure, for each) gets its own audit event.
  **Not yet tested against a real Microsoft 365 tenant or mail server —
  see docs/PHASES.md Phase 8 notes before relying on this in production.**
- **Phase 9 — RBAC, Immutable Audit, Encryption, Prompt-Injection &
  Malware Defenses:** real login (JWT, PBKDF2 password hashing), three
  hierarchical roles (tester/approver/admin) enforced on every workflow
  endpoint, AES-256-GCM encryption at rest for stored PII, a SHA-256
  hash-chained append-only audit log with a `verify` endpoint, deterministic
  prompt-injection screening, and upload malware scanning (structural
  validation always; optional ClamAV). Every "who did this" field
  (`confirmed_by`, `exported_by`, etc.) now comes from the authenticated
  identity — none of it is client-supplied text anymore.
- **Phase 10 — LLM-as-Judge + Structured Telemetry:** every pipeline stage
  now emits JSON-structured telemetry (agent transitions, semantic cache
  distance/BM25 scores, per-stage latency). A non-gating LLM-as-Judge
  layer scores Completeness/Hallucination Prevention/Schema Adherence in
  the background (never blocks the response, never overrides the
  deterministic Phase 5 Critic) — viewable in the Refinement Grid a few
  seconds after generation.

First-time setup now requires creating an account — visit the app, and
the login screen offers "Create the initial admin account" (works once,
while no users exist yet; see docs/PHASES.md Phase 9 notes).

## Quick start

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Visit http://localhost:8000/health and http://localhost:8000/docs

To exercise real Phase 4 generation (not just fast-path/cached results),
you'll need [Ollama](https://ollama.com) running locally:
```bash
ollama serve
ollama pull llama3.1:8b   # or set OLLAMA_MODEL in .env to a model you have
```
Without Ollama running, `/api/generation/run` still works for fast-path
matches and cache hits — it returns a clear HTTP 503 (not a crash) only
when it actually needs the LLM and can't reach it.

To exercise real Phase 8 SharePoint sync / email, set the `SHAREPOINT_*`
and `SMTP_*` variables in `.env` (see `.env.example`) and
`pip install msal`. Without them configured, exporting still works — the
SharePoint/email steps just report a clear "not configured" error instead
of a crash, and the Excel file itself is unaffected either way.

Every workflow endpoint now requires login (Phase 9). Before doing
anything else:
```bash
# Replace SECRET_KEY (signs JWTs) and generate an ENCRYPTION_KEY (AES-256,
# encrypts stored PII like export recipient lists) — both empty/placeholder
# by default so nothing accidentally ships with a real key in git history.
python3 -c "import secrets; print(secrets.token_urlsafe(32))"       # -> SECRET_KEY
python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"  # -> ENCRYPTION_KEY
```
Put both in `.env`, then open the app — the login screen's "Create the
initial admin account" link works exactly once, while no users exist yet.
Every account after that is created by an admin from the Users page.
`CLAMD_HOST` (optional, malware scanning) can stay empty — structural
upload validation (disguised executables, zip bombs) always runs
regardless; ClamAV is an optional second layer requiring its own daemon.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Visit http://localhost:5173 — try Step 1 (upload `backend/tests/fixtures/sample_ldm.xlsx`
with a Report ID like `RPT-Demo`), then Step 2 to confirm scope, Step 3 to
generate/edit scenarios, and Step 4 to download the Excel workbook. On
Step 3, a non-fast-path generation call also schedules a background
LLM-as-Judge review — a supplementary quality card appears a few seconds
later if Ollama is running (see Phase 10 notes in docs/PHASES.md).

### Tests
```bash
cd backend
pytest
```

## Requirements
- Python 3.11+
- Node.js 20+
- (Later phases) Ollama installed locally for open-source LLM inference

## License
Internal enterprise use — adjust as needed for your organization.
