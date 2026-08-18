"""
Embedding layer — Phase 3.

Technology Policy A requires free, open-source, self-hostable technologies
with no paid APIs and no mandatory downloads. A "real" sentence-transformer
or Ollama embedding model needs either a network download or a running
Ollama daemon — neither of which can be assumed to exist at install time.

HashingEmbedder is the zero-dependency default: a classic feature-hashing
bag-of-words embedder (SHA-256-based, so it's deterministic across
processes/machines — unlike Python's built-in hash()). It requires no
model weights and no network access, so it always works out of the box.

Swapping in a richer embedder (e.g. Ollama's `nomic-embed-text` via
OLLAMA_BASE_URL, already defined in core/config.py) is a drop-in
replacement: implement `.embed(text) -> np.ndarray` and `.dim`, nothing
else in this codebase needs to change.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    """
    Lowercase, alphanumeric-only tokenization. Underscores are treated as
    delimiters (not part of a token) specifically because LDM/RDD column
    names are typically SNAKE_CASE (e.g. SWIPE_CARD_IND) while natural
    language requirements phrase the same concept as separate words
    ("swipe card indicator"). Without splitting on underscore, those two
    forms share zero tokens and schema-linking/BM25 matching silently
    fails on exactly the realistic case this system exists to handle.
    """
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class HashingEmbedder:
    """Deterministic bag-of-words embedder using the hashing trick."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for tok in tokenize(text):
            digest = hashlib.sha256(tok.encode("utf-8")).hexdigest()
            h = int(digest, 16)
            idx = h % self.dim
            sign = 1.0 if (h // self.dim) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return vec

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.vstack([self.embed(t) for t in texts])
