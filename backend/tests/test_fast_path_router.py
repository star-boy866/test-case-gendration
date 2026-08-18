from app.services.fast_path_router import try_fast_path


def test_date_format_requirement_matches():
    r = try_fast_path("Please validate the date formatting on this report")
    assert r is not None
    assert r.matched_rule == "date_timestamp_format"


def test_pagination_requirement_matches():
    r = try_fast_path("Check pagination behaves correctly across pages")
    assert r is not None
    assert r.matched_rule == "pagination"


def test_layout_header_requirement_matches():
    r = try_fast_path("Ensure the column headers match the RDD layout")
    assert r is not None
    assert r.matched_rule == "layout_header"


def test_non_standard_requirement_falls_through():
    r = try_fast_path("Validate swipe card indicator business logic")
    assert r is None


def test_empty_requirement_falls_through():
    assert try_fast_path("") is None
    assert try_fast_path(None) is None
