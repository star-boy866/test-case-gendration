"""
Semantic cache classification — Phase 3.

This is the PURE decision logic behind the Local Semantic Cache Layer,
deliberately separated from persistence (semantic_cache.py) so it can be
unit tested without a database or a vector index library installed.

Per the Master System Prompt:
  - L2 distance <= CACHE_HIT_THRESHOLD (default 0.15): Cache Hit
  - CACHE_HIT_THRESHOLD < distance <= CACHE_PARTIAL_HIT_THRESHOLD (0.30):
    Partial Cache Hit
  - distance > CACHE_PARTIAL_HIT_THRESHOLD: Cache Miss

Hybrid extension (this is my addition, not in the original spec, and is
clearly labeled as such): if the nearest neighbor's L2 distance alone would
classify as a Miss, but its BM25 keyword-overlap score is very high
relative to the best score in the candidate set, the result is "rescued"
to a Partial Cache Hit. The hashing-trick embedder in embeddings.py is a
coarse bag-of-words signal, not true semantic similarity — the BM25
rescue catches near-exact keyword matches that a coarse embedder might
place just outside the FAISS thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClassificationResult:
    status: str  # "hit" | "partial_hit" | "miss"
    best_index: int | None
    best_distance: float | None
    best_bm25_score: float | None
    bm25_rescued: bool
    explanation: str


def classify_match(
    distances: list[float],
    bm25_scores: list[float],
    *,
    hit_threshold: float,
    partial_threshold: float,
    bm25_rescue_ratio: float = 0.8,
    bm25_absolute_min: float = 2.0,
) -> ClassificationResult:
    """
    distances / bm25_scores must be parallel lists over the same candidate
    set (index i in one corresponds to index i in the other). Returns a
    Miss with no best_index if there are no candidates at all.

    bm25_absolute_min guards against the degenerate case of a single (or
    otherwise weak) candidate set where the best score trivially equals the
    max score regardless of how small it is in absolute terms — the rescue
    must represent genuine keyword overlap, not just "best of a weak set".
    """
    if not distances:
        return ClassificationResult(
            status="miss",
            best_index=None,
            best_distance=None,
            best_bm25_score=None,
            bm25_rescued=False,
            explanation="No prior cache entries exist for this report_id.",
        )

    best_index = min(range(len(distances)), key=lambda i: distances[i])
    best_distance = distances[best_index]
    best_bm25 = bm25_scores[best_index] if bm25_scores else 0.0
    max_bm25 = max(bm25_scores) if bm25_scores else 0.0

    if best_distance <= hit_threshold:
        return ClassificationResult(
            status="hit",
            best_index=best_index,
            best_distance=best_distance,
            best_bm25_score=best_bm25,
            bm25_rescued=False,
            explanation=(
                f"L2 distance {best_distance:.4f} <= hit threshold "
                f"{hit_threshold} — streaming cached result directly."
            ),
        )

    if best_distance <= partial_threshold:
        return ClassificationResult(
            status="partial_hit",
            best_index=best_index,
            best_distance=best_distance,
            best_bm25_score=best_bm25,
            bm25_rescued=False,
            explanation=(
                f"L2 distance {best_distance:.4f} is between hit threshold "
                f"{hit_threshold} and partial threshold {partial_threshold} "
                f"— using as a few-shot example, not a direct answer."
            ),
        )

    # Beyond the partial threshold on pure semantic distance — check the
    # BM25 hybrid rescue before declaring a miss. Requires BOTH relative
    # dominance within the candidate set AND an absolute floor, so a
    # single weak candidate can't trivially "rescue" itself.
    if (
        max_bm25 > 0
        and best_bm25 >= bm25_rescue_ratio * max_bm25
        and best_bm25 >= bm25_absolute_min
    ):
        return ClassificationResult(
            status="partial_hit",
            best_index=best_index,
            best_distance=best_distance,
            best_bm25_score=best_bm25,
            bm25_rescued=True,
            explanation=(
                f"L2 distance {best_distance:.4f} exceeds the partial "
                f"threshold {partial_threshold}, but BM25 keyword overlap "
                f"score {best_bm25:.3f} is within {bm25_rescue_ratio:.0%} of "
                f"the best keyword match in the candidate set — rescued to "
                f"partial_hit (hybrid signal, not part of the pure FAISS "
                f"L2 rule)."
            ),
        )

    return ClassificationResult(
        status="miss",
        best_index=best_index,
        best_distance=best_distance,
        best_bm25_score=best_bm25,
        bm25_rescued=False,
        explanation=(
            f"Nearest L2 distance {best_distance:.4f} exceeds the partial "
            f"threshold {partial_threshold} and no BM25 rescue applied — "
            f"routing to the full multi-agent generation loop."
        ),
    )
