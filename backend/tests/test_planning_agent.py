import json

import pytest

from app.agents.planning_agent import plan_scenarios, PlanningParseError

CONTEXT_SLICE = {
    "tables": [{"table_name": "MEMBERS", "description": "member records"}],
    "columns": [
        {"table_name": "MEMBERS", "column_name": "MEMBER_ID", "data_type": "VARCHAR(20)", "key_type": "PK"},
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND", "data_type": "CHAR(1)", "key_type": None},
    ],
    "joins": [], "valid_values": [], "business_rules": [],
}


def test_clean_json_response_parses_correctly():
    def fake_llm(prompt):
        assert "MEMBERS" in prompt
        assert "SWIPE_CARD_IND" in prompt
        return json.dumps([{
            "title": "Check indicator", "rationale": "r", "category": "valid_value_check",
            "target_table": "MEMBERS", "target_columns": ["SWIPE_CARD_IND"],
            "filters": [], "joins_needed": [],
        }])

    result = plan_scenarios(CONTEXT_SLICE, "validate swipe card indicator", fake_llm)
    assert len(result) == 1
    assert result[0].target_table == "MEMBERS"


def test_markdown_fenced_response_is_extracted():
    def fake_llm(prompt):
        return (
            "```json\n"
            '[{"title": "t", "rationale": "r", "category": "null_check", '
            '"target_table": "MEMBERS", "target_columns": ["MEMBER_ID"]}]\n'
            "```"
        )

    result = plan_scenarios(CONTEXT_SLICE, "req", fake_llm)
    assert len(result) == 1


def test_prose_wrapped_response_is_extracted():
    def fake_llm(prompt):
        return (
            "Here are the scenarios you requested:\n"
            '[{"title": "t", "rationale": "r", "category": "null_check", '
            '"target_table": "MEMBERS", "target_columns": ["MEMBER_ID"]}]\n'
            "Let me know if you need more!"
        )

    result = plan_scenarios(CONTEXT_SLICE, "req", fake_llm)
    assert len(result) == 1


def test_garbage_response_raises_clean_error():
    def fake_llm(prompt):
        return "I cannot help with that."

    with pytest.raises(PlanningParseError):
        plan_scenarios(CONTEXT_SLICE, "req", fake_llm)


def test_max_scenarios_cap_is_respected():
    def fake_llm(prompt):
        items = [
            {"title": f"t{i}", "rationale": "r", "category": "null_check",
             "target_table": "MEMBERS", "target_columns": ["MEMBER_ID"]}
            for i in range(10)
        ]
        return json.dumps(items)

    result = plan_scenarios(CONTEXT_SLICE, "req", fake_llm, max_scenarios=3)
    assert len(result) == 3


def test_malformed_individual_item_is_skipped_not_fatal():
    def fake_llm(prompt):
        return json.dumps([
            {"title": "good", "rationale": "r", "category": "null_check",
             "target_table": "MEMBERS", "target_columns": ["MEMBER_ID"]},
            "this is not a dict",
            42,
        ])

    result = plan_scenarios(CONTEXT_SLICE, "req", fake_llm)
    assert len(result) == 1
    assert result[0].title == "good"


def test_few_shot_example_is_included_in_prompt():
    seen_prompts = []

    def fake_llm(prompt):
        seen_prompts.append(prompt)
        return json.dumps([{
            "title": "t", "rationale": "r", "category": "null_check",
            "target_table": "MEMBERS", "target_columns": ["MEMBER_ID"],
        }])

    few_shot = {"cached_payload": [{"test_scenario": "Prior example scenario"}]}
    plan_scenarios(CONTEXT_SLICE, "req", fake_llm, few_shot_example=few_shot)
    assert "Prior example scenario" in seen_prompts[0]
