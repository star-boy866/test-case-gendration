from app.services.bm25 import SimpleBM25


def test_ranks_relevant_document_highest():
    corpus = [
        "MEMBERS table with SWIPE_CARD_IND column tracks card issuance",
        "CLAIMS table has CLAIM_ID and MEMBER_ID foreign key",
        "PROVIDERS table with PROVIDER_ID unrelated to swipe cards",
    ]
    bm25 = SimpleBM25(corpus)
    scores = bm25.score("swipe card indicator")

    assert scores[0] > scores[1]
    assert scores[0] > scores[2]


def test_underscored_query_matches_prose_document():
    # Regression guard for the tokenizer fix: querying with the raw
    # SNAKE_CASE column name should still find the document that describes
    # it in prose, since both get split into the same word-level tokens.
    corpus = [
        "MEMBERS table with SWIPE_CARD_IND column tracks card issuance",
        "CLAIMS table has CLAIM_ID and MEMBER_ID foreign key",
    ]
    bm25 = SimpleBM25(corpus)
    scores = bm25.score("SWIPE_CARD_IND")
    assert scores[0] > 0
    assert scores[0] > scores[1]


def test_empty_corpus_returns_empty_scores():
    bm25 = SimpleBM25([])
    assert bm25.score("anything") == []


def test_no_query_term_matches_yields_zero_scores():
    bm25 = SimpleBM25(["completely unrelated content here"])
    scores = bm25.score("zzz_no_match_at_all")
    assert scores == [0.0]
