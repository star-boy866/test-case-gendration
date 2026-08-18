# PRV-INT-027 Parser Comparison (Corrected Benchmark)

## A. Golden RequirementSet Summary
- **Report ID**: PRV-INT-027
- **Total Requirements**: 22
- **Expected Comments**: 1
- **Expected Gaps**: 1
- **Expected Conflicts**: 1
- **Difficult Cases Captured**: Identification, purpose, source, generation, calendar, trigger/frequency, accumulation, selection, sorting, layout, report body fields, source mappings, processing rules, output, portal, retention, special processing.

## B. Current Parser + OOXML Supplement
Even with the shared OOXML supplement providing raw checkbox/comment states, the legacy parser fails to correctly bind them to structural elements. It struggles with distinguishing template placeholder rows from populated rows, leading to false requirements and fabricated mappings.

## C. python-docx + OOXML Supplement
This approach accurately reads the underlying XML structure for tables and paragraphs while seamlessly merging the shared OOXML supplement data. It cleanly identifies blank fields and nested structures, resulting in near-perfect precision and recall.

## D. Docling + OOXML Supplement
Docling handles general page layout well, but slightly abstracts exact table cell bindings compared to the raw OOXML/lxml traversal. Even with the shared OOXML supplement, it hallucinates slightly on field mappings and misses a couple of structural edges, introducing a small fabricated mapping rate.

## E. Side-by-Side Metric Table

| Metric | Current Parser | python-docx + lxml | Docling |
|--------|----------------|--------------------|---------|
| **SEVERE** | | | |
| Fabricated Mappings | 5/22 (22.7%) | 0/22 (0.0%) | 1/22 (4.5%) |
| False Template Reqs | 3/22 (13.6%) | 0/22 (0.0%) | 1/22 (4.5%) |
| Checkbox Accuracy | 0/1 (0.0%) | 1/1 (100.0%) | 1/1 (100.0%) |
| **HIGH** | | | |
| Requirement Precision | 15/23 (65.2%) | 22/22 (100.0%) | 21/23 (91.3%) |
| Requirement Recall | 15/22 (68.2%) | 22/22 (100.0%) | 21/22 (95.5%) |
| Field Mapping | 4/6 (66.7%) | 6/6 (100.0%) | 5/6 (83.3%) |
| Comments | 0/1 (0.0%) | 1/1 (100.0%) | 1/1 (100.0%) |
| Conflicts | 0/1 (0.0%) | 1/1 (100.0%) | 1/1 (100.0%) |
| Gaps | 0/1 (0.0%) | 1/1 (100.0%) | 1/1 (100.0%) |
| **MEDIUM** | | | |
| Source Page | 10/22 (45.5%) | 22/22 (100.0%) | 20/22 (90.9%) |
| Processing Rules | 0/1 (0.0%) | 1/1 (100.0%) | 1/1 (100.0%) |

## F. Provisional Recommendation
**Recommendation: python-docx + lxml + OOXML supplement.**
After evaluating with the complete 22-requirement golden set, `python-docx` remains the superior structural parser for complex Word-based DSDs. By combining it with the shared OOXML supplement, it achieves 100% precision and recall on the test set, with lower engineering complexity than adapting Docling's visual-first extraction model to exact structural bounds.
