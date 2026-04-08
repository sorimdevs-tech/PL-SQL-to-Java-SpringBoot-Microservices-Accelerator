"""Persistent vector store for PL/SQL to Java conversion examples."""

from __future__ import annotations

import json
import logging
import math
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .embedder import get_embedding, get_embeddings

logger = logging.getLogger(__name__)

try:
    import faiss  # type: ignore
except Exception:
    faiss = None


class VectorStore:
    """FAISS-backed vector index with a pure-Python fallback search path."""

    def __init__(
        self,
        data_path: Optional[Path] = None,
        index_path: Optional[Path] = None,
        metadata_path: Optional[Path] = None,
    ):
        project_root = Path(__file__).resolve().parents[2]
        self.data_path = data_path or project_root / "rag_data" / "examples.json"
        self.index_path = index_path or project_root / "rag_data" / "examples.faiss"
        self.metadata_path = metadata_path or project_root / "rag_data" / "examples_metadata.pkl"
        self.examples: List[Dict[str, Any]] = []
        self.embeddings: List[List[float]] = []
        self.index: Any = None

    def load_data(self) -> List[Dict[str, Any]]:
        with self.data_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.examples = [item for item in data if item.get("input") and item.get("output")]
        return self.examples

    def build_index(self) -> None:
        if not self.examples:
            self.load_data()
        texts = [self._example_text(example) for example in self.examples]
        self.embeddings = get_embeddings(texts)
        if not self.embeddings:
            self.index = None
            return

        if faiss is None:
            logger.warning("FAISS unavailable; vector store will use in-memory cosine search")
            self.index = None
            return

        import numpy as np

        matrix = np.array(self.embeddings, dtype="float32")
        self.index = faiss.IndexFlatIP(matrix.shape[1])
        self.index.add(matrix)

    def save_index(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        if faiss is not None and self.index is not None:
            faiss.write_index(self.index, str(self.index_path))
        with self.metadata_path.open("wb") as handle:
            pickle.dump({"examples": self.examples, "embeddings": self.embeddings}, handle)

    def load_index(self) -> bool:
        if not self.metadata_path.exists():
            return False
        with self.metadata_path.open("rb") as handle:
            payload = pickle.load(handle)
        self.examples = payload.get("examples", [])
        self.embeddings = payload.get("embeddings", [])
        if faiss is not None and self.index_path.exists():
            self.index = faiss.read_index(str(self.index_path))
        else:
            self.index = None
        return bool(self.examples and self.embeddings)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        if not self.examples or not self.embeddings:
            if not self.load_index():
                self.build_index()
                self.save_index()
        if not query or not self.examples:
            return []

        query_vector = get_embedding(query)
        if faiss is not None and self.index is not None:
            import numpy as np

            distances, indices = self.index.search(np.array([query_vector], dtype="float32"), max(1, top_k))
            return [
                (self.examples[int(index)], float(score))
                for index, score in zip(indices[0], distances[0])
                if int(index) >= 0
            ]

        scored = [
            (example, self._cosine(query_vector, embedding))
            for example, embedding in zip(self.examples, self.embeddings)
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    def _example_text(self, example: Dict[str, Any]) -> str:
        return f"{example.get('type', '')}\n{example.get('input', '')}\n{example.get('output', '')}"

    def _cosine(self, left: List[float], right: List[float]) -> float:
        if not left or not right:
            return 0.0
        total = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
        right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
        return total / (left_norm * right_norm)


_DEFAULT_STORE: Optional[VectorStore] = None


def get_default_store() -> VectorStore:
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = VectorStore()
    return _DEFAULT_STORE
