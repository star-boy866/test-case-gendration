import json

from app.agents.pipeline import run_pipeline

CONTEXT_SLICE = {
    "tables": [{"table_name": "MEMBERS", "description": "member records"}],
    "columns": [
        {"table_name": "MEMBERS", "column_name": "MEMBER_ID", "data_type": "VARCHAR(20)", "key_type": "PK"},
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND", "data_type": "CHAR(1)", "key_type": None},
    ],
    "candidate_tables": ["MEMBERS"],
    "joins": [], "valid_values": [], "business_rules": [],
}


def _generator_response():
    return json.dumps({
        "test_scenario": "Validate SWIPE_CARD_IND values",
        "detailed_test_steps": "1. Query MEMBERS.",
        "expected_results": "Only Y or N present.",
    })


def test_valid_scenario_survives_full_pipeline():
    def fake_llm(prompt):
        if "JSON array" in prompt:
            return json.dumps([{
                "title": "Valid check", "rationale": "r", "category": "valid_value_check",
                "target_table": "MEMBERS", "target_columns": ["SWIPE_CARD_IND"],
                "filters": [{"column": "SWIPE_CARD_IND", "op": "NOT IN", "value": "('Y','N')"}],
            }])
        return _generator_response()

    scenarios, warnings = run_pipeline(CONTEXT_SLICE, "validate swipe card indicator", fake_llm)
    assert len(scenarios) == 1
    assert scenarios[0].test_scenario == "Validate SWIPE_CARD_IND values"
    assert "MEMBERS" in scenarios[0].verification_sql
    assert warnings == []


def test_hallucinated_scenario_dropped_valid_one_survives():
    call_count = {"n": 0}

    def fake_llm(prompt):
        call_count["n"] += 1
        if "JSON array" in prompt:
            return json.dumps([
                {"title": "Valid check", "rationale": "r", "category": "valid_value_check",
                 "target_table": "MEMBERS", "target_columns": ["SWIPE_CARD_IND"],
                 "filters": [{"column": "SWIPE_CARD_IND", "op": "NOT IN", "value": "('Y','N')"}]},
                {"title": "Hallucinated check", "rationale": "r", "category": "valid_value_check",
                 "target_table": "NONEXISTENT_TABLE", "target_columns": ["FAKE_COL"]},
            ])
        return _generator_response()

    scenarios, warnings = run_pipeline(CONTEXT_SLICE, "validate swipe card indicator", fake_llm)

    assert len(scenarios) == 1
    assert len(warnings) == 1
    assert "NONEXISTENT_TABLE" in warnings[0]
    # Critical: the hallucinated scenario must NEVER reach the Generator —
    # exactly 2 calls (1 planning + 1 generator for the ONE valid scenario).
    assert call_count["n"] == 2


def test_planning_failure_returns_empty_with_warning():
    def fake_llm(prompt):
        return "I cannot help with that."

    scenarios, warnings = run_pipeline(CONTEXT_SLICE, "req", fake_llm)
    assert scenarios == []
    assert len(warnings) == 1
    assert "Planning Agent failed" in warnings[0]


def test_zero_scenarios_proposed_returns_warning():
    def fake_llm(prompt):
        return "[]"

    scenarios, warnings = run_pipeline(CONTEXT_SLICE, "req", fake_llm)
    assert scenarios == []
    assert "zero scenarios" in warnings[0]


def test_generator_failure_drops_only_that_scenario():
    def fake_llm(prompt):
        if "JSON array" in prompt:
            return json.dumps([{
                "title": "Valid check", "rationale": "r", "category": "valid_value_check",
                "target_table": "MEMBERS", "target_columns": ["SWIPE_CARD_IND"],
            }])
        return "not valid json at all"

    scenarios, warnings = run_pipeline(CONTEXT_SLICE, "req", fake_llm)
    assert scenarios == []
    assert "Generator Agent failed" in warnings[0]


def test_max_scenarios_respected_end_to_end():
    def fake_llm(prompt):
        if "JSON array" in prompt:
            items = [
                {"title": f"t{i}", "rationale": "r", "category": "null_check",
                 "target_table": "MEMBERS", "target_columns": ["MEMBER_ID"]}
                for i in range(10)
            ]
            return json.dumps(items)
        return _generator_response()

    scenarios, warnings = run_pipeline(CONTEXT_SLICE, "req", fake_llm, max_scenarios=2)
    assert len(scenarios) == 2
