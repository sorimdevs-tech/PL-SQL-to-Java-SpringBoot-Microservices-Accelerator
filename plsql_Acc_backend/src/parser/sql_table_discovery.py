"""Utilities for extracting SQL table names for discovery APIs."""

from __future__ import annotations

import re
from typing import Iterable, List, Set


CREATE_TABLE_PATTERN = re.compile(
    r"""
    \bcreate\s+table\s+
    (?:if\s+not\s+exists\s+)?
    (?:
        (?:"?[\w$#]+"?|`?[\w$#]+`?)
        \s*\.\s*
    )?
    ["`]?([\w$#]+)["`]?
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)

CREATE_TABLE_BODY_PATTERN = re.compile(
    r"\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?"
    r"(?:(?:\"?[\w$#]+\"?|`?[\w$#]+`?)\s*\.\s*)?"
    r"(?:\"?[\w$#]+\"?|`?[\w$#]+`?)\s*\(",
    flags=re.IGNORECASE,
)


class SQLDiscoveryParseError(ValueError):
    """Raised when SQL discovery parsing cannot continue."""


def remove_sql_comments(sql_text: str) -> str:
    """Remove line and block comments from SQL text."""
    without_block = re.sub(r"/\*.*?\*/", " ", sql_text, flags=re.DOTALL)
    return re.sub(r"--[^\r\n]*", " ", without_block)


def extract_create_table_names(sql_text: str) -> List[str]:
    """Extract unique table names from CREATE TABLE statements."""
    if sql_text is None:
        raise SQLDiscoveryParseError("SQL content cannot be null")

    cleaned = remove_sql_comments(sql_text)
    table_names: Set[str] = set()
    for match in CREATE_TABLE_PATTERN.finditer(cleaned):
        table_name = match.group(1)
        if table_name:
            table_names.add(table_name.upper())

    return sorted(table_names)


def merge_table_names(chunks: Iterable[str]) -> List[str]:
    """Extract tables from multiple SQL chunks and return sorted unique names."""
    merged: Set[str] = set()
    for chunk in chunks:
        merged.update(extract_create_table_names(chunk))
    return sorted(merged)


def _split_top_level_csv(content: str) -> List[str]:
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    for char in content:
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            segment = "".join(current).strip()
            if segment:
                parts.append(segment)
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def extract_create_table_columns(sql_text: str) -> Dict[str, List[Dict[str, str]]]:
    """Extract table columns (name + type) from CREATE TABLE statements."""
    if sql_text is None:
        raise SQLDiscoveryParseError("SQL content cannot be null")

    cleaned = remove_sql_comments(sql_text)
    table_columns: Dict[str, List[Dict[str, str]]] = {}

    for match in CREATE_TABLE_BODY_PATTERN.finditer(cleaned):
        header = match.group(0)
        # Extract table name from header
        name_match = CREATE_TABLE_PATTERN.search(header)
        if not name_match:
            continue
        table_name = name_match.group(1)
        if not table_name:
            continue
        normalized_table = table_name.upper()

        open_idx = match.end() - 1
        depth = 0
        close_idx = None
        for idx in range(open_idx, len(cleaned)):
            char = cleaned[idx]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    close_idx = idx
                    break
        if close_idx is None:
            continue

        body = cleaned[open_idx + 1 : close_idx]
        columns: List[Dict[str, str]] = []
        for item in _split_top_level_csv(body):
            segment = " ".join(item.strip().split())
            if not segment:
                continue
            lowered = segment.lower()
            if lowered.startswith(("constraint ", "primary ", "foreign ", "unique ", "check ")):
                continue
            col_match = re.match(r'^["`]?([\w$#]+)["`]?\s+([A-Za-z][A-Za-z0-9_]*(?:\s*\([^)]*\))?)', segment)
            if not col_match:
                continue
            col_name = col_match.group(1).upper()
            col_type = col_match.group(2).upper()
            columns.append({"name": col_name, "type": col_type})

        if columns:
            table_columns[normalized_table] = columns

    return table_columns
