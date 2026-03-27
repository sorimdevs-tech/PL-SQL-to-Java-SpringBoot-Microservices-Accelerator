"""Shared naming and normalization helpers for deterministic code generation."""

from __future__ import annotations

import re
from typing import Optional, Set


# Java reserved and restricted identifiers that cannot be used as method names.
JAVA_RESERVED_IDENTIFIERS = frozenset(
    {
        "abstract",
        "assert",
        "boolean",
        "break",
        "byte",
        "case",
        "catch",
        "char",
        "class",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extends",
        "final",
        "finally",
        "float",
        "for",
        "goto",
        "if",
        "implements",
        "import",
        "instanceof",
        "int",
        "interface",
        "long",
        "native",
        "new",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "short",
        "static",
        "strictfp",
        "super",
        "switch",
        "synchronized",
        "this",
        "throw",
        "throws",
        "transient",
        "try",
        "void",
        "volatile",
        "while",
        "true",
        "false",
        "null",
        "_",
        # Restricted identifiers in modern Java versions.
        "var",
        "yield",
        "record",
        "sealed",
        "permits",
        "non-sealed",
        "module",
        "open",
        "opens",
        "exports",
        "requires",
        "transitive",
        "uses",
        "provides",
        "to",
        "with",
    }
)


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


def is_java_reserved_identifier(value: str) -> bool:
    token = (value or "").strip()
    return bool(token) and token.lower() in JAVA_RESERVED_IDENTIFIERS


def make_java_safe_identifier(value: str, suffix: str = "Value", existing: Optional[Set[str]] = None) -> str:
    token = (value or "").strip() or "value"
    candidate = token
    if is_java_reserved_identifier(candidate):
        candidate = f"{candidate}{suffix}"
    taken = set(existing or set())
    if candidate not in taken and not is_java_reserved_identifier(candidate):
        return candidate
    base = candidate
    idx = 2
    while candidate in taken or is_java_reserved_identifier(candidate):
        candidate = f"{base}{idx}"
        idx += 1
    return candidate
