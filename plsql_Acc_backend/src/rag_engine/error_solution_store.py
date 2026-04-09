"""Store and retrieve learned build-error solutions."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.sql_normalizer import SQLNormalizer
from .cloud_vector_store import CloudVectorStore

logger = logging.getLogger(__name__)


class ErrorSolutionStore:
    """Persistence and retrieval layer for learned error-solution pairs."""

    def __init__(
        self,
        vector_store: Optional[CloudVectorStore] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.config = dict(config or {})
        self.vector_store = vector_store or CloudVectorStore(self.config)
        fallback_path = Path(self.config.get("fallback_path") or "./rag_data/error_solutions_fallback.json")
        self.registry_path = fallback_path.with_name("error_solution_registry.json")
        self.sql_normalizer = SQLNormalizer()
        self.registry: Dict[str, Dict[str, Any]] = {}
        self._load_registry()

    def store_error_solution(
        self,
        error_message: str,
        sql_context: str,
        solution: Dict[str, Any],
        error_type: str = "compilation",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        fingerprint = self.generate_fingerprint(error_message, sql_context, error_type)
        if fingerprint in self.registry or self.vector_store.has_vector(fingerprint):
            return {"stored": False, "fingerprint": fingerprint, "reason": "duplicate"}

        metadata = dict(metadata or {})
        sql_pattern = metadata.get("sql_pattern") or ",".join(self.sql_normalizer.extract_key_patterns(sql_context))
        record = {
            "fingerprint": fingerprint,
            "error_message": error_message,
            "error_type": error_type,
            "sql_pattern": sql_pattern,
            "solution_summary": solution.get("summary", ""),
            "solution_steps": solution.get("steps", []),
            "changed_files": solution.get("changed_files", []),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **metadata,
        }
        text = self._build_search_text(error_message, sql_context, record)
        self.vector_store.store_vectors(
            [
                {
                    "id": fingerprint,
                    "text": text,
                    "metadata": record,
                }
            ]
        )
        self.registry[fingerprint] = record
        self._persist_registry()
        return {
            "stored": True,
            "fingerprint": fingerprint,
            "vector_status": self.vector_store.get_status(),
        }

    def retrieve_similar_errors(
        self,
        error_message: str,
        sql_context: str = "",
        top_k: int = 3,
        error_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        filter_payload = {"error_type": error_type} if error_type else None
        query_text = self._build_search_text(
            error_message,
            sql_context,
            {"sql_pattern": ",".join(self.sql_normalizer.extract_key_patterns(sql_context))},
        )
        matches = self.vector_store.search_vectors(query_text, top_k=top_k, metadata_filter=filter_payload)
        results: List[Dict[str, Any]] = []
        for match in matches:
            metadata = dict(match.get("metadata") or {})
            metadata["score"] = match.get("score", 0.0)
            results.append(metadata)
        return results

    def generate_fingerprint(self, error_message: str, sql_context: str, error_type: str = "compilation") -> str:
        normalized_sql = self.sql_normalizer.normalize_sql(sql_context)
        normalized_error = " ".join((error_message or "").strip().lower().split())
        payload = f"{error_type}|{normalized_error}|{normalized_sql}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def deduplicate(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique: List[Dict[str, Any]] = []
        seen = set()
        for record in records or []:
            fingerprint = record.get("fingerprint")
            if not fingerprint or fingerprint in seen:
                continue
            seen.add(fingerprint)
            unique.append(record)
        return unique

    def _build_search_text(self, error_message: str, sql_context: str, metadata: Dict[str, Any]) -> str:
        sql_pattern = metadata.get("sql_pattern", "")
        normalized_sql = self.sql_normalizer.normalize_sql(sql_context)
        return "\n".join(
            part for part in [
                error_message or "",
                normalized_sql,
                str(sql_pattern or ""),
                str(metadata.get("category", "")),
                str(metadata.get("code", "")),
            ]
            if part
        )

    def _load_registry(self) -> None:
        if not self.registry_path.exists():
            return
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self.registry = {
                    str(key): value
                    for key, value in payload.items()
                    if isinstance(value, dict)
                }
        except Exception as exc:
            logger.warning("Failed to read error solution registry %s: %s", self.registry_path, exc)

    def _persist_registry(self) -> None:
        try:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            self.registry_path.write_text(json.dumps(self.registry, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to persist error solution registry %s: %s", self.registry_path, exc)
