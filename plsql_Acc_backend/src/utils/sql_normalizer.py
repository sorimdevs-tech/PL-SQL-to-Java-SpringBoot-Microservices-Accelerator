"""Helpers for producing stable SQL fingerprints across minor formatting changes."""

from __future__ import annotations

import re


class SQLNormalizer:
    """Normalize PL/SQL and SQL text for matching and deduplication."""

    _line_comment_pattern = re.compile(r"--.*?$", re.MULTILINE)
    _block_comment_pattern = re.compile(r"/\*.*?\*/", re.DOTALL)
    _whitespace_pattern = re.compile(r"\s+")
    _quoted_pattern = re.compile(r'"([^"]+)"')
    _procedure_pattern = re.compile(r"\b(create|replace|or|procedure|function|trigger|package|body)\b", re.IGNORECASE)

    def normalize_sql(self, sql: str) -> str:
        """Return a stable normalized representation of SQL/PLSQL text."""
        text = sql or ""
        text = self._block_comment_pattern.sub(" ", text)
        text = self._line_comment_pattern.sub(" ", text)
        text = self._quoted_pattern.sub(lambda match: match.group(1), text)
        text = text.replace("\r", "\n")
        text = self._whitespace_pattern.sub(" ", text)
        text = text.strip().lower()
        return text

    def extract_key_patterns(self, sql: str) -> list[str]:
        """Extract lightweight semantic markers used as retrieval metadata."""
        normalized = self.normalize_sql(sql)
        if not normalized:
            return []

        patterns: list[str] = []
        for keyword in ("select", "insert", "update", "delete", "merge", "join", "group by", "order by", "for update", "skip locked", "bulk collect"):
            if keyword in normalized:
                patterns.append(keyword.replace(" ", "_"))

        if self._procedure_pattern.search(normalized):
            patterns.append("plsql_program_unit")

        return patterns
