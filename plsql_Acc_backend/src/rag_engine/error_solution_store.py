"""Store and retrieve learned build-error solutions."""

from __future__ import annotations

import hashlib
import json
import logging
import re
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
        self._dedup_index: Dict[str, str] = {}
        self._load_registry()

    def store_error_solution(
        self,
        error_message: str,
        sql_context: str,
        solution: Dict[str, Any],
        error_type: str = "compilation",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata = dict(metadata or {})
        fingerprint = self.generate_fingerprint(error_message, sql_context, error_type, metadata)
        dedup_key = self.generate_dedup_key(error_message, error_type, metadata)
        existing_fingerprint = self._dedup_index.get(dedup_key)
        use_local_duplicate_guard = not self.vector_store.uses_cloud_backend()
        if use_local_duplicate_guard and (
            fingerprint in self.registry or self.vector_store.has_vector(fingerprint) or existing_fingerprint
        ):
            return {
                "stored": False,
                "fingerprint": existing_fingerprint or fingerprint,
                "reason": "duplicate",
                "vector_status": {
                    **self.vector_store.get_status(),
                    "mode": "duplicate",
                },
            }

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
        self._dedup_index[dedup_key] = fingerprint
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
        seen_keys = set()
        for match in matches:
            metadata = dict(match.get("metadata") or {})
            dedup_key = self.generate_dedup_key(
                str(metadata.get("error_message") or error_message),
                str(metadata.get("error_type") or error_type or "compilation"),
                metadata,
            )
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            metadata["score"] = match.get("score", 0.0)
            results.append(metadata)
        return results

    def generate_fingerprint(
        self,
        error_message: str,
        sql_context: str,
        error_type: str = "compilation",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        metadata = dict(metadata or {})
        canonical_error = self._canonicalize_error(error_message, metadata)
        sql_pattern = metadata.get("sql_pattern") or ",".join(self.sql_normalizer.extract_key_patterns(sql_context))
        category = str(metadata.get("category") or "").strip().lower()
        code = str(metadata.get("code") or "").strip().lower()
        payload = f"{error_type}|{category}|{code}|{canonical_error}|{sql_pattern}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def generate_dedup_key(
        self,
        error_message: str,
        error_type: str = "compilation",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        metadata = dict(metadata or {})
        canonical_error = self._canonicalize_error(error_message, metadata)
        category = str(metadata.get("category") or "").strip().lower()
        code = str(metadata.get("code") or "").strip().lower()
        return "|".join(
            [
                str(error_type or "compilation").strip().lower(),
                category,
                code,
                canonical_error,
            ]
        )

    def _canonicalize_error(self, error_message: str, metadata: Dict[str, Any]) -> str:
        normalized_error = " ".join((error_message or "").strip().lower().split())
        category = str(metadata.get("category") or "").strip().lower()
        code = str(metadata.get("code") or "").strip().lower()

        if code == "repository_method_signature_mismatch" or category == "repository-mismatch":
            signature_match = re.search(
                r"with\s+(\d+)\s+args?.*?with\s+\[([0-9,\s]+)\]\s+args?",
                normalized_error,
            )
            if signature_match:
                called_args = signature_match.group(1)
                declared_args = ",".join(
                    sorted(part.strip() for part in signature_match.group(2).split(",") if part.strip())
                )
                return f"repository_method_signature_mismatch|called={called_args}|declared={declared_args}"
            if "not declared" in normalized_error:
                return "missing_repository_method"

        return normalized_error

    def deduplicate(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique: List[Dict[str, Any]] = []
        seen = set()
        for record in records or []:
            dedup_key = self.generate_dedup_key(
                str(record.get("error_message") or ""),
                str(record.get("error_type") or "compilation"),
                record,
            )
            fingerprint = record.get("fingerprint") or dedup_key
            if dedup_key in seen or fingerprint in seen:
                continue
            seen.add(dedup_key)
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
                self._rebuild_dedup_index()
        except Exception as exc:
            logger.warning("Failed to read error solution registry %s: %s", self.registry_path, exc)

    def _persist_registry(self) -> None:
        try:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            self.registry_path.write_text(json.dumps(self.registry, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to persist error solution registry %s: %s", self.registry_path, exc)

    def _rebuild_dedup_index(self) -> None:
        self._dedup_index = {}
        for fingerprint, record in self.registry.items():
            dedup_key = self.generate_dedup_key(
                str(record.get("error_message") or ""),
                str(record.get("error_type") or "compilation"),
                record,
            )
            self._dedup_index.setdefault(dedup_key, fingerprint)
