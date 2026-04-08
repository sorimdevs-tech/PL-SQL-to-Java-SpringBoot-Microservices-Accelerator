"""Core RAG service for enriching logic-tree SQL nodes."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .retriever import Retriever
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self, vector_store: Optional[VectorStore] = None, top_k: int = 3):
        self.vector_store = vector_store or VectorStore()
        self.retriever = Retriever(self.vector_store)
        self.top_k = top_k
        self.initialized = False

    def initialize_rag(self) -> None:
        if self.initialized:
            return
        if not self.vector_store.load_index():
            self.vector_store.load_data()
            self.vector_store.build_index()
            self.vector_store.save_index()
        self.initialized = True
        logger.info("RAG initialized with %d conversion examples", len(self.vector_store.examples))

    def get_relevant_examples(self, sql_node: Any, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        self.initialize_rag()
        query = self._get_attr(sql_node, "query") or self._get_metadata(sql_node).get("query") or self._get_metadata(sql_node).get("sql")
        semantic_type = self._get_attr(sql_node, "semantic_type") or self._get_metadata(sql_node).get("semantic_type", "")
        if not query:
            return []
        return self.retriever.retrieve(str(query), str(semantic_type), top_k or self.top_k)

    def _get_metadata(self, sql_node: Any) -> Dict[str, Any]:
        if isinstance(sql_node, dict):
            return sql_node.get("metadata") or {}
        return getattr(sql_node, "metadata", {}) or {}

    def _get_attr(self, sql_node: Any, name: str) -> Any:
        if isinstance(sql_node, dict):
            return sql_node.get(name)
        return getattr(sql_node, name, None)


_DEFAULT_RAG_SERVICE: Optional[RAGService] = None


def initialize_rag(top_k: int = 3) -> RAGService:
    global _DEFAULT_RAG_SERVICE
    if _DEFAULT_RAG_SERVICE is None:
        _DEFAULT_RAG_SERVICE = RAGService(top_k=top_k)
    _DEFAULT_RAG_SERVICE.initialize_rag()
    return _DEFAULT_RAG_SERVICE


def get_relevant_examples(sql_node: Any, top_k: int = 3) -> List[Dict[str, Any]]:
    service = initialize_rag(top_k=top_k)
    return service.get_relevant_examples(sql_node, top_k=top_k)
