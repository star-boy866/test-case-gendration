"""
Vector index abstraction — Phase 3.

Per Technology Policy A, `faiss-cpu` is the intended production backend
(listed in requirements.txt) and is used automatically if it's installed.
But a working system shouldn't hard-fail just because a native wheel
didn't build in some environment, and this sandbox has no network access
to install it — so NumpyFlatL2Index is a pure-Python/numpy brute-force
fallback with the exact same interface. Since semantic cache lookups are
always scoped to a single report_id first (via a SQL WHERE clause — see
semantic_cache.py), the candidate set per lookup is small in practice, so
brute-force L2 is not a real performance concern at this data scale.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class VectorIndexBackend(Protocol):
    def add(self, ids: list[int], vectors: np.ndarray) -> None: ...
    def search(self, query: np.ndarray, k: int) -> tuple[list[int], list[float]]: ...
    def remove(self, ids: list[int]) -> None: ...


class NumpyFlatL2Index:
    """Brute-force L2 nearest-neighbor search. Always available, zero deps."""

    def __init__(self, dim: int):
        self.dim = dim
        self._ids: list[int] = []
        self._vectors: np.ndarray = np.zeros((0, dim), dtype=np.float32)

    def add(self, ids: list[int], vectors: np.ndarray) -> None:
        if len(ids) != vectors.shape[0]:
            raise ValueError("ids and vectors must have the same length")
        self._ids.extend(ids)
        self._vectors = np.vstack([self._vectors, vectors.astype(np.float32)])

    def search(self, query: np.ndarray, k: int) -> tuple[list[int], list[float]]:
        if len(self._ids) == 0:
            return [], []
        diffs = self._vectors - query.reshape(1, -1)
        dists = np.linalg.norm(diffs, axis=1)
        order = np.argsort(dists)[:k]
        return [self._ids[i] for i in order], [float(dists[i]) for i in order]

    def remove(self, ids: list[int]) -> None:
        remove_set = set(ids)
        keep_mask = [i for i, _id in enumerate(self._ids) if _id not in remove_set]
        self._ids = [self._ids[i] for i in keep_mask]
        self._vectors = self._vectors[keep_mask] if keep_mask else np.zeros((0, self.dim), dtype=np.float32)

    def __len__(self) -> int:
        return len(self._ids)


class FaissFlatL2Index:
    """Thin wrapper around faiss.IndexIDMap(faiss.IndexFlatL2(dim)). Used automatically if faiss is installed."""

    def __init__(self, dim: int):
        import faiss  # deferred import — only required if this class is instantiated

        self.dim = dim
        self._index = faiss.IndexIDMap(faiss.IndexFlatL2(dim))

    def add(self, ids: list[int], vectors: np.ndarray) -> None:
        import numpy as _np

        self._index.add_with_ids(vectors.astype("float32"), _np.array(ids, dtype="int64"))

    def search(self, query: np.ndarray, k: int) -> tuple[list[int], list[float]]:
        distances, ids = self._index.search(query.reshape(1, -1).astype("float32"), k)
        pairs = [(int(i), float(d)) for i, d in zip(ids[0], distances[0]) if i != -1]
        found_ids = [p[0] for p in pairs]
        found_dists = [p[1] for p in pairs]
        return found_ids, found_dists

    def remove(self, ids: list[int]) -> None:
        import numpy as _np

        self._index.remove_ids(_np.array(ids, dtype="int64"))


def get_vector_index(dim: int) -> VectorIndexBackend:
    """Factory: prefer FAISS if installed, otherwise fall back to numpy brute-force."""
    try:
        return FaissFlatL2Index(dim)
    except ImportError:
        return NumpyFlatL2Index(dim)
