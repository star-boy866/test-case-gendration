# Template Variant Inventory

To support the 600-report rollout, the Golden Corpus has identified 5 core structural variants of Cognos DSDs (Report Definitions).

| Variant ID | Representative Reports | Structural Characteristics | Parser Status | Golden Fixture Status | Certification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `VAR-01` | `PRV-INT-027` | Standard layout, clean requirement matrices, 4-column format. | HIGH CONFIDENCE | 1 Golden Fixture | CERTIFIED |
| `VAR-02` | `OPR-SRA-139` | General Ledger layouts, complex merged headers, conditional formatting tables. | HIGH CONFIDENCE | 1 Golden Fixture | CERTIFIED |
| `VAR-03` | `OPR-TPL-005` | Third Party Liability, nested sub-tables for Program Generated Measures. | HIGH CONFIDENCE | 1 Golden Fixture | CERTIFIED |
| `VAR-04` | `section125.txt` | Deeply nested text-based conditions, unstructured layouts, legacy extraction formats. | LOW CONFIDENCE | None | UNCERTIFIED |
| `VAR-05` | `Report Definition template.docx` | Empty/Placeholder structured documents lacking populated rows. | HIGH CONFIDENCE | None | PARTIALLY_CERTIFIED |

## Certification Gap
Currently, 3 of the 5 variants (`VAR-01`, `VAR-02`, `VAR-03`) are **CERTIFIED** with golden corpus coverage proving zero semantic drift. `VAR-04` and `VAR-05` require additional manual QA and golden fixture creation before 600-report automated execution.

## Parser Routing Plan
The `DocumentParser` assigns confidence to extracted outputs. If `confidence < 0.9` (as expected with `VAR-04`), the generated artifact is natively flagged `REVIEW_REQUIRED` inside the Refinement Grid, blocking automated output distribution.
