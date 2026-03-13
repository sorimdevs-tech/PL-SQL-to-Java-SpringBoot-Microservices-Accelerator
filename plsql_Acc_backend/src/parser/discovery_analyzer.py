"""Discovery metadata analyzer for SQL/PLSQL sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Set

from src.parser.sql_table_discovery import remove_sql_comments


KEYWORD_BLOCKLIST = {
    "if",
    "elsif",
    "else",
    "loop",
    "for",
    "while",
    "select",
    "insert",
    "update",
    "delete",
    "into",
    "values",
    "return",
    "raise",
    "when",
    "count",
    "sum",
    "min",
    "max",
    "substr",
    "nvl",
}

OBJECT_PATTERN = re.compile(
    r"\bcreate\s+(?:or\s+replace\s+)?(?:editionable\s+|noneditionable\s+)?(procedure|function|package(?:\s+body)?)\s+([`\"\w$#\.]+)",
    flags=re.IGNORECASE,
)
PARAM_PATTERN = re.compile(
    r"""^\s*["`]?([\w$#]+)["`]?\s+(?:(in\s+out|in|out)\s+)?(.+?)\s*$""",
    flags=re.IGNORECASE,
)


@dataclass
class ObjectSlice:
    """PL/SQL object block and metadata."""

    object_type: str
    object_name: str
    block_text: str


def _normalize_identifier(raw_name: str) -> str:
    clean = raw_name.strip().strip('"`')
    if "." in clean:
        clean = clean.split(".")[-1]
    return clean


def _to_pascal_case(name: str) -> str:
    parts = re.split(r"[_\W]+", name)
    return "".join(part[:1].upper() + part[1:].lower() for part in parts if part)


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


def _extract_parameter_section(header_text: str) -> str:
    first_paren = header_text.find("(")
    if first_paren < 0:
        return ""

    depth = 0
    for index in range(first_paren, len(header_text)):
        char = header_text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return header_text[first_paren + 1 : index]
    return ""


def _extract_objects(sql_text: str) -> List[ObjectSlice]:
    matches = list(OBJECT_PATTERN.finditer(sql_text))
    if not matches:
        return []

    objects: List[ObjectSlice] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(sql_text)
        raw_type = match.group(1).upper().replace(" BODY", "")
        name = _normalize_identifier(match.group(2))
        objects.append(ObjectSlice(object_type=raw_type, object_name=name, block_text=sql_text[start:end]))
    return objects


def _extract_parameters(block_text: str) -> Dict[str, List[Dict[str, str]]]:
    header_limit = re.search(r"\b(?:is|as)\b", block_text, flags=re.IGNORECASE)
    header = block_text[: header_limit.start()] if header_limit else block_text[:800]
    parameter_text = _extract_parameter_section(header)

    in_params: List[Dict[str, str]] = []
    out_params: List[Dict[str, str]] = []
    if not parameter_text.strip():
        return {"in": in_params, "out": out_params}

    for item in _split_top_level_csv(parameter_text):
        normalized = " ".join(item.split())
        match = PARAM_PATTERN.match(normalized)
        if not match:
            continue
        name, direction, data_type = match.groups()
        payload = {"name": _normalize_identifier(name), "type": data_type.strip().upper()}
        direction_text = (direction or "IN").upper().replace("  ", " ")
        if "OUT" in direction_text:
            out_params.append(payload)
        if direction_text in {"IN", "IN OUT"}:
            in_params.append(payload)
    return {"in": in_params, "out": out_params}


def _extract_operations_and_tables(block_text: str) -> Dict[str, Any]:
    operations: Set[str] = set()
    tables: Set[str] = set()

    def _add_table(raw_name: str) -> None:
        if not raw_name:
            return
        tables.add(_normalize_identifier(raw_name).upper())

    for pattern, operation in (
        (r"\bselect\b", "SELECT"),
        (r"\binsert\b", "INSERT"),
        (r"\bupdate\b", "UPDATE"),
        (r"\bdelete\b", "DELETE"),
    ):
        if re.search(pattern, block_text, flags=re.IGNORECASE):
            operations.add(operation)

    for match in re.finditer(r"\bfrom\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        _add_table(match.group(1))
    for match in re.finditer(r"\bjoin\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        _add_table(match.group(1))
    for match in re.finditer(r"\binsert\s+into\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        _add_table(match.group(1))
    for match in re.finditer(r"\bupdate\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        _add_table(match.group(1))
    for match in re.finditer(r"\bdelete\s+from\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        _add_table(match.group(1))

    return {"operations": sorted(operations), "tables": sorted(tables)}


def _extract_table_aliases(block_text: str) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for match in re.finditer(
        r"\b(?:from|join)\s+([`\"\w$#\.]+)\s*(?:as\s+)?([A-Za-z_][\w$#]*)?",
        block_text,
        flags=re.IGNORECASE,
    ):
        table = _normalize_identifier(match.group(1)).upper()
        alias = match.group(2)
        aliases[table] = table
        if alias:
            aliases[alias.upper()] = table
    return aliases


def _extract_table_columns(block_text: str, tables: Sequence[str]) -> Dict[str, List[str]]:
    aliases = _extract_table_aliases(block_text)
    normalized_tables = {table.upper() for table in tables}
    columns: Dict[str, Set[str]] = {table: set() for table in normalized_tables}
    for match in re.finditer(r"\b([A-Za-z_][\w$#]*)\s*\.\s*([A-Za-z_][\w$#]*)", block_text):
        prefix = match.group(1).upper()
        column = match.group(2).upper()
        table = aliases.get(prefix, prefix)
        if table in normalized_tables:
            columns.setdefault(table, set()).add(column)
    return {table: sorted(values) for table, values in columns.items()}


def _extract_table_relationships(block_text: str) -> List[Dict[str, str]]:
    aliases = _extract_table_aliases(block_text)
    relationships: List[Dict[str, str]] = []
    pattern = re.compile(
        r"\bjoin\s+([`\"\w$#\.]+)\s*(?:as\s+)?([A-Za-z_][\w$#]*)?\s+on\s+"
        r"([A-Za-z_][\w$#]*)\s*\.\s*([A-Za-z_][\w$#]*)\s*=\s*"
        r"([A-Za-z_][\w$#]*)\s*\.\s*([A-Za-z_][\w$#]*)",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(block_text):
        right_table = _normalize_identifier(match.group(1)).upper()
        right_alias = match.group(2)
        left_alias = match.group(3).upper()
        left_column = match.group(4).upper()
        right_alias_ref = match.group(5).upper()
        right_column = match.group(6).upper()
        left_table = aliases.get(left_alias, left_alias)
        right_table_resolved = aliases.get(right_alias_ref, right_alias_ref)
        if right_alias:
            aliases[right_alias.upper()] = right_table
        relationships.append(
            {
                "fromTable": left_table,
                "fromColumn": left_column,
                "toTable": right_table_resolved,
                "toColumn": right_column,
            }
        )
    return relationships


def _extract_local_variables(block_text: str) -> List[Dict[str, str]]:
    declaration_section = ""
    header_end = re.search(r"\b(?:is|as)\b", block_text, flags=re.IGNORECASE)
    if header_end:
        remainder = block_text[header_end.end() :]
        begin_match = re.search(r"\bbegin\b", remainder, flags=re.IGNORECASE)
        declaration_section = remainder[: begin_match.start()] if begin_match else remainder

    local_vars: List[Dict[str, str]] = []
    for line in declaration_section.splitlines():
        normalized = " ".join(line.strip().split())
        if not normalized or normalized.startswith("--"):
            continue
        match = re.match(
            r"""^["`]?([\w$#]+)["`]?\s+(?:constant\s+)?([A-Za-z][\w$#]*(?:\s*\([^;]+\))?)\s*(?:;|:=|default\b)""",
            normalized,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        name, data_type = match.groups()
        local_vars.append({"name": _normalize_identifier(name), "type": data_type.upper()})
    return local_vars


def _extract_exceptions(block_text: str) -> List[str]:
    found: Set[str] = set()
    for match in re.finditer(r"\bwhen\s+([A-Za-z_][\w$#]*)\s+then\b", block_text, flags=re.IGNORECASE):
        found.add(match.group(1).upper())
    for match in re.finditer(r"\b([A-Za-z_][\w$#]*)\s+exception\s*;", block_text, flags=re.IGNORECASE):
        found.add(match.group(1).upper())
    return sorted(found)


def _extract_procedure_calls(block_text: str, current_object: str) -> List[str]:
    calls: Set[str] = set()
    for match in re.finditer(r"\b([A-Za-z_][\w$#]*)\s*\(", block_text):
        call_name = match.group(1)
        lowered = call_name.lower()
        if lowered in KEYWORD_BLOCKLIST:
            continue
        if lowered == current_object.lower():
            continue
        calls.add(call_name.upper())
    return sorted(calls)


def _complexity_metrics(block_text: str) -> Dict[str, int]:
    non_empty_lines = [line for line in block_text.splitlines() if line.strip()]
    return {
        "linesOfCode": len(non_empty_lines),
        "numberOfQueries": len(
            re.findall(r"\b(?:select|insert|update|delete)\b", block_text, flags=re.IGNORECASE)
        ),
        "numberOfConditions": len(re.findall(r"\b(?:if|elsif|else)\b", block_text, flags=re.IGNORECASE)),
        "numberOfLoops": len(re.findall(r"\bloop\b", block_text, flags=re.IGNORECASE)),
    }


def _build_conversion_preview(procedure_name: str, tables_used: Sequence[str]) -> Dict[str, List[str]]:
    entities = sorted({_to_pascal_case(table) for table in tables_used if table})
    repositories = [f"{entity}Repository" for entity in entities]
    service_base = _to_pascal_case(procedure_name) or "Discovery"
    return {
        "entities": entities,
        "repositories": repositories,
        "services": [f"{service_base}Service"],
        "controllers": [f"{service_base}Controller"],
        "dtos": [f"{entity}Dto" for entity in entities],
    }


def analyze_sql_source(sql_text: str) -> List[Dict[str, Any]]:
    """Analyze SQL/PLSQL text and return discovery metadata per object."""
    cleaned = remove_sql_comments(sql_text)
    objects = _extract_objects(cleaned)
    if not objects:
        return []

    results: List[Dict[str, Any]] = []
    for item in objects:
        params = _extract_parameters(item.block_text)
        operations_tables = _extract_operations_and_tables(item.block_text)
        tables_used = operations_tables["tables"]
        table_columns = _extract_table_columns(item.block_text, tables_used)
        table_relationships = _extract_table_relationships(item.block_text)
        entry: Dict[str, Any] = {
            "procedureName": item.object_name,
            "objectType": item.object_type,
            "parameters": params,
            "tablesUsed": tables_used,
            "operations": operations_tables["operations"],
            "localVariables": _extract_local_variables(item.block_text),
            "exceptions": _extract_exceptions(item.block_text),
            "complexity": _complexity_metrics(item.block_text),
            "dependencyGraph": {
                "tablesUsed": tables_used,
                "proceduresCalled": _extract_procedure_calls(item.block_text, item.object_name),
            },
            "tableDetails": {
                "tables": [
                    {"name": table, "columns": table_columns.get(table, [])} for table in tables_used
                ],
                "relationships": table_relationships,
            },
        }
        entry["conversionPreview"] = _build_conversion_preview(item.object_name, tables_used)
        results.append(entry)
    return results
