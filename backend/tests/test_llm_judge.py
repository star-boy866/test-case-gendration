import json

from app.agents.llm_judge import run_llm_judge, JudgeParseError

SCENARIOS = [
    {
        "test_scenario": "Validate SWIPE_CARD_IND",
        "detailed_test_steps": "1. Query MEMBERS.",
        "expected_results": "Only Y/N.",
        "verification_sql": "SELECT * FROM MEMBERS;",
    },
]
CONTEXT_SLICE = {"candidate_tables": ["MEMBERS"]}


def test_clean_response_produces_scores_and_overall():
    def fake_llm(prompt):
        assert "MEMBERS" in prompt
        return json.dumps({
            "completeness": 0.9, "hallucination_prevention": 1.0,
            "schema_adherence": 1.0, "rationale": "Solid coverage.", "warnings": [],
        })

    score = run_llm_judge(SCENARIOS, CONTEXT_SLICE, "validate swipe card indicator", fake_llm)
    assert score is not None
    assert score.overall == round((0.9 + 1.0 + 1.0) / 3, 3)


def test_empty_scenario_list_returns_none_not_a_zero_score():
    def fake_llm(prompt):
        return json.dumps({"completeness": 0.0, "hallucination_prevention": 0.0, "schema_adherence": 0.0, "rationale": "", "warnings": []})

    score = run_llm_judge([], CONTEXT_SLICE, "req", fake_llm)
    assert score is None


def test_llm_backend_failure_is_swallowed_returns_none():
    def failing_llm(prompt):
        raise RuntimeError("simulated LLM backend failure")

    score = run_llm_judge(SCENARIOS, CONTEXT_SLICE, "req", failing_llm)
    assert score is None


def test_malformed_response_returns_none():
    def garbage_llm(prompt):
        return "not json at all"

    score = run_llm_judge(SCENARIOS, CONTEXT_SLICE, "req", garbage_llm)
    assert score is None


def test_out_of_range_scores_are_clamped_to_unit_interval():
    def out_of_range_llm(prompt):
        return json.dumps({
            "completeness": 1.5, "hallucination_prevention": -0.3,
            "schema_adherence": 0.5, "rationale": "r", "warnings": [],
        })

    score = run_llm_judge(SCENARIOS, CONTEXT_SLICE, "req", out_of_range_llm)
    assert score.completeness == 1.0
    assert score.hallucination_prevention == 0.0
    assert score.schema_adherence == 0.5


def test_markdown_fenced_response_is_extracted():
    def fake_llm(prompt):
        return (
            "```json\n"
            '{"completeness": 0.8, "hallucination_prevention": 0.9, '
            '"schema_adherence": 1.0, "rationale": "r", "warnings": ["minor issue"]}\n'
            "```"
        )

    score = run_llm_judge(SCENARIOS, CONTEXT_SLICE, "req", fake_llm)
    assert score is not None
    assert score.warnings == ["minor issue"]
