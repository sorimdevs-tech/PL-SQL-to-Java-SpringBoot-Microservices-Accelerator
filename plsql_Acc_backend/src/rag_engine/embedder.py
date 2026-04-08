"""Embedding utilities for the conversion RAG engine."""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Iterable, List

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
FALLBACK_DIMENSIONS = 384
_MODEL = None
_MODEL_LOAD_ATTEMPTED = False


def _load_model():
    global _MODEL, _MODEL_LOAD_ATTEMPTED
    if _MODEL_LOAD_ATTEMPTED:
        return _MODEL
    _MODEL_LOAD_ATTEMPTED = True
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        _MODEL = SentenceTransformer(MODEL_NAME)
        logger.info("Loaded sentence-transformers model: %s", MODEL_NAME)
    except Exception as exc:
        logger.warning(
            "sentence-transformers model unavailable; using hashing embeddings. Reason: %s",
            exc,
        )
        _MODEL = None
    return _MODEL


def _hash_embedding(text: str, dimensions: int = FALLBACK_DIMENSIONS) -> List[float]:
    """Deterministic fallback embedding for environments without model deps."""
    vector = [0.0] * dimensions
    tokens = (text or "").lower().replace("_", " ").split()
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = -1.0 if digest[4] % 2 else 1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def get_embedding(text: str) -> List[float]:
    """Return an embedding vector for a single text input."""
    model = _load_model()
    if model is not None:
        return model.encode(text or "", normalize_embeddings=True).tolist()
    return _hash_embedding(text or "")


def get_embeddings(list_of_texts: Iterable[str]) -> List[List[float]]:
    """Return embedding vectors for multiple text inputs."""
    texts = list(list_of_texts or [])
    if not texts:
        return []
    model = _load_model()
    if model is not None:
        return model.encode(texts, normalize_embeddings=True).tolist()
    return [_hash_embedding(text) for text in texts]
