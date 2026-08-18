"""
BM25 keyword scoring — Phase 3.

A minimal, dependency-free BM25Okapi implementation. The Master System
Prompt's open-source stack calls for "FAISS + BM25" generically — BM25
itself is a well-defined, simple-enough algorithm that implementing it
directly avoids adding another external dependency for something this
small. Swapping in the `rank_bm25` package (identical scoring formula) is
a one-file change if preferred; nothing else in this codebase depends on
the implementation detail.
"""

from __future__ import annotations

import math
from collections import Counter

from app.services.embeddings import tokenize


class SimpleBM25:
    """BM25Okapi scoring (k1=1.5, b=0.75 — standard defaults) over a fixed corpus."""

    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.tokenized: list[list[str]] = [tokenize(doc) for doc in corpus]
        self.doc_lens: list[int] = [len(d) for d in self.tokenized]
        self.n_docs = len(corpus)
        self.avgdl = (sum(self.doc_lens) / self.n_docs) if self.n_docs else 0.0
        self.term_freqs: list[Counter] = [Counter(d) for d in self.tokenized]

        doc_freq: Counter = Counter()
        for doc_tokens in self.tokenized:
            for term in set(doc_tokens):
                doc_freq[term] += 1
        self.idf: dict[str, float] = {
            term: math.log(1 + (self.n_docs - freq + 0.5) / (freq + 0.5))
            for term, freq in doc_freq.items()
        }

    def score(self, query: str) -> list[float]:
        """Returns one BM25 score per corpus document, in corpus order."""
        if self.n_docs == 0:
            return []
        q_tokens = tokenize(query)
        scores = []
        for i in range(self.n_docs):
            dl = self.doc_lens[i]
            freqs = self.term_freqs[i]
            s = 0.0
            for term in q_tokens:
                f = freqs.get(term)
                if not f:
                    continue
                idf = self.idf.get(term, 0.0)
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                s += idf * (f * (self.k1 + 1)) / (denom or 1)
            scores.append(s)
        return scores
