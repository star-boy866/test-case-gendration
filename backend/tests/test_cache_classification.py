from app.services.cache_classification import classify_match


def test_hit_when_distance_within_hit_threshold():
    r = classify_match([0.10, 0.5], [3.0, 0.1], hit_threshold=0.15, partial_threshold=0.30)
    assert r.status == "hit"


def test_partial_hit_on_pure_distance():
    r = classify_match([0.20, 0.5], [3.0, 0.1], hit_threshold=0.15, partial_threshold=0.30)
    assert r.status == "partial_hit"
    assert r.bm25_rescued is False


def test_miss_when_distance_and_bm25_both_weak():
    r = classify_match([0.50], [0.5], hit_threshold=0.15, partial_threshold=0.30)
    assert r.status == "miss"


def test_bm25_rescues_a_miss_to_partial_hit():
    r = classify_match([0.45, 0.9], [5.0, 0.1], hit_threshold=0.15, partial_threshold=0.30)
    assert r.status == "partial_hit"
    assert r.bm25_rescued is True


def test_weak_bm25_does_not_rescue_even_if_relatively_best():
    # Single weak candidate: best_bm25 trivially equals max_bm25, but the
    # absolute floor (bm25_absolute_min) must still block the rescue.
    r = classify_match([0.50], [0.3], hit_threshold=0.15, partial_threshold=0.30)
    assert r.status == "miss"
    assert r.bm25_rescued is False


def test_empty_candidate_set_is_a_miss_with_no_best_index():
    r = classify_match([], [], hit_threshold=0.15, partial_threshold=0.30)
    assert r.status == "miss"
    assert r.best_index is None
