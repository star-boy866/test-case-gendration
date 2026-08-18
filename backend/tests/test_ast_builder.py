from app.agents.schemas import ScenarioIntent
from app.agents.ast_builder import build_ast

CONTEXT_SLICE = {
    "candidate_tables": ["MEMBERS", "CLAIMS", "PROVIDERS", "LICENSE", "ADDRESS"],
    "columns": [
        {"table_name": "MEMBERS", "column_name": "MEMBER_ID"},
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND"},
        {"table_name": "CLAIMS", "column_name": "CLAIM_ID"},
        {"table_name": "CLAIMS", "column_name": "MEMBER_ID"},
        {"table_name": "CLAIMS", "column_name": "PROVIDER_ID"},
        {"table_name": "PROVIDERS", "column_name": "PROVIDER_ID"},
        {"table_name": "PROVIDERS", "column_name": "LICENSE_END_DATE"},  # ambiguous with LICENSE table
        {"table_name": "PROVIDERS", "column_name": "STATUS"},
        {"table_name": "LICENSE", "column_name": "PROVIDER_ID"},
        {"table_name": "LICENSE", "column_name": "LICENSE_END_DATE"},
        {"table_name": "LICENSE", "column_name": "STATUS"},
        {"table_name": "ADDRESS", "column_name": "MEMBER_ID"},
        {"table_name": "ADDRESS", "column_name": "CITY"},
    ],
    "joins": [
        {"from_table": "CLAIMS", "from_column": "MEMBER_ID", "to_table": "MEMBERS", "to_column": "MEMBER_ID", "join_type": "INNER"},
        {"from_table": "PROVIDERS", "from_column": "PROVIDER_ID", "to_table": "LICENSE", "to_column": "PROVIDER_ID", "join_type": "INNER"},
        {"from_table": "CLAIMS", "from_column": "PROVIDER_ID", "to_table": "PROVIDERS", "to_column": "PROVIDER_ID", "join_type": "LEFT"},
        {"from_table": "MEMBERS", "from_column": "MEMBER_ID", "to_table": "ADDRESS", "to_column": "MEMBER_ID", "join_type": "INNER"},
    ],
}

