import pytest

from app.agents.schemas import ScenarioIntent, ValidatedAST
from app.agents.ast_builder import build_ast
from app.services.sql_render import render_sql

CONTEXT_SLICE = {
    "candidate_tables": ["MEMBERS"],
    "columns": [
        {"table_name": "MEMBERS", "column_name": "MEMBER_ID"},
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND"},
    ],
    "joins": [],
}


def test_renders_select_from_where():
    intent = ScenarioIntent(
        title="t", rationale="r", category="valid_value_check",
        target_table="MEMBERS", target_columns=["MEMBER_ID", "SWIPE_CARD_IND"],
        filters=[{"column": "SWIPE_CARD_IND", "op": "NOT IN", "value": "('Y','N')"}],
    )
    ast = build_ast(intent, CONTEXT_SLICE)
    sql = render_sql(ast)

    assert "SELECT MEMBERS.MEMBER_ID, MEMBERS.SWIPE_CARD_IND" in sql
    assert "FROM MEMBERS" in sql
    assert "WHERE MEMBERS.SWIPE_CARD_IND NOT IN ('Y','N')" in sql
    assert sql.strip().endswith(";")


def test_renders_is_null_without_value():
    ast = ValidatedAST(
        is_valid=True, select=["MEMBERS.MEMBER_ID"], from_table="MEMBERS",
        where=[{"column": "MEMBERS.MEMBER_ID", "op": "IS NULL", "value": ""}],
    )
    sql = render_sql(ast)
    assert "WHERE MEMBERS.MEMBER_ID IS NULL" in sql


def test_refuses_to_render_invalid_ast():
    bad_ast = ValidatedAST(is_valid=False, rejection_reasons=["bad"])
    with pytest.raises(ValueError):
        render_sql(bad_ast)


def test_renders_joins():
    ast = ValidatedAST(
        is_valid=True, select=["MEMBER_ID"], from_table="MEMBERS",
        joins=[{"table": "CLAIMS", "on": "CLAIMS.MEMBER_ID = MEMBERS.MEMBER_ID", "join_type": "INNER"}],
    )
    sql = render_sql(ast)
    assert "INNER JOIN CLAIMS ON CLAIMS.MEMBER_ID = MEMBERS.MEMBER_ID" in sql
