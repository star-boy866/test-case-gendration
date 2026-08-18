# core/

Cross-cutting infrastructure — configuration, security, and telemetry —
used across services/, agents/, and api/ rather than belonging to any one
of them.

- config.py (Phase 0) - all environment-driven settings (pydantic-settings).
  Every setting referenced anywhere in this app is defined here with a
  working default; see backend/.env.example for the full list with
  explanations of what each one does and which phase introduced it.
- security.py (Phase 9) - password hashing (stdlib PBKDF2-HMAC-SHA256, 200k
  iterations) and JWT issuing/verification (pyjwt). Both dependencies are
  genuinely installed in the sandbox this was built in, so the round-trip,
  expiry, and tamper-detection behavior were actually run, not just
  syntax-checked.
- rbac.py (Phase 9) - three roles (tester/approver/admin), hierarchical
  not a flat allowlist. `CurrentUser.has_at_least()` — the pure role-
  comparison logic — was run for real; the FastAPI dependency functions
  themselves (`get_current_user`/`require_role`) need a live request/DB
  context to test end-to-end, consistent with every other FastAPI-
  dependency-based check in this project.
- encryption.py (Phase 9) - AES-256-GCM field encryption via the
  `cryptography` library (genuinely installed here — round-trip AND tamper
  detection via the GCM auth tag were actually run). Refuses to operate
  with no ENCRYPTION_KEY configured rather than using an insecure default.
- immutable_audit.py (Phase 9) - two independent layers protecting
  AuditLogEntry: SQLAlchemy event-listener guards block any UPDATE/DELETE
  through the ORM (the only way application code touches this table), and
  a SHA-256 hash chain (each row covers its own fields + the previous
  row's hash) makes tampering that bypasses the ORM entirely — e.g. a raw
  sqlite3 edit — detectable after the fact via `verify_audit_chain()`,
  exposed at `GET /api/auth/audit-log/verify`. The pure hash-chain
  computation was run for real; the SQLAlchemy event-listener registration
  itself needs sqlalchemy (not installed in this sandbox) to exercise
  end-to-end.
- prompt_injection.py (Phase 9) - deterministic, pattern-based (not
  LLM-based — see the module's own docstring for why) detection for direct
  user input, plus a separate sanitization pass for lower-trust
  Knowledge-Base-derived text templated into LLM prompts. Explicitly
  positioned as defense-in-depth on TOP of the structural defense that
  already existed since Phase 4 (ast_builder.py rejecting anything not in
  the verified schema) — not the primary defense. Fully tested (pure
  Python, zero dependencies): zero false positives on legitimate business
  language containing trigger-adjacent words, catches all attack patterns
  tested.
- telemetry.py (Phase 10) - structured JSON logging for agent state
  transitions, semantic cache distance/BM25 scores, and pipeline latency.
  Prefers `structlog` if installed, falls back to an equivalent
  dependency-free stdlib-logging implementation otherwise (same pattern as
  FAISS in Phase 3, LangGraph in Phase 4).

See docs/PHASES.md for what was actually executed vs. syntax-checked-only
in each module, phase by phase.