def test_1_valid_single_table_column():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="MEMBERS", target_columns=["MEMBER_ID"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid

def test_2_invalid_single_table_column():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="MEMBERS", target_columns=["INVALID_COL"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid
    assert "Unknown column" in str(ast.rejection_reasons)

def test_3_valid_joined_table_column():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS", joins_needed=["MEMBERS"], target_columns=["SWIPE_CARD_IND"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid
    assert "MEMBERS.SWIPE_CARD_IND" in ast.select

def test_4_invalid_joined_table_column():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS", joins_needed=["MEMBERS"], target_columns=["INVALID_COL"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid

def test_5_valid_qualified_alias():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS c", target_columns=["c.CLAIM_ID"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid
    assert ast.select == ["c.CLAIM_ID"]

def test_6_unknown_alias():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS c", target_columns=["x.CLAIM_ID"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid
    assert "Unknown alias" in str(ast.rejection_reasons)

def test_7_unknown_table():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="INVALID_TABLE", target_columns=["ID"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid
    assert "Unknown table" in str(ast.rejection_reasons)

def test_8_unknown_column():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS c", target_columns=["c.UNKNOWN_COL"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid
    assert "Unknown column" in str(ast.rejection_reasons)

def test_9_column_belongs_to_wrong_joined_table():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS c", joins_needed=["MEMBERS m"], target_columns=["c.SWIPE_CARD_IND"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid
    assert "Unknown column" in str(ast.rejection_reasons)

def test_10_valid_join_on_condition():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS", joins_needed=["MEMBERS"], target_columns=["CLAIM_ID"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid
    assert "CLAIMS.MEMBER_ID = MEMBERS.MEMBER_ID" in ast.joins[0]["on"] or "MEMBERS.MEMBER_ID = CLAIMS.MEMBER_ID" in ast.joins[0]["on"]

def test_11_invalid_join_on_table():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS", joins_needed=["LICENSE"], target_columns=["CLAIM_ID"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid
    assert "No verified join path exists" in str(ast.rejection_reasons)

def test_12_valid_joined_table_filter():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS c", joins_needed=["MEMBERS m"], target_columns=["c.CLAIM_ID"], filters=[{"column": "m.SWIPE_CARD_IND", "op": "=", "value": "'Y'"}])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid
    assert ast.where[0]["column"] == "m.SWIPE_CARD_IND"

def test_13_invalid_joined_table_filter():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS c", joins_needed=["MEMBERS m"], target_columns=["c.CLAIM_ID"], filters=[{"column": "m.INVALID_COL", "op": "=", "value": "'Y'"}])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid

def test_14_valid_group_by_joined_column():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS", joins_needed=["MEMBERS"], target_columns=["CLAIM_ID"], group_by=["SWIPE_CARD_IND"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid
    assert ast.group_by == ["MEMBERS.SWIPE_CARD_IND"]

def test_15_invalid_group_by_joined_column():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS", joins_needed=["MEMBERS"], target_columns=["CLAIM_ID"], group_by=["INVALID_COL"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid

def test_16_valid_order_by_joined_column():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS", joins_needed=["MEMBERS"], target_columns=["CLAIM_ID"], order_by=["SWIPE_CARD_IND"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid

def test_17_invalid_order_by_joined_column():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS", joins_needed=["MEMBERS"], target_columns=["CLAIM_ID"], order_by=["INVALID_COL"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid

def test_18_valid_having_joined_column():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS", joins_needed=["MEMBERS"], target_columns=["CLAIM_ID"], having=[{"column": "SWIPE_CARD_IND", "op": "=", "value": "1"}])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid
    assert ast.having[0]["column"] == "MEMBERS.SWIPE_CARD_IND"

def test_19_invalid_having_joined_column():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS", joins_needed=["MEMBERS"], target_columns=["CLAIM_ID"], having=[{"column": "INVALID_COL", "op": "=", "value": "1"}])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid

def test_20_ambiguous_unqualified_column():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="PROVIDERS p", joins_needed=["LICENSE l"], target_columns=["STATUS"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid
    assert "Ambiguous column" in str(ast.rejection_reasons)

def test_21_multiple_joins():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS c", joins_needed=["MEMBERS m", "PROVIDERS p"], target_columns=["c.CLAIM_ID", "m.SWIPE_CARD_IND", "p.STATUS"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid

def test_22_alias_collision():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="CLAIMS c", joins_needed=["MEMBERS c"], target_columns=["c.CLAIM_ID"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert not ast.is_valid
    assert "Alias collision" in str(ast.rejection_reasons)

def test_23_same_column_name_multiple_joined_tables_requires_alias():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="PROVIDERS p", joins_needed=["LICENSE l"], target_columns=["p.STATUS", "l.STATUS"])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid

def test_24_no_target_columns_is_rejected():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="MEMBERS", target_columns=[])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid is False

def test_25_disallowed_filter_operator_is_rejected():
    intent = ScenarioIntent(title="t", rationale="r", category="x", target_table="MEMBERS", target_columns=["MEMBER_ID"], filters=[{"column": "MEMBER_ID", "op": "DROP TABLE", "value": "x"}])
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid is False


# ==============================================================================
# CRITICAL NEGATIVE TEST MATRIX
# ==============================================================================

def test_critical_negative_test_matrix():
    # Base: PASS
    intent = ScenarioIntent(
        title="t", rationale="r", category="x",
        target_table="providers p",
        joins_needed=["license l"],
        target_columns=["p.provider_id", "l.license_end_date"]
    )
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid is True
    
    # alter l.license_end_date -> l.DOES_NOT_EXIST
    intent.target_columns = ["p.provider_id", "l.DOES_NOT_EXIST"]
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid is False
    assert "Unknown column" in str(ast.rejection_reasons)
    
    # alter l.license_end_date -> p.DOES_NOT_EXIST
    intent.target_columns = ["p.DOES_NOT_EXIST", "l.license_end_date"]
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid is False
    assert "Unknown column" in str(ast.rejection_reasons)
    
    # un-aliased license_end_date (ambiguous)
    intent.target_columns = ["p.provider_id", "license_end_date"]
    ast = build_ast(intent, CONTEXT_SLICE)
    assert ast.is_valid is False
    assert "Ambiguous column" in str(ast.rejection_reasons)
