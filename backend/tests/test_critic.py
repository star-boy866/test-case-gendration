from app.agents.schemas import GeneratedScenario
from app.agents.critic import evaluate

CONTEXT_SLICE = {
    "columns": [
        {"table_name": "MEMBERS", "column_name": "MEMBER_ID", "key_type": "PK"},
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND", "key_type": None},
    ],
    "valid_values": [
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND", "valid_value": "Y"},
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND", "valid_value": "N"},
    ],
    "business_rules": [
        {"rule_text": "SWIPE_CARD_IND must be Y or N, never null", "related_table": "MEMBERS", "related_column": "SWIPE_CARD_IND"},
        {"rule_text": "MEMBER_ID must be unique", "related_table": "MEMBERS", "related_column": "MEMBER_ID"},
    ],
}


def _scenario(title, sql, category, tables, columns):
    return GeneratedScenario(
        test_scenario=title, detailed_test_steps="...", expected_results="...",
        verification_sql=sql, category=category, ast_valid=True,
        referenced_tables=tables, referenced_columns=columns,
    )


def test_good_batch_passes_all_four_checks():
    scenarios = [
        _scenario(
            "Validate SWIPE_CARD_IND domain",
            "SELECT MEMBERS.SWIPE_CARD_IND FROM MEMBERS WHERE MEMBERS.SWIPE_CARD_IND NOT IN (Y,N);",
            "valid_value_check", ["MEMBERS"], ["MEMBERS.SWIPE_CARD_IND"],
        ),
        _scenario(
            "Validate MEMBER_ID uniqueness",
            "SELECT MEMBERS.MEMBER_ID FROM MEMBERS GROUP BY MEMBERS.MEMBER_ID HAVING COUNT(*) > 1;",
            "duplicate_check", ["MEMBERS"], ["MEMBERS.MEMBER_ID"],
        ),
    ]
    report = evaluate(scenarios, CONTEXT_SLICE)
    assert report.passed is True
    assert report.score == 1.0
    assert report.issues == []


def test_uncovered_business_rule_fails_checklist():
    scenarios = [
        _scenario("Check A", "SELECT MEMBERS.SWIPE_CARD_IND FROM MEMBERS;", "format_check", ["MEMBERS"], ["MEMBERS.SWIPE_CARD_IND"]),
    ]
    report = evaluate(scenarios, CONTEXT_SLICE)
    assert report.checklist["business_rules_covered"] is False
    assert any("MEMBER_ID must be unique" in issue for issue in report.issues)


def test_exact_duplicate_sql_fails_checklist():
    scenarios = [
        _scenario("Check A", "SELECT MEMBERS.SWIPE_CARD_IND FROM MEMBERS;", "format_check", ["MEMBERS"], ["MEMBERS.SWIPE_CARD_IND"]),
        _scenario("Check A copy", "SELECT MEMBERS.SWIPE_CARD_IND FROM MEMBERS;", "format_check", ["MEMBERS"], ["MEMBERS.SWIPE_CARD_IND"]),
    ]
    report = evaluate(scenarios, CONTEXT_SLICE)
    assert report.checklist["no_duplicate_scenarios"] is False


def test_missing_edge_case_coverage_fails_when_pk_or_domain_present():
    scenarios = [
        _scenario("Check A", "SELECT MEMBERS.SWIPE_CARD_IND FROM MEMBERS;", "format_check", ["MEMBERS"], ["MEMBERS.SWIPE_CARD_IND"]),
    ]
    report = evaluate(scenarios, CONTEXT_SLICE)
    assert report.checklist["edge_cases_covered"] is False


def test_edge_case_check_vacuously_passes_without_pk_or_domain_signal():
    plain_context = {"columns": [{"table_name": "T", "column_name": "C", "key_type": None}], "valid_values": [], "business_rules": []}
    scenarios = [_scenario("Check", "SELECT T.C FROM T;", "format_check", ["T"], ["T.C"])]
    report = evaluate(scenarios, plain_context)
    assert report.checklist["edge_cases_covered"] is True


def test_ast_invalid_scenario_fails_sql_schema_check():
    bad = GeneratedScenario(
        test_scenario="Bad", detailed_test_steps="...", expected_results="...",
        verification_sql="SELECT 1;", category="format_check", ast_valid=False,
        referenced_tables=[], referenced_columns=[],
    )
    report = evaluate([bad], CONTEXT_SLICE)
    assert report.checklist["sql_schema_valid"] is False


def test_no_business_rules_is_vacuously_satisfied():
    context_no_rules = {"columns": [], "valid_values": [], "business_rules": []}
    report = evaluate([], context_no_rules)
    assert report.checklist["business_rules_covered"] is True
