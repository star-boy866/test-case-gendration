"""
Semantic Cache — Phase 3.

Ties together:
- embeddings.py (HashingEmbedder) — turns prompt text into vectors.
- vector_index.py (FAISS or numpy fallback) — L2 nearest-neighbor search.
- bm25.py — the hybrid keyword-overlap rescue signal.
- cache_classification.py — the pure hit/partial_hit/miss decision.
- models/cache.py (SemanticCacheEntry) — source of truth for cached
  payloads; the vector index only ever holds vectors + this table's `id`.

Design choice, stated plainly: the vector index is rebuilt from SQL on
every lookup rather than persisted as a long-lived process-global index.
This is deliberate, not an oversight — lookups are always scoped to a
single (report_id, source_file_hash) pair first via the SQL WHERE clause,
so the candidate set per lookup is small (bounded by how many distinct
prompts have been cached for one report), and brute-force rebuild is cheap
at that scale. A persistent on-disk index (via FAISS_INDEX_PATH) is a
reasonable Phase 9/10 hardening step if cache volume grows, not a Phase 3
requirement.
"""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cache import SemanticCacheEntry
from app.services.bm25 import SimpleBM25
from app.services.cache_classification import classify_match
from app.services.embeddings import HashingEmbedder
from app.services.vector_index import get_vector_index

_default_embedder = HashingEmbedder(dim=settings.EMBEDDING_DIM)


def check_cache(
    db: Session,
    *,
    report_id: str,
    source_file_hash: str,
    prompt_text: str,
    embedder: Optional[HashingEmbedder] = None,
) -> dict:
    """
    Returns a dict:
      {
        "status": "hit" | "partial_hit" | "miss",
        "cached_entry": {...} | None,   # populated for hit/partial_hit
        "distance": float | None,
        "bm25_score": float | None,
        "bm25_rescued": bool,
        "explanation": str,
      }
    """
    embedder = embedder or _default_embedder

    entries = (
        db.query(SemanticCacheEntry)
        .filter(
            SemanticCacheEntry.report_id == report_id,
            SemanticCacheEntry.source_file_hash == source_file_hash,
        )
        .all()
    )

    if not entries:
        result = classify_match(
            [], [],
            hit_threshold=settings.CACHE_HIT_THRESHOLD,
            partial_threshold=settings.CACHE_PARTIAL_HIT_THRESHOLD,
        )
        return {
            "status": result.status,
            "cached_entry": None,
            "distance": None,
            "bm25_score": None,
            "bm25_rescued": False,
            "explanation": result.explanation,
        }

    entries_by_id = {e.id: e for e in entries}

    query_vec = embedder.embed(prompt_text)
    index = get_vector_index(embedder.dim)
    ids = [e.id for e in entries]
    vectors = embedder.embed_batch([e.prompt_text for e in entries])
    index.add(ids, vectors)

    # Rank the FULL candidate set (k = all entries) so distances and BM25
    # scores can be aligned over the same, complete candidate list — this
    # is what cache_classification.classify_match's contract requires.
    found_ids, distances = index.search(query_vec, k=len(entries))
    ordered_prompts = [entries_by_id[i].prompt_text for i in found_ids]
    bm25_scores = SimpleBM25(ordered_prompts).score(prompt_text)

    result = classify_match(
        distances, bm25_scores,
        hit_threshold=settings.CACHE_HIT_THRESHOLD,
        partial_threshold=settings.CACHE_PARTIAL_HIT_THRESHOLD,
    )

    cached_entry = None
    if result.best_index is not None and result.status in ("hit", "partial_hit"):
        matched = entries_by_id[found_ids[result.best_index]]
        cached_entry = {
            "id": matched.id,
            "prompt_text": matched.prompt_text,
            "cached_payload": json.loads(matched.cached_payload),
            "quality_score": matched.quality_score,
            "created_at": matched.created_at.isoformat() if matched.created_at else None,
        }

    return {
        "status": result.status,
        "cached_entry": cached_entry,
        "distance": result.best_distance,
        "bm25_score": result.best_bm25_score,
        "bm25_rescued": result.bm25_rescued,
        "explanation": result.explanation,
    }


def store_result(
    db: Session,
    *,
    report_id: str,
    source_file_hash: str,
    prompt_text: str,
    scenarios: list[dict],
    quality_score: float = 1.0,
) -> int:
    """Persist a successfully-produced set of test scenarios for future cache hits."""
    entry = SemanticCacheEntry(
        report_id=report_id,
        source_file_hash=source_file_hash,
        prompt_text=prompt_text,
        cached_payload=json.dumps(scenarios),
        quality_score=quality_score,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry.id


def invalidate_cache_for_report(db: Session, report_id: str) -> int:
    """
    Cache-busting: purge all cache entries for a report_id. Called from the
    ingestion API when a re-uploaded file changes the Knowledge Base (see
    knowledge_base.persist_parsed_document's `kb_invalidated_prior_version`
    flag) — closing the loop promised in Phase 1's docstring.
    """
    entries = db.query(SemanticCacheEntry).filter(SemanticCacheEntry.report_id == report_id).all()
    count = len(entries)
    for e in entries:
        db.delete(e)
    db.commit()
    return count
