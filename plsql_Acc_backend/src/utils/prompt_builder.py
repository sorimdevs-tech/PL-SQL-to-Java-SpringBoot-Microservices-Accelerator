"""Prompt construction helpers for RAG-assisted SQL conversion."""

from __future__ import annotations

from typing import Any, Dict, List


def _metadata(sql_node: Any) -> Dict[str, Any]:
    if isinstance(sql_node, dict):
        return sql_node.get("metadata") or {}
    return getattr(sql_node, "metadata", {}) or {}


def _value(sql_node: Any, name: str, fallback: str = "") -> str:
    if isinstance(sql_node, dict):
        value = sql_node.get(name)
    else:
        value = getattr(sql_node, name, None)
    if value is None:
        value = _metadata(sql_node).get(name, fallback)
    return str(value or fallback)


def build_prompt(sql_node: Any, examples: List[Dict[str, Any]]) -> str:
    query = _value(sql_node, "query") or _metadata(sql_node).get("sql", "")
    semantic_type = _value(sql_node, "semantic_type", "UNKNOWN")
    formatted_examples = []
    for index, example in enumerate(examples or [], start=1):
        formatted_examples.append(
            f"Example {index}:\n"
            f"Type: {example.get('type', '')}\n"
            f"Input: {example.get('input', '')}\n"
            f"Output:\n{example.get('output', '')}"
        )
    examples_text = "\n\n".join(formatted_examples) or "No close examples were found."
    return f"""You are an expert backend engineer.

Convert PL/SQL and SQL semantics into clean Java Spring Boot code.
Use the examples as implementation patterns, not as text to copy blindly.

Current semantic type: {semantic_type}

Here are similar examples:

{examples_text}

Now convert this SQL:
{query}

Return only clean Java Spring Boot code."""
