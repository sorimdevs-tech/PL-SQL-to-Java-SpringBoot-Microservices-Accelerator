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
