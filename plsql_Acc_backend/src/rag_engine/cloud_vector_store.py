"""Cloud vector-store abstraction with local fallback persistence."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .embedder import FALLBACK_DIMENSIONS, get_embedding

logger = logging.getLogger(__name__)


class CloudVectorStore:
    """Provider-agnostic vector store for learned error-solution records."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = dict(config or {})
        self.provider = str(self.config.get("provider", "pinecone")).lower()
        self.enabled = bool(self.config.get("enabled", False))
        self.dimensions = int(self.config.get("dimensions", FALLBACK_DIMENSIONS) or FALLBACK_DIMENSIONS)
        self.namespace = str(self.config.get("namespace") or "plsql-modernization")
        self.index_name = str(self.config.get("index_name") or "error-solutions")
        self.collection_name = str(self.config.get("collection_name") or self.index_name)
        self.metric = str(self.config.get("metric") or "cosine")
        self.fallback_path = Path(self.config.get("fallback_path") or "./rag_data/error_solutions_fallback.json")
        self._records: Dict[str, Dict[str, Any]] = {}
        self._client: Any = None
        self._index: Any = None
        self.last_operation_status: Dict[str, Any] = {"provider": self.provider, "success": False, "mode": "fallback"}
        self._load_fallback_records()
        self._connect()

    def store_vectors(self, items: List[Dict[str, Any]]) -> List[str]:
        if not items:
            return []

        prepared = [self._prepare_item(item) for item in items if item and item.get("id")]
        if not prepared:
            return []

        if self._index is not None:
            try:
                if self.provider == "pinecone":
                    vectors = [
                        {
                            "id": item["id"],
                            "values": item["values"],
                            "metadata": item["metadata"],
                        }
                        for item in prepared
                    ]
                    self._index.upsert(vectors=vectors, namespace=self.namespace)
                    self.last_operation_status = {"provider": self.provider, "success": True, "mode": "cloud", "count": len(vectors)}
                elif self.provider == "qdrant":
                    from qdrant_client.models import PointStruct  # type: ignore

                    points = [
                        PointStruct(id=item["id"], vector=item["values"], payload=item["metadata"])
                        for item in prepared
                    ]
                    self._index.upsert(collection_name=self.collection_name, points=points)
                    self.last_operation_status = {"provider": self.provider, "success": True, "mode": "cloud", "count": len(points)}
            except Exception as exc:
                logger.warning("Cloud vector upsert failed; using local fallback. Reason: %s", exc)
                self.last_operation_status = {
                    "provider": self.provider,
                    "success": False,
                    "mode": "fallback",
                    "error": str(exc),
                }

        for item in prepared:
            self._records[item["id"]] = item
        self._persist_fallback_records()
        return [item["id"] for item in prepared]

    def search_vectors(
        self,
        query_text: str,
        top_k: int = 3,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not query_text:
            return []

        query_vector = get_embedding(query_text)
        metadata_filter = metadata_filter or {}

        if self._index is not None:
            try:
                if self.provider == "pinecone":
                    response = self._index.query(
                        vector=query_vector,
                        top_k=max(1, top_k),
                        include_metadata=True,
                        namespace=self.namespace,
                        filter=metadata_filter or None,
                    )
                    matches = getattr(response, "matches", None) or response.get("matches", [])
                    self.last_operation_status = {"provider": self.provider, "success": True, "mode": "cloud-query", "count": len(matches)}
                    return [
                        {
                            "id": getattr(match, "id", None) or match.get("id"),
                            "score": float(getattr(match, "score", 0.0) or match.get("score", 0.0)),
                            "metadata": getattr(match, "metadata", None) or match.get("metadata", {}),
                        }
                        for match in matches
                    ]
                if self.provider == "qdrant":
                    hits = self._index.search(
                        collection_name=self.collection_name,
                        query_vector=query_vector,
                        limit=max(1, top_k),
                    )
                    return [
                        {
                            "id": str(getattr(hit, "id", "")),
                            "score": float(getattr(hit, "score", 0.0)),
                            "metadata": getattr(hit, "payload", {}) or {},
                        }
                        for hit in hits
                        if self._matches_filter(getattr(hit, "payload", {}) or {}, metadata_filter)
                    ]
            except Exception as exc:
                logger.warning("Cloud vector query failed; using local fallback. Reason: %s", exc)
                self.last_operation_status = {
                    "provider": self.provider,
                    "success": False,
                    "mode": "fallback-query",
                    "error": str(exc),
                }

        scored: List[Dict[str, Any]] = []
        for item in self._records.values():
            if not self._matches_filter(item.get("metadata", {}), metadata_filter):
                continue
            score = self._cosine(query_vector, item.get("values") or [])
            scored.append({"id": item["id"], "score": score, "metadata": item.get("metadata", {})})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    def delete_vectors(self, ids: List[str]) -> None:
        ids = [item for item in (ids or []) if item]
        if not ids:
            return

        if self._index is not None:
            try:
                if self.provider == "pinecone":
                    self._index.delete(ids=ids, namespace=self.namespace)
                elif self.provider == "qdrant":
                    self._index.delete(collection_name=self.collection_name, points_selector=ids)
            except Exception as exc:
                logger.warning("Cloud vector delete failed; removing from fallback only. Reason: %s", exc)

        for item_id in ids:
            self._records.pop(item_id, None)
        self._persist_fallback_records()

    def has_vector(self, vector_id: str) -> bool:
        return vector_id in self._records

    def uses_cloud_backend(self) -> bool:
        return self.enabled and self._index is not None

    def _prepare_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        values = item.get("values")
        text = item.get("text") or ""
        if values is None:
            values = get_embedding(text)
        metadata = dict(item.get("metadata") or {})
        if text and "text" not in metadata:
            metadata["text"] = text
        return {
            "id": str(item["id"]),
            "values": list(values),
            "metadata": metadata,
        }

    def _connect(self) -> None:
        if not self.enabled:
            logger.info("Cloud vector DB disabled; using local fallback store at %s", self.fallback_path)
            return

        try:
            if self.provider == "pinecone":
                self._connect_pinecone()
            elif self.provider == "qdrant":
                self._connect_qdrant()
            else:
                logger.warning("Unknown vector DB provider '%s'; using local fallback", self.provider)
        except Exception as exc:
            logger.warning("Failed to initialize %s vector store; using local fallback. Reason: %s", self.provider, exc)
            self._client = None
            self._index = None

    def _connect_pinecone(self) -> None:
        api_key = self.config.get("api_key")
        if not api_key:
            logger.warning("Pinecone enabled but no API key configured; using local fallback")
            return

        try:
            from pinecone import Pinecone, ServerlessSpec  # type: ignore

            self._client = Pinecone(api_key=api_key)
            existing = {item.get("name") if isinstance(item, dict) else getattr(item, "name", None) for item in self._client.list_indexes()}
            if self.index_name not in existing:
                region = self.config.get("environment") or "us-east-1"
                self._client.create_index(
                    name=self.index_name,
                    dimension=self.dimensions,
                    metric=self.metric,
                    spec=ServerlessSpec(cloud="aws", region=region),
                )
            self._index = self._client.Index(self.index_name)
            try:
                stats = self._index.describe_index_stats()
                dimension = None
                if isinstance(stats, dict):
                    dimension = stats.get("dimension")
                else:
                    dimension = getattr(stats, "dimension", None)
                if dimension and int(dimension) != self.dimensions:
                    raise ValueError(
                        f"Pinecone index '{self.index_name}' dimension {dimension} does not match configured dimension {self.dimensions}"
                    )
            except Exception:
                raise
        except ImportError:
            logger.warning("pinecone package not installed; using local fallback")

    def _connect_qdrant(self) -> None:
        url = self.config.get("qdrant_url")
        if not url:
            logger.warning("Qdrant enabled but no URL configured; using local fallback")
            return

        try:
            from qdrant_client import QdrantClient  # type: ignore
            from qdrant_client.models import Distance, VectorParams  # type: ignore

            self._client = QdrantClient(url=url, api_key=self.config.get("qdrant_api_key"))
            collections = self._client.get_collections().collections
            existing = {item.name for item in collections}
            if self.collection_name not in existing:
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.dimensions, distance=Distance.COSINE),
                )
            self._index = self._client
        except ImportError:
            logger.warning("qdrant-client package not installed; using local fallback")

    def _load_fallback_records(self) -> None:
        if not self.fallback_path.exists():
            return
        try:
            payload = json.loads(self.fallback_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._records = {
                    str(key): value
                    for key, value in payload.items()
                    if isinstance(value, dict)
                }
        except Exception as exc:
            logger.warning("Failed to read fallback vector store %s: %s", self.fallback_path, exc)

    def _persist_fallback_records(self) -> None:
        try:
            self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
            self.fallback_path.write_text(json.dumps(self._records, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to persist fallback vector store %s: %s", self.fallback_path, exc)

    def _matches_filter(self, metadata: Dict[str, Any], metadata_filter: Dict[str, Any]) -> bool:
        for key, expected in (metadata_filter or {}).items():
            if metadata.get(key) != expected:
                return False
        return True

    def _cosine(self, left: List[float], right: List[float]) -> float:
        if not left or not right:
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = sum(value * value for value in left) ** 0.5 or 1.0
        right_norm = sum(value * value for value in right) ** 0.5 or 1.0
        return numerator / (left_norm * right_norm)

    def get_status(self) -> Dict[str, Any]:
        return dict(self.last_operation_status)
