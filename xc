[33mb8f68a4[m[33m ([m[1;36mHEAD[m[33m -> [m[1;32mmain[m[33m)[m chore: finalize Cognos DSD intelligence test generation working in order
 ...5430_add_scenario_order_to_cognos_test_cases.py |   32 [32m+[m
 backend/app/api/cognos_api.py                      |  118 [32m+[m[31m-[m
 .../cognos/extraction/nh_mmis_dsd_interpreter.py   |  307 [32m++[m[31m-[m
 .../app/cognos/extraction/nh_mmis_dsd_mapper.py    |   38 [32m+[m
 .../extraction/nh_mmis_requirement_builder.py      |   26 [32m+[m[31m-[m
 backend/app/cognos/pipeline.py                     |   19 [32m+[m[31m-[m
 backend/app/cognos/rules/__init__.py               |    3 [32m+[m[31m-[m
 backend/app/cognos/rules/scenario_composer.py      |  274 [32m++[m[31m-[m
 backend/app/cognos/rules/scenario_expander.py      |  307 [32m++[m[31m-[m
 backend/app/cognos/rules/scenario_patterns.py      |   54 [32m+[m[31m-[m
 backend/app/cognos/rules/sql_generator.py          |  959 [32m++++++++++[m
 backend/app/cognos/rules/test_case_builder.py      |  268 [32m++[m[31m-[m
 backend/app/cognos/schema/nh_mmis_dsd_models.py    |   19 [32m+[m
 backend/app/cognos/schema/nh_mmis_dsd_schema.yaml  |    1 [32m+[m
 backend/app/domain/cognos_models.py                |   28 [32m+[m[31m-[m
 backend/app/domain/cognos_requirement.py           |   87 [32m+[m
 backend/app/domain/cognos_test_case.py             |   21 [32m+[m
 backend/app/models/cognos_orm.py                   |    2 [32m+[m
 backend/app/services/cognos_excel_compiler.py      |    4 [32m+[m[31m-[m
 .../app/services/dsd_semantic_proof_renderer.py    |   20 [32m+[m[31m-[m
 backend/app/services/dsd_snapshot_resolver.py      |  253 [32m++[m[31m-[m
 backend/render/render_snapshot.js                  | 2002 [32m+++++++++++++++++++[m[31m-[m
 backend/test_combined_out/PRV027-CTRL-01.png       |  Bin [31m0[m -> [32m20331[m bytes
 backend/test_combined_out/PRV027-DBCO-01.png       |  Bin [31m0[m -> [32m20331[m bytes
 backend/test_combined_out/PRV027-SORT-01.png       |  Bin [31m0[m -> [32m20331[m bytes
 backend/test_combined_out/PRV027-SORT-02.png       |  Bin [31m0[m -> [32m20331[m bytes
 .../CR 18175 PRV-INT-027 UT DOCUMENT 1_crop.png    |  Bin [31m0[m -> [32m20331[m bytes
 backend/test_crops_output/count_total_errors.png   |  Bin [31m0[m -> [32m16219[m bytes
 backend/test_crops_output/p7_para3_dsd.png         |  Bin [31m0[m -> [32m20331[m bytes
 backend/test_crops_output/sort_error_field.png     |  Bin [31m0[m -> [32m10998[m bytes
 backend/test_crops_output/sort_prov_lic.png        |  Bin [31m0[m -> [32m10998[m bytes
 backend/test_crops_output/totals.png               |  Bin [31m0[m -> [32m16219[m bytes
 backend/test_inspect_all_images/p5_para10.png      |  Bin [31m0[m -> [32m67509[m bytes
 backend/test_inspect_all_images/p5_para14.png      |  Bin [31m0[m -> [32m26845[m bytes
 backend/test_inspect_all_images/p5_para18.png      |  Bin [31m0[m -> [32m10998[m bytes
 backend/test_inspect_all_images/p5_para2.png       |  Bin [31m0[m -> [32m34626[m bytes
 backend/test_inspect_all_images/p5_para5.png       |  Bin [31m0[m -> [32m15497[m bytes
 backend/test_inspect_all_images/p6_para13.png      |  Bin [31m0[m -> [32m8081[m bytes
 backend/test_inspect_all_images/p6_para16.png      |  Bin [31m0[m -> [32m39039[m bytes
 backend/test_inspect_all_images/p6_para2.png       |  Bin [31m0[m -> [32m17659[m bytes
 backend/test_inspect_all_images/p6_para21.png      |  Bin [31m0[m -> [32m17783[m bytes
 backend/test_inspect_all_images/p6_para24.png      |  Bin [31m0[m -> [32m12951[m bytes
 backend/test_inspect_all_images/p6_para25.png      |  Bin [31m0[m -> [32m16310[m bytes
 backend/test_inspect_all_images/p6_para30.png      |  Bin [31m0[m -> [32m7367[m bytes
 backend/test_inspect_all_images/p6_para32.png      |  Bin [31m0[m -> [32m24535[m bytes
 backend/test_inspect_all_images/p6_para37.png      |  Bin [31m0[m -> [32m35847[m bytes
 backend/test_inspect_all_images/p6_para38.png      |  Bin [31m0[m -> [32m17466[m bytes
 backend/test_inspect_all_images/p6_para39.png      |  Bin [31m0[m -> [32m8862[m bytes
 backend/test_inspect_all_images/p6_para41.png      |  Bin [31m0[m -> [32m26360[m bytes
 backend/test_inspect_all_images/p6_para5.png       |  Bin [31m0[m -> [32m27959[m bytes
 backend/test_inspect_all_images/p7_para10.png      |  Bin [31m0[m -> [32m38977[m bytes
 backend/test_inspect_all_images/p7_para16.png      |  Bin [31m0[m -> [32m28734[m bytes
 backend/test_inspect_all_images/p7_para3.png       |  Bin [31m0[m -> [32m20331[m bytes
 backend/test_inspect_all_images/p7_para5.png       |  Bin [31m0[m -> [32m17550[m bytes
 backend/test_inspect_all_images/p7_para8.png       |  Bin [31m0[m -> [32m16219[m bytes
 backend/test_inspect_all_images/p8_para11.png      |  Bin [31m0[m -> [32m35119[m bytes
 backend/test_inspect_all_images/p8_para15.png      |  Bin [31m0[m -> [32m45732[m bytes
 backend/test_inspect_all_images/p8_para2.png       |  Bin [31m0[m -> [32m30585[m bytes
 backend/test_inspect_all_images/p8_para6.png       |  Bin [31m0[m -> [32m13706[m bytes
 backend/test_inspect_all_images/p8_para9.png       |  Bin [31m0[m -> [32m27463[m bytes
 backend/test_inspect_all_images/p9_para15.png      |  Bin [31m0[m -> [32m26408[m bytes
 backend/test_inspect_all_images/p9_para18.png      |  Bin [31m0[m -> [32m40498[m bytes
 backend/test_inspect_all_images/p9_para2.png       |  Bin [31m0[m -> [32m37779[m bytes
 .../CR 18175 PRV-INT-027 UT DOCUMENT 1_margin.png  |  Bin [31m0[m -> [32m20331[m bytes
 .../Report Definition- OPT-TPL-005_margin.png      |  Bin [31m0[m -> [32m19114[m bytes
 backend/test_verify_12f/PRV027-CTRL-01.png         |  Bin [31m0[m -> [32m20331[m bytes
 backend/test_verify_12f/PRV027-DBCO-01.png         |  Bin [31m0[m -> [32m20331[m bytes
 backend/test_verify_12f/PRV027-SORT-01.png         |  Bin [31m0[m -> [32m10998[m bytes
 backend/test_verify_12f/PRV027-SORT-02.png         |  Bin [31m0[m -> [32m10998[m bytes
 backend/test_verify_12g/opr_tpl_sort.png           |  Bin [31m0[m -> [32m14832[m bytes
 backend/test_verify_12g/prv_dbco_01.png            |  Bin [31m0[m -> [32m20331[m bytes
 backend/test_verify_12g/prv_dbre_06.png            |  Bin [31m0[m -> [32m13706[m bytes
 backend/test_verify_12g/prv_labe_01.png            |  Bin [31m0[m -> [32m67509[m bytes
 backend/test_verify_12g/prv_layo_01.png            |  Bin [31m0[m -> [32m57823[m bytes
 backend/test_verify_12g/prv_sort.png               |  Bin [31m0[m -> [32m20331[m bytes
 backend/test_verify_12g/prv_sort_02.png            |  Bin [31m0[m -> [32m20331[m bytes
 .../Report Definition- OPT-TPL-005.png             |  Bin [31m0[m -> [32m18539[m bytes
 backend/test_verify_12g3_out/OPR-TPL-SORT.png      |  Bin [31m0[m -> [32m18539[m bytes
 backend/test_verify_12g3_out/PRV027-DBCO-01.png    |  Bin [31m0[m -> [32m20331[m bytes
 backend/test_verify_12g3_out/PRV027-SORT-01.png    |  Bin [31m0[m -> [32m20331[m bytes
 backend/test_verify_12g3_out/PRV027-SORT-02.png    |  Bin [31m0[m -> [32m20331[m bytes
 backend/tests/test_part7_traceability.py           |    2 [32m+[m[31m-[m
 backend/tests/test_phase12k3_sort_sql.py           |  179 [32m++[m
 backend/tests/test_phase12k_sql_generation.py      |  295 [32m+++[m
 backend/tests/test_phase12l_scheduled_snapshot.py  |   95 [32m+[m
 .../test_phase12m_header_section_validation.py     |  243 [32m+++[m
 .../test_phase12n_special_processing_validation.py |  223 [32m+++[m
 backend/tests/test_phase12o_layout_snapshot.py     |   62 [32m+[m
 backend/tests/test_phase12q1_db_persistence.py     |  121 [32m++[m
 backend/tests/test_phase12q_scenario_order.py      |  124 [32m++[m
 backend/tests/test_phase12r_selection_criteria.py  |  209 [32m++[m
 frontend/src/components/StepShell.jsx              |    4 [32m+[m[31m-[m
 frontend/src/components/cognos/CoverageMatrix.jsx  |  174 [32m++[m
 .../components/cognos/DSDIntelligenceSummary.jsx   |  134 [32m++[m
 frontend/src/components/cognos/EvidenceLibrary.jsx |  182 [32m++[m
 .../cognos/InteractiveEvidenceViewer.jsx           | 1671 [32m++++++++++++++++[m
 .../src/components/cognos/RequirementsView.jsx     |  137 [32m++[m
 .../src/components/cognos/TestScenarioExplorer.jsx | 1111 [32m+++++++++++[m
 .../src/components/cognos/TestingDimensions.jsx    |  118 [32m++[m
 frontend/src/pages/CognosDashboard.jsx             |  628 [32m++[m[31m----[m
 100 files changed, 9937 insertions(+), 617 deletions(-)
