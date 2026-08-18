import pytest

from app.agents.schemas import ScenarioIntent, ValidatedAST
from app.agents.generator_agent import generate_scenario_content, GeneratorParseError

INTENT = ScenarioIntent(
    title="Check indicator", rationale="must be Y/N", category="valid_value_check",
    target_table="MEMBERS", target_columns=["SWIPE_CARD_IND"],
)
AST = ValidatedAST(
    is_valid=True, select=["SWIPE_CARD_IND"], from_table="MEMBERS",
    where=[{"column": "SWIPE_CARD_IND", "op": "NOT IN", "value": "('Y','N')"}],
)


def test_clean_generation():
    def fake_llm(prompt):
        assert "MEMBERS" in prompt
        assert "SWIPE_CARD_IND" in prompt
        return (
            '{"test_scenario": "Validate SWIPE_CARD_IND values", '
            '"detailed_test_steps": "1. Query MEMBERS.", '
            '"expected_results": "Only Y or N present."}'
        )

    result = generate_scenario_content(INTENT, AST, fake_llm)
    assert result["test_scenario"] == "Validate SWIPE_CARD_IND values"


def test_refuses_invalid_ast():
    bad_ast = ValidatedAST(is_valid=False, rejection_reasons=["bad"])
    with pytest.raises(ValueError):
        generate_scenario_content(INTENT, bad_ast, lambda p: "{}")


def test_missing_required_field_raises_clean_error():
    def fake_llm(prompt):
        return '{"test_scenario": "t"}'

    with pytest.raises(GeneratorParseError):
        generate_scenario_content(INTENT, AST, fake_llm)


def test_markdown_fenced_response_is_extracted():
    def fake_llm(prompt):
        return (
            "```json\n"
            '{"test_scenario": "t", "detailed_test_steps": "s", "expected_results": "e"}\n'
            "```"
        )

    result = generate_scenario_content(INTENT, AST, fake_llm)
    assert result["test_scenario"] == "t"
