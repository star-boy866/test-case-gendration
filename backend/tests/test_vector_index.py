import numpy as np
import pytest

from app.services.vector_index import NumpyFlatL2Index, get_vector_index


def test_add_and_search_returns_nearest_first():
    idx = NumpyFlatL2Index(dim=8)
    idx.add(
        [1, 2, 3],
        np.array(
            [
                [1, 0, 0, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0, 0, 0],
                [0, 0, 1, 0, 0, 0, 0, 0],
            ],
            dtype=np.float32,
        ),
    )
    ids, dists = idx.search(np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32), k=2)
    assert ids[0] == 1
    assert dists[0] < 1e-6
    assert len(ids) == 2


def test_remove_excludes_id_from_future_searches():
    idx = NumpyFlatL2Index(dim=8)
    idx.add(
        [1, 2, 3],
        np.array(
            [
                [1, 0, 0, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0, 0, 0],
                [0, 0, 1, 0, 0, 0, 0, 0],
            ],
            dtype=np.float32,
        ),
    )
    idx.remove([1])
    ids, _ = idx.search(np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32), k=2)
    assert 1 not in ids
    assert len(idx) == 2


def test_add_mismatched_lengths_raises():
    idx = NumpyFlatL2Index(dim=4)
    with pytest.raises(ValueError):
        idx.add([1, 2], np.zeros((1, 4), dtype=np.float32))


def test_search_on_empty_index_returns_empty():
    idx = NumpyFlatL2Index(dim=4)
    ids, dists = idx.search(np.zeros(4, dtype=np.float32), k=3)
    assert ids == []
    assert dists == []


def test_factory_falls_back_to_numpy_when_faiss_unavailable():
    # This sandbox has no faiss installed, so the factory must fall back.
    # In an environment WITH faiss installed, this test would need to be
    # skipped or adjusted — see the docstring in vector_index.py.
    backend = get_vector_index(dim=8)
    assert isinstance(backend, NumpyFlatL2Index)
