import numpy as np

from app.services.embeddings import HashingEmbedder, tokenize


def test_tokenize_splits_on_underscore():
    # This is the specific bug found and fixed during Phase 3 development:
    # SNAKE_CASE column names must split into separate tokens so they can
    # match natural-language phrasing like "swipe card indicator".
    assert tokenize("SWIPE_CARD_IND") == ["swipe", "card", "ind"]


def test_embed_is_deterministic():
    e = HashingEmbedder(dim=64)
    v1 = e.embed("validate swipe card indicator is Y or N")
    v2 = e.embed("validate swipe card indicator is Y or N")
    assert np.allclose(v1, v2)


def test_embed_is_normalized():
    e = HashingEmbedder(dim=64)
    v = e.embed("some text here")
    assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-5


def test_similar_text_closer_than_unrelated_text():
    e = HashingEmbedder(dim=64)
    v1 = e.embed("validate swipe card indicator is Y or N")
    v2 = e.embed("validate swipe card indicator is Y or N")
    v3 = e.embed("completely unrelated text about golf scores")

    dist_same = np.linalg.norm(v1 - v2)
    dist_diff = np.linalg.norm(v1 - v3)
    assert dist_same < dist_diff


def test_embed_batch_matches_individual_embeds():
    e = HashingEmbedder(dim=32)
    texts = ["alpha beta", "gamma delta"]
    batch = e.embed_batch(texts)
    individual = np.vstack([e.embed(t) for t in texts])
    assert np.allclose(batch, individual)


def test_embed_batch_empty_list():
    e = HashingEmbedder(dim=32)
    batch = e.embed_batch([])
    assert batch.shape == (0, 32)
