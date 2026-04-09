"""Rule-based classifier for Java/Maven/Gradle build failures."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict


class ErrorClassifier:
    """Categorize compiler failures into retrieval-friendly buckets."""

    def classify_error(self, error: Any) -> Dict[str, str]:
        payload = self._to_dict(error)
        message = f"{payload.get('code', '')} {payload.get('message', '')}".strip().lower()

        error_type = "compilation"
        category = "general"

        if "cannot find symbol" in message or "package " in message and "does not exist" in message:
            category = "dependency"
        elif "incompatible types" in message or "cannot be converted to" in message:
            category = "type-mismatch"
        elif ("with 2 args" in message or "with 1 args" in message or "with 3 args" in message or "with 4 args" in message) and "declares" in message:
            category = "repository-mismatch"
        elif "expected" in message or "';'" in message or "reached end of file" in message:
            category = "syntax"
        elif "method " in message and ("cannot be applied" in message or "not applicable" in message):
            category = "signature"
        elif "does not override" in message or "abstract" in message:
            category = "inheritance"
        elif "variable " in message and "already defined" in message:
            category = "duplicate-definition"

        build_tool = str(payload.get("build_tool") or "").lower()
        if "test" in message and build_tool in {"maven", "gradle"}:
            error_type = "test-compilation"

        return {
            "error_type": error_type,
            "category": category,
        }

    def _to_dict(self, error: Any) -> Dict[str, Any]:
        if isinstance(error, dict):
            return error
        if is_dataclass(error):
            return asdict(error)
        return {
            "message": getattr(error, "message", ""),
            "code": getattr(error, "code", ""),
            "build_tool": getattr(error, "build_tool", ""),
        }
