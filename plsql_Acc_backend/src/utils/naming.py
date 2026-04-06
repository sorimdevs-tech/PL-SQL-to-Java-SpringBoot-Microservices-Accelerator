"""Shared naming and normalization helpers for deterministic code generation."""

from __future__ import annotations

import re


def to_pascal_case(value: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", (value or "").strip()) if part]
    if not parts:
        return ""
    return "".join(part[:1].upper() + part[1:].lower() for part in parts)


def normalize_column_name(col: str) -> str:
    """Normalize SQL-ish identifiers into deterministic lowerCamelCase names."""
    raw = (col or "").strip().strip('"`')
    if "." in raw:
        raw = raw.split(".")[-1]
    raw = re.sub(r"^(p|v)_+", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_")
    if not raw:
        return "value"
    pascal = to_pascal_case(raw)
    if not pascal:
        return "value"
    return pascal[:1].lower() + pascal[1:]

