from app.services.context_minimizer import _select_context

SAMPLE_KB = {
    "tables": [
        {"table_name": "MEMBERS", "description": "Unique member identifier"},
        {"table_name": "CLAIMS", "description": "Unique claim identifier"},
        {"table_name": "PROVIDERS", "description": "Provider info"},
    ],
    "columns": [
        {"table_name": "MEMBERS", "column_name": "MEMBER_ID", "data_type": "VARCHAR(20)", "key_type": "PK", "description": None},
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND", "data_type": "CHAR(1)", "key_type": None, "description": None},
        {"table_name": "CLAIMS", "column_name": "CLAIM_ID", "data_type": "VARCHAR(30)", "key_type": "PK", "description": None},
        {"table_name": "CLAIMS", "column_name": "MEMBER_ID", "data_type": "VARCHAR(20)", "key_type": "FK", "description": None},
        {"table_name": "PROVIDERS", "column_name": "PROVIDER_ID", "data_type": "VARCHAR(15)", "key_type": "PK", "description": None},
    ],
    "joins": [
        {"from_table": "CLAIMS", "from_column": "MEMBER_ID", "to_table": "MEMBERS", "to_column": "MEMBER_ID", "join_type": "INNER"},
    ],
    "valid_values": [
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND", "valid_value": "Y", "meaning": "Card issued"},
        {"table_name": "MEMBERS", "column_name": "SWIPE_CARD_IND", "valid_value": "N", "meaning": "Card not issued"},
    ],
    "business_rules": [
        {"rule_text": "SWIPE_CARD_IND must be Y or N, never null", "related_table": "MEMBERS", "related_column": "SWIPE_CARD_IND"},
    ],
}


def test_realistic_requirement_scopes_to_relevant_tables_only():
    # This is the exact example phrasing from the Master System Prompt's
    # own Excel Scenario Output Specification.
    result = _select_context(
        SAMPLE_KB, "RPT-Demo",
        "Validate Swipe Card Issuance tracking when indicator equals 'N'",
    )

    assert "MEMBERS" in result.directly_matched_tables
    assert "PROVIDERS" not in result.candidate_tables
    assert result.reduced_counts["tables"] < result.full_kb_counts["tables"]


def test_join_partner_is_pulled_in_via_one_hop_expansion():
    result = _select_context(SAMPLE_KB, "RPT-Demo", "swipe card indicator")
    assert "CLAIMS" in result.join_expanded_tables
    assert "CLAIMS" in result.candidate_tables


def test_unrelated_table_excluded_and_no_transitive_closure():
    result = _select_context(SAMPLE_KB, "RPT-Demo", "swipe card indicator")
    # PROVIDERS has no join to MEMBERS/CLAIMS, so it must never appear.
    assert "PROVIDERS" not in result.candidate_tables
    assert all(t["table_name"] != "PROVIDERS" for t in result.tables)


def test_no_keyword_match_fails_open_to_full_kb_with_warning():
    result = _select_context(
        {
            "tables": [{"table_name": "MEMBERS", "description": None}],
            "columns": [{"table_name": "MEMBERS", "column_name": "MEMBER_ID", "data_type": "VARCHAR(20)", "key_type": "PK", "description": None}],
            "joins": [], "valid_values": [], "business_rules": [],
        },
        "RPT-X", "something totally unrelated about zebras",
    )
    assert result.candidate_tables == ["MEMBERS"]
    assert len(result.warnings) == 1


def test_valid_value_meaning_text_triggers_a_direct_match():
    # "Card issued" / "Card not issued" meanings should match "card
    # issuance" even though the column name SWIPE_CARD_IND alone wouldn't
    # contain the word "issuance".
    result = _select_context(SAMPLE_KB, "RPT-Demo", "card issuance status")
    assert "MEMBERS" in result.directly_matched_tables


def test_reduction_ratio_is_computed_correctly():
    result = _select_context(SAMPLE_KB, "RPT-Demo", "swipe card indicator")
    assert result.reduction_ratio["tables"] == round(
        result.reduced_counts["tables"] / result.full_kb_counts["tables"], 3
    )
