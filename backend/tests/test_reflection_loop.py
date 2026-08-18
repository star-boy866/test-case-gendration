import json

from app.agents.pipeline import run_pipeline
from app.agents.reflection_loop import run_reflection_loop
from app.agents.schemas import GeneratedScenario

CONTEXT_SLICE = {
    "tables": [{"table_name": "MEMBERS", "description": "member records"}],
    "columns": [
        {"table_name": "MEMBERS", "column_name": "MEMBER_ID", "data_type": "VARCHAR(20)", "key_type": "PK"},
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND", "data_type": "CHAR(1)", "key_type": None},
    ],
    "candidate_tables": ["MEMBERS"],
    "joins": [],
    "valid_values": [
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND", "valid_value": "Y", "meaning": "issued"},
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND", "valid_value": "N", "meaning": "not issued"},
    ],
    "business_rules": [
        {"rule_text": "SWIPE_CARD_IND must be Y or N", "related_table": "MEMBERS", "related_column": "SWIPE_CARD_IND"},
        {"rule_text": "MEMBER_ID must never be null", "related_table": "MEMBERS", "related_column": "MEMBER_ID"},
    ],
}


def test_reflection_loop_closes_a_real_coverage_gap():
    def fake_llm(prompt):
        if "JSON array" in prompt:
            if "ADDITIONAL INSTRUCTION" in prompt:
                assert "MEMBER_ID must never be null" in prompt
                return json.dumps([{
                    "title": "Check MEMBER_ID not null", "rationale": "r", "category": "null_check",
                    "target_table": "MEMBERS", "target_columns": ["MEMBER_ID"],
                    "filters": [{"column": "MEMBER_ID", "op": "IS NULL", "value": ""}],
                }])
            return json.dumps([{
                "title": "Check SWIPE_CARD_IND domain", "rationale": "r", "category": "valid_value_check",
                "target_table": "MEMBERS", "target_columns": ["SWIPE_CARD_IND"],
                "filters": [{"column": "SWIPE_CARD_IND", "op": "NOT IN", "value": "('Y','N')"}],
            }])
        if "SWIPE_CARD_IND" in prompt:
            return json.dumps({"test_scenario": "Validate SWIPE_CARD_IND values", "detailed_test_steps": "1. Query.", "expected_results": "Only Y/N."})
        return json.dumps({"test_scenario": "Validate MEMBER_ID not null", "detailed_test_steps": "1. Query.", "expected_results": "No nulls."})

    initial_scenarios, _ = run_pipeline(CONTEXT_SLICE, "validate members table", fake_llm)
    assert len(initial_scenarios) == 1  # only covers one of two rules initially

    result = run_reflection_loop(initial_scenarios, CONTEXT_SLICE, "validate members table", fake_llm, max_iterations=2)

    assert result.critic_report.passed is True
    assert len(result.scenarios) == 2
    assert result.iterations_used == 1


def test_exact_duplicate_scenarios_deduped_without_any_llm_call():
    plain_context = {"columns": [{"table_name": "MEMBERS", "column_name": "MEMBER_NAME", "key_type": None}], "valid_values": [], "business_rules": []}

    dup_scenarios = [
        GeneratedScenario(
            test_scenario="A", detailed_test_steps="s", expected_results="e",
            verification_sql="SELECT MEMBERS.MEMBER_NAME FROM MEMBERS;", category="format_check", ast_valid=True,
            referenced_tables=["MEMBERS"], referenced_columns=["MEMBERS.MEMBER_NAME"],
        ),
        GeneratedScenario(
            test_scenario="B", detailed_test_steps="s", expected_results="e",
            verification_sql="SELECT MEMBERS.MEMBER_NAME FROM MEMBERS;", category="format_check", ast_valid=True,
            referenced_tables=["MEMBERS"], referenced_columns=["MEMBERS.MEMBER_NAME"],
        ),
    ]

    def should_not_be_called(prompt):
        raise AssertionError("LLM should not be called for a purely mechanical dedupe fix")

    result = run_reflection_loop(dup_scenarios, plain_context, "req", should_not_be_called, max_iterations=2)
    assert len(result.scenarios) == 1
    assert result.critic_report.passed is True


def test_unrecoverable_gap_is_bounded_not_infinite():
    context_slice = {
        "columns": [{"table_name": "MEMBERS", "column_name": "MEMBER_ID", "key_type": "PK"}],
        "candidate_tables": ["MEMBERS"], "joins": [], "valid_values": [],
        "business_rules": [{"rule_text": "impossible rule", "related_table": "MEMBERS", "related_column": "NONEXISTENT_COL"}],
    }

    def always_hallucinate(prompt):
        if "JSON array" in prompt:
            return json.dumps([{
                "title": "t", "rationale": "r", "category": "null_check",
                "target_table": "MEMBERS", "target_columns": ["NONEXISTENT_COL"],
            }])
        return json.dumps({"test_scenario": "t", "detailed_test_steps": "s", "expected_results": "e"})

    result = run_reflection_loop([], context_slice, "req", always_hallucinate, max_iterations=2)
    assert result.critic_report.passed is False
    assert result.iterations_used <= 2


def test_already_passing_batch_returns_immediately_with_zero_iterations():
    plain_context = {"columns": [{"table_name": "T", "column_name": "C", "key_type": None}], "valid_values": [], "business_rules": []}
    good_scenario = GeneratedScenario(
        test_scenario="Good", detailed_test_steps="s", expected_results="e",
        verification_sql="SELECT T.C FROM T;", category="format_check", ast_valid=True,
        referenced_tables=["T"], referenced_columns=["T.C"],
    )

    def should_not_be_called(prompt):
        raise AssertionError("LLM should not be called when the batch already passes")

    result = run_reflection_loop([good_scenario], plain_context, "req", should_not_be_called, max_iterations=2)
    assert result.critic_report.passed is True
    assert result.iterations_used == 0
