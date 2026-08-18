# Test fixtures

Checked-in sample files used by the Phase 1 test suite:

- `sample_ldm.xlsx` — synthetic LDM with 5 sheets: column-level metadata
  (MEMBERS, CLAIMS tables), a join mapping sheet, a valid-values sheet, a
  business-rules sheet, and one deliberately unrecognizable "junk" sheet
  (to verify it gets skipped, not guessed at).
- `sample_rdd.docx` — synthetic RDD with one structured table (PROVIDERS)
  and free-form paragraph text including an embedded rule in prose, to
  verify prose is never auto-promoted to a business rule.
- `junk.csv` — a file with no recognizable LDM/RDD structure at all, used
  to verify the "Insufficient metadata available" path.

These are synthetic and contain no real healthcare data.
