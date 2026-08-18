"""
Semantic cache ORM model — Phase 3.

Stores the full cached test-scenario payload, not just a pointer. The
in-memory vector index (FAISS or numpy fallback, see vector_index.py) only
ever holds vectors + this table's integer `id` as the vector id — it is
rebuilt from these rows per lookup rather than persisted separately, so
there is exactly one source of truth for cache contents.

Scoped to (report_id, source_file_hash): a lookup only ever compares
against entries sharing both. This means entries for a report_id
automatically stop being matched the moment its Knowledge Base changes
(new file hash), even before `invalidate_cache_for_report` physically
deletes them — belt and suspenders with the Phase 1 cache-busting rule.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime, Float

from app.db.session import Base


class SemanticCacheEntry(Base):
    __tablename__ = "semantic_cache_entries"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String, nullable=False, index=True)
    source_file_hash = Column(String, nullable=False, index=True)
    prompt_text = Column(Text, nullable=False)
    cached_payload = Column(Text, nullable=False)  # JSON-encoded list of test scenario dicts
    quality_score = Column(Float, nullable=True)  # from Critic/Judge in Phase 5/10; fast-path entries default to 1.0
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
