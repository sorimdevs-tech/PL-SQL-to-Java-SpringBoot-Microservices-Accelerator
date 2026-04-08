"""Semantic-aware retriever for conversion examples."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from .vector_store import VectorStore, get_default_store

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or get_default_store()

    def retrieve(self, query: str, semantic_type: str = "", top_k: int = 3) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []

        requested_type = (semantic_type or "").upper().strip()
        search_k = max(top_k * 4, top_k, 5)
        scored = self.vector_store.search(query, top_k=search_k)
        filtered = [
            self._format_result(example, score)
            for example, score in scored
            if not requested_type or str(example.get("type", "")).upper() == requested_type
        ]

        if not filtered:
            filtered = [self._format_result(example, score) for example, score in scored]

        results: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        for item in filtered:
            key = f"{item.get('type')}::{item.get('input')}::{item.get('output')}"
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
            if len(results) >= top_k:
                break

        logger.debug("RAG retrieved %d examples for semantic_type=%s", len(results), requested_type or "ANY")
        return results

    def _format_result(self, example: Dict[str, Any], score: float) -> Dict[str, Any]:
        return {
            "input": example.get("input", ""),
            "type": example.get("type", ""),
            "output": example.get("output", ""),
            "score": score,
        }


_DEFAULT_RETRIEVER: Optional[Retriever] = None


def retrieve(query: str, semantic_type: str = "", top_k: int = 3) -> List[Dict[str, Any]]:
    global _DEFAULT_RETRIEVER
    if _DEFAULT_RETRIEVER is None:
        _DEFAULT_RETRIEVER = Retriever()
    return _DEFAULT_RETRIEVER.retrieve(query, semantic_type, top_k)
