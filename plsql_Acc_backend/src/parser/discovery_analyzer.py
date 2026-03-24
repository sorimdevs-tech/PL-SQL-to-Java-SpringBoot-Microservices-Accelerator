"""Discovery metadata analyzer for SQL/PLSQL sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Set, Tuple, Optional

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

TABLE_NAME_BLOCKLIST = {
    "SET",
    "SKIP",
    "LOCKED",
    "MATCHED",
    "NOT",
    "DUAL",
    "INTO",
    "FROM",
    "JOIN",
    "ON",
    "USING",
    "WHEN",
    "THEN",
    "VALUES",
    "TABLE",
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
}

TYPE_BLOCKLIST = {
    "VARCHAR2",
    "NVARCHAR2",
    "CHAR",
    "NCHAR",
    "NUMBER",
    "DATE",
    "TIMESTAMP",
    "CLOB",
    "BLOB",
    "INTEGER",
    "PLS_INTEGER",
    "BOOLEAN",
    "FLOAT",
    "DECIMAL",
}

AGGREGATION_FUNCTIONS = ("SUM", "COUNT", "AVG", "MIN", "MAX")

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


def _normalize_table_candidate(raw_name: str) -> str:
    normalized = _normalize_identifier(raw_name).upper()
    if not normalized or normalized in TABLE_NAME_BLOCKLIST:
        return ""
    return normalized


def _to_pascal_case(name: str) -> str:
    parts = re.split(r"[_\W]+", name)
    return "".join(part[:1].upper() + part[1:].lower() for part in parts if part)


def _prepare_sql_text(sql_text: str) -> str:
    cleaned = remove_sql_comments(sql_text)
    return _remove_sqlplus_commands(cleaned)


def _remove_sqlplus_commands(sql_text: str) -> str:
    filtered_lines: List[str] = []
    command_prefixes = (
        "spool ",
        "prompt ",
        "rem ",
        "connect ",
        "whenever ",
        "column ",
        "ttitle ",
        "btitle ",
        "pause ",
        "show ",
        "exit",
        "start ",
        "@@",
        "@",
    )
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped == "/":
            continue
        lowered = stripped.lower()
        if lowered.startswith("set "):
            if re.match(r'^set\s+["`A-Za-z_][\w$#"`]*\s*=', stripped, flags=re.IGNORECASE):
                filtered_lines.append(line)
                continue
            continue
        if any(lowered.startswith(prefix) for prefix in command_prefixes):
            continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines)


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


def _extract_create_table_columns(sql_text: str) -> Dict[str, List[str]]:
    create_pattern = re.compile(r"\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?", flags=re.IGNORECASE)
    name_pattern = re.compile(
        r'(?:"?[\w$#]+"?|`?[\w$#]+`?)(?:\s*\.\s*(?:"?[\w$#]+"?|`?[\w$#]+`?))?',
        flags=re.IGNORECASE,
    )
    ddl_columns: Dict[str, List[str]] = {}

    for match in create_pattern.finditer(sql_text):
        cursor = match.end()
        remainder = sql_text[cursor:]
        name_match = name_pattern.match(remainder.lstrip())
        if not name_match:
            continue
        raw_name = name_match.group(0)
        table_name = _normalize_identifier(raw_name).upper()
        cursor += remainder.find(raw_name) + len(raw_name)

        open_idx = sql_text.find("(", cursor)
        if open_idx == -1:
            continue
        depth = 0
        close_idx = None
        for idx in range(open_idx, len(sql_text)):
            char = sql_text[idx]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    close_idx = idx
                    break
        if close_idx is None:
            continue

        body = sql_text[open_idx + 1 : close_idx]
        columns: List[str] = []
        for item in _split_top_level_csv(body):
            segment = " ".join(item.strip().split())
            if not segment:
                continue
            lowered = segment.lower()
            if lowered.startswith(("constraint ", "primary ", "foreign ", "unique ", "check ")):
                continue
            col_match = re.match(r'^["`]?([\w$#]+)["`]?\s+', segment)
            if not col_match:
                continue
            columns.append(_normalize_identifier(col_match.group(1)).upper())

        if columns:
            ddl_columns[table_name] = columns
    return ddl_columns


def _extract_table_definitions(sql_text: str) -> List[Dict[str, Any]]:
    create_pattern = re.compile(r"\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?", flags=re.IGNORECASE)
    name_pattern = re.compile(
        r'(?:"?[\w$#]+"?|`?[\w$#]+`?)(?:\s*\.\s*(?:"?[\w$#]+"?|`?[\w$#]+`?))?',
        flags=re.IGNORECASE,
    )
    table_defs: List[Dict[str, Any]] = []

    for match in create_pattern.finditer(sql_text):
        cursor = match.end()
        remainder = sql_text[cursor:]
        name_match = name_pattern.match(remainder.lstrip())
        if not name_match:
            continue
        raw_name = name_match.group(0)
        table_name = _normalize_identifier(raw_name).upper()
        cursor += remainder.find(raw_name) + len(raw_name)

        open_idx = sql_text.find("(", cursor)
        if open_idx == -1:
            continue
        depth = 0
        close_idx = None
        for idx in range(open_idx, len(sql_text)):
            char = sql_text[idx]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    close_idx = idx
                    break
        if close_idx is None:
            continue

        body = sql_text[open_idx + 1 : close_idx]
        columns: List[Dict[str, Any]] = []
        primary_keys: List[str] = []
        foreign_keys: List[Dict[str, str]] = []

        for item in _split_top_level_csv(body):
            segment = " ".join(item.strip().split())
            if not segment:
                continue
            lowered = segment.lower()

            table_pk_match = re.search(r"\bprimary\s+key\s*\(([^)]+)\)", segment, flags=re.IGNORECASE)
            if table_pk_match:
                primary_keys.extend(
                    _normalize_identifier(token).upper()
                    for token in _split_top_level_csv(table_pk_match.group(1))
                )
            table_fk_match = re.search(
                r"\bforeign\s+key\s*\(([^)]+)\)\s+references\s+([`\"\w$#\.]+)\s*\(([^)]+)\)",
                segment,
                flags=re.IGNORECASE,
            )
            if table_fk_match:
                source_cols = [_normalize_identifier(token).upper() for token in _split_top_level_csv(table_fk_match.group(1))]
                target_table = _normalize_identifier(table_fk_match.group(2)).upper()
                target_cols = [_normalize_identifier(token).upper() for token in _split_top_level_csv(table_fk_match.group(3))]
                for src, dst in zip(source_cols, target_cols):
                    foreign_keys.append(
                        {
                            "source_column": src,
                            "target_table": target_table,
                            "target_column": dst,
                        }
                    )
                continue

            if lowered.startswith(("constraint ", "primary ", "foreign ", "unique ", "check ")):
                continue

            col_match = re.match(
                r'^["`]?([\w$#]+)["`]?\s+([A-Za-z][A-Za-z0-9_]*(?:\s*\([^)]*\))?)',
                segment,
            )
            if not col_match:
                continue
            col_name = _normalize_identifier(col_match.group(1)).upper()
            col_type = col_match.group(2).upper()
            columns.append({"name": col_name, "type": col_type})

            if re.search(r"\bprimary\s+key\b", segment, flags=re.IGNORECASE):
                primary_keys.append(col_name)
            inline_ref = re.search(
                r"\breferences\s+([`\"\w$#\.]+)\s*\(([^)]+)\)",
                segment,
                flags=re.IGNORECASE,
            )
            if inline_ref:
                target_table = _normalize_identifier(inline_ref.group(1)).upper()
                target_cols = [_normalize_identifier(token).upper() for token in _split_top_level_csv(inline_ref.group(2))]
                if target_cols:
                    foreign_keys.append(
                        {
                            "source_column": col_name,
                            "target_table": target_table,
                            "target_column": target_cols[0],
                        }
                    )

        table_defs.append(
            {
                "name": table_name,
                "columns": columns,
                "primary_keys": sorted(dict.fromkeys(primary_keys)),
                "foreign_keys": foreign_keys,
            }
        )

    return table_defs


def infer_tables_from_dml(sql_text: str) -> List[Dict[str, Any]]:
    cleaned = _prepare_sql_text(sql_text)
    objects = _extract_objects(cleaned)
    blocks = [item.block_text for item in objects] or [cleaned]
    inferred_tables: Set[str] = set()
    inferred_columns: Dict[str, Set[str]] = {}

    def add_table(raw_name: str) -> None:
        normalized = _normalize_identifier(raw_name).upper()
        if not normalized or normalized in {"DUAL", "TABLE"}:
            return
        inferred_tables.add(normalized)
        inferred_columns.setdefault(normalized, set())

    for block_text in blocks:
        operations_tables = _extract_operations_and_tables(block_text)
        operations_by_table = _extract_operations_by_table(block_text)
        block_tables: Set[str] = set()

        for table_name in operations_tables.get("tables", []):
            normalized_table = _normalize_identifier(table_name).upper()
            add_table(normalized_table)
            if normalized_table and normalized_table not in {"DUAL", "TABLE"}:
                block_tables.add(normalized_table)
        for table_name in operations_by_table:
            normalized_table = _normalize_identifier(table_name).upper()
            add_table(normalized_table)
            if normalized_table and normalized_table not in {"DUAL", "TABLE"}:
                block_tables.add(normalized_table)

        bulk_operations = detect_bulk_operations({"block_text": block_text})
        for operation in bulk_operations:
            op_type = str(operation.get("type", "")).upper()
            if op_type == "BULK_COLLECT":
                source_table = _normalize_identifier(str(operation.get("source", ""))).upper()
                add_table(source_table)
                if source_table and source_table not in {"DUAL", "TABLE"}:
                    block_tables.add(source_table)
            elif op_type == "FORALL":
                target_table = _normalize_identifier(str(operation.get("table", ""))).upper()
                add_table(target_table)
                if target_table and target_table not in {"DUAL", "TABLE"}:
                    block_tables.add(target_table)

        table_columns = _extract_table_columns(block_text, sorted(block_tables))
        for table_name, columns in table_columns.items():
            normalized_table = _normalize_identifier(table_name).upper()
            inferred_columns.setdefault(normalized_table, set()).update(
                _normalize_identifier(column).upper()
                for column in columns
                if column
            )

    return [
        {
            "name": table_name,
            "table_name": table_name,
            "columns": [
                {"name": column_name, "type": "UNKNOWN"}
                for column_name in sorted(inferred_columns.get(table_name, set()))
            ],
            "primary_keys": [],
            "foreign_keys": [],
            "source": "inferred_from_procedure",
        }
        for table_name in sorted(inferred_tables)
    ]


def _extract_alter_table_foreign_keys(sql_text: str) -> List[Dict[str, str]]:
    pattern = re.compile(
        r'alter\s+table\s+([`"\w$#\.]+).*?foreign\s+key\s*\(([^)]+)\)\s+references\s+([`"\w$#\.]+)\s*\(([^)]+)\)',
        flags=re.IGNORECASE | re.DOTALL,
    )
    relationships: List[Dict[str, str]] = []
    for match in pattern.finditer(sql_text):
        source_table = _normalize_identifier(match.group(1)).upper()
        source_cols = [_normalize_identifier(token).upper() for token in _split_top_level_csv(match.group(2))]
        target_table = _normalize_identifier(match.group(3)).upper()
        target_cols = [_normalize_identifier(token).upper() for token in _split_top_level_csv(match.group(4))]
        for src, dst in zip(source_cols, target_cols):
            relationships.append(
                {
                    "source_table": source_table,
                    "source_column": src,
                    "target_table": target_table,
                    "target_column": dst,
                }
            )
    return relationships


def _extract_sequence_catalog(sql_text: str) -> Dict[str, Any]:
    sequence_names = sorted(
        {
            _normalize_identifier(match.group(1)).upper()
            for match in re.finditer(r"\bcreate\s+sequence\s+([`\"\w$#\.]+)", sql_text, flags=re.IGNORECASE)
        }
    )
    known_sequences = set(sequence_names)
    mappings: List[Dict[str, str]] = []
    seen_pairs: Set[Tuple[str, str]] = set()

    insert_pat = re.compile(
        r"\binsert\s+into\s+([`\"\w$#\.]+)\b.*?\b([A-Za-z_][\w$#]*)\.nextval\b",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in insert_pat.finditer(sql_text):
        table_name = _normalize_identifier(match.group(1)).upper()
        sequence_name = _normalize_identifier(match.group(2)).upper()
        if sequence_name not in known_sequences:
            continue
        pair = (sequence_name, table_name)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        mappings.append({"sequence_name": sequence_name, "mapped_table": table_name})

    return {
        "sequences": [{"name": seq} for seq in sequence_names],
        "sequence_mapping": mappings,
        "sequence_names": sequence_names,
    }


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
    all_params: List[Dict[str, str]] = []
    if not parameter_text.strip():
        return {"in": in_params, "out": out_params, "all": all_params}

    for item in _split_top_level_csv(parameter_text):
        normalized = " ".join(item.split())
        match = PARAM_PATTERN.match(normalized)
        if not match:
            continue
        name, direction, data_type = match.groups()
        direction_text = (direction or "IN").upper().replace("  ", " ")
        payload = {
            "name": _normalize_identifier(name),
            "type": data_type.strip().upper(),
            "direction": direction_text,
        }
        all_params.append(payload)
        direction_text = (direction or "IN").upper().replace("  ", " ")
        io_payload = {"name": payload["name"], "type": payload["type"]}
        if "OUT" in direction_text:
            out_params.append(io_payload)
        if direction_text in {"IN", "IN OUT"}:
            in_params.append(io_payload)
    return {"in": in_params, "out": out_params, "all": all_params}


def _extract_operations_and_tables(block_text: str) -> Dict[str, Any]:
    operations: Set[str] = set()
    tables: Set[str] = set()

    def _add_table(raw_name: str) -> None:
        if not raw_name:
            return
        normalized = _normalize_table_candidate(raw_name)
        if not normalized:
            return
        tables.add(normalized)

    if re.search(r"\bselect\b", block_text, flags=re.IGNORECASE):
        operations.add("SELECT")
    if re.search(r"\binsert\s+into\b", block_text, flags=re.IGNORECASE):
        operations.add("INSERT")
    if re.search(r"(?<!\bfor\s)\bupdate\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        operations.add("UPDATE")
    if re.search(r"\bdelete\s+from\b", block_text, flags=re.IGNORECASE):
        operations.add("DELETE")
    if re.search(r"\bmerge\s+into\b", block_text, flags=re.IGNORECASE):
        operations.add("MERGE")

    for match in re.finditer(r"\bfrom\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        _add_table(match.group(1))
    for match in re.finditer(r"\bjoin\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        _add_table(match.group(1))
    for match in re.finditer(r"\binsert\s+into\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        _add_table(match.group(1))
    for match in re.finditer(r"(?<!\bfor\s)\bupdate\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        _add_table(match.group(1))
    for match in re.finditer(r"\bdelete\s+from\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        _add_table(match.group(1))
    for match in re.finditer(r"\bmerge\s+into\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        _add_table(match.group(1))

    return {"operations": sorted(operations), "tables": sorted(tables)}


def _extract_operations_by_table(block_text: str) -> Dict[str, List[str]]:
    per_table: Dict[str, Set[str]] = {}

    def add(table: str, op: str) -> None:
        normalized = _normalize_table_candidate(table)
        if not normalized:
            return
        per_table.setdefault(normalized, set()).add(op)

    for match in re.finditer(r"\bselect\b.*?\bfrom\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE | re.DOTALL):
        add(match.group(1), "SELECT")
    for match in re.finditer(r"\binsert\s+into\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        add(match.group(1), "INSERT")
    for match in re.finditer(r"(?<!\bfor\s)\bupdate\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        add(match.group(1), "UPDATE")
    for match in re.finditer(r"\bdelete\s+from\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        add(match.group(1), "DELETE")
    for match in re.finditer(r"\bmerge\s+into\s+([`\"\w$#\.]+)", block_text, flags=re.IGNORECASE):
        add(match.group(1), "MERGE")

    return {table: sorted(ops) for table, ops in per_table.items()}


def build_conversion_units(sql_text: str) -> List[Dict[str, Any]]:
    """Return raw object blocks plus extracted semantics for code generation."""
    cleaned = _prepare_sql_text(sql_text)
    model = build_discovery_model(cleaned)
    semantics_by_object = {
        (proc.get("name", "").upper(), proc.get("object_type", "").upper()): proc
        for proc in model.get("procedures", [])
    }

    units: List[Dict[str, Any]] = []
    for item in _extract_objects(cleaned):
        object_key = (item.object_name.upper(), item.object_type.upper())
        semantics = semantics_by_object.get(object_key, {})
        units.append(
            {
                "name": item.object_name,
                "object_type": item.object_type,
                "raw_plsql": item.block_text.strip(),
                "tables_used": semantics.get("tables_used", []),
                "operations_by_table": semantics.get("operations", {}),
                "input_parameters": semantics.get("input_parameters", []),
                "output_parameters": semantics.get("output_parameters", []),
                "variables": semantics.get("variables", []),
                "lookup_keys": semantics.get("lookup_keys", {}),
                "bulk_operations": semantics.get("bulk_operations", []),
                "cursor": semantics.get("cursor", {}),
                "transaction": semantics.get("transaction", {}),
                "exceptions": semantics.get("exceptions", []),
                "business_rules": semantics.get("business_rules", []),
                "issues": semantics.get("issues", []),
                "semantic_analysis": semantics.get("semantic_analysis", {}),
            }
        )

    return units


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


def _extract_lookup_keys(
    block_text: str,
    ddl_columns: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, List[str]]:
    lookup_keys: Dict[str, Set[str]] = {}

    def add_key(table_name: str, column_name: str) -> None:
        normalized_table = _normalize_table_candidate(table_name)
        normalized_column = _normalize_identifier(column_name).upper()
        if not normalized_table or not normalized_column:
            return
        lookup_keys.setdefault(normalized_table, set()).add(normalized_column)

    def extract_clause_columns(
        clause_text: str,
        alias_map: Dict[str, str],
        default_table: str = "",
    ) -> None:
        if not clause_text.strip():
            return

        for match in re.finditer(r"\b([A-Za-z_][\w$#]*)\s*\.\s*([A-Za-z_][\w$#]*)\b", clause_text):
            resolved_table = alias_map.get(match.group(1).upper(), "")
            if resolved_table:
                add_key(resolved_table, match.group(2))

        if not default_table:
            return

        known_columns = {
            _normalize_identifier(column).upper()
            for column in (ddl_columns or {}).get(default_table.upper(), [])
            if column
        }
        unqualified_pattern = re.compile(
            r"(?:^|[\s(,])([A-Za-z_][\w$#]*)\s*"
            r"(=|<>|!=|>=|<=|>|<|\blike\b|\bin\s*\(|\bbetween\b|\bis\s+(?:not\s+)?null\b)",
            flags=re.IGNORECASE,
        )
        for raw_name, _ in unqualified_pattern.findall(clause_text):
            normalized_name = _normalize_identifier(raw_name).upper()
            if not normalized_name:
                continue
            if (
                normalized_name in TABLE_NAME_BLOCKLIST
                or normalized_name in TYPE_BLOCKLIST
                or normalized_name.lower() in KEYWORD_BLOCKLIST
            ):
                continue
            if known_columns and normalized_name not in known_columns:
                continue
            add_key(default_table, normalized_name)

    def extract_predicate_clauses(statement_text: str) -> List[str]:
        clauses: List[str] = []
        seen_clauses: Set[str] = set()
        clause_patterns = (
            re.compile(
                r"\bon\s*\((.*?)\)\s*(?=\bwhen\b|\bjoin\b|\bwhere\b|\bgroup\s+by\b|\border\s+by\b|\bhaving\b|;)",
                flags=re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\bon\s+(.*?)(?=\bjoin\b|\bwhere\b|\bgroup\s+by\b|\border\s+by\b|\bhaving\b|\bwhen\b|;)",
                flags=re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\bwhere\b(.*?)(?=\bgroup\s+by\b|\border\s+by\b|\bhaving\b|\bconnect\s+by\b|\bstart\s+with\b|\bfor\s+update\b|\breturning\b|\bwhen\b|;)",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        )
        for pattern in clause_patterns:
            for match in pattern.finditer(statement_text):
                clause = _normalize_statement_text(match.group(1))
                if not clause or clause in seen_clauses:
                    continue
                seen_clauses.add(clause)
                clauses.append(clause)
        return clauses

    def register_statement(statement_text: str, default_table: str = "", target_alias: str = "") -> None:
        alias_map = _extract_table_aliases(statement_text)
        if default_table:
            normalized_default = _normalize_table_candidate(default_table)
            if normalized_default:
                alias_map[normalized_default] = normalized_default
                if target_alias:
                    alias_map[target_alias.upper()] = normalized_default
                default_table = normalized_default
            else:
                default_table = ""
        else:
            statement_tables = {
                table_name.upper()
                for table_name in alias_map.values()
                if table_name.upper() not in {"DUAL", "TABLE"}
            }
            default_table = next(iter(statement_tables)) if len(statement_tables) == 1 else ""

        for clause_text in extract_predicate_clauses(statement_text):
            extract_clause_columns(clause_text, alias_map, default_table)

    for match in re.finditer(r"\bselect\b[\s\S]*?;", block_text, flags=re.IGNORECASE):
        register_statement(match.group(0))

    statement_patterns = (
        re.compile(
            r"\bupdate\s+([`\"\w$#\.]+)(?:\s+(?:as\s+)?([A-Za-z_][\w$#]*))?\s+set\b[\s\S]*?;",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"\bdelete\s+from\s+([`\"\w$#\.]+)(?:\s+(?:as\s+)?([A-Za-z_][\w$#]*))?[\s\S]*?;",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"\bmerge\s+into\s+([`\"\w$#\.]+)(?:\s+(?:as\s+)?([A-Za-z_][\w$#]*))?[\s\S]*?;",
            flags=re.IGNORECASE,
        ),
    )
    for pattern in statement_patterns:
        for match in pattern.finditer(block_text):
            register_statement(
                match.group(0),
                default_table=match.group(1),
                target_alias=match.group(2) or "",
            )

    return {table: sorted(columns) for table, columns in lookup_keys.items()}


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
    declaration_section = _extract_declaration_section(block_text)

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


def _extract_declaration_section(block_text: str) -> str:
    header_end = re.search(r"\b(?:is|as)\b", block_text, flags=re.IGNORECASE)
    if not header_end:
        return ""
    remainder = block_text[header_end.end() :]
    begin_match = re.search(r"\bbegin\b", remainder, flags=re.IGNORECASE)
    return remainder[: begin_match.start()] if begin_match else remainder


def _extract_collection_definitions(
    block_text: str,
    local_variables: Sequence[Dict[str, str]],
) -> Dict[str, Any]:
    declaration_section = _extract_declaration_section(block_text)
    type_definitions: Dict[str, Dict[str, Any]] = {}
    type_pattern = re.compile(
        r"\btype\s+([A-Za-z_][\w$#]*)\s+is\s+table\s+of\s+(.+?)(?:\s+index\s+by\s+(.+?))?\s*;",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in type_pattern.finditer(declaration_section):
        type_name = _normalize_identifier(match.group(1)).upper()
        element_type = _normalize_statement_text(match.group(2))
        index_by = _normalize_statement_text(match.group(3)) if match.group(3) else ""
        source_table = ""
        rowtype_match = re.search(r"([`\"\w$#\.]+)\s*%ROWTYPE", element_type, flags=re.IGNORECASE)
        if rowtype_match:
            source_table = _normalize_identifier(rowtype_match.group(1)).upper()
        type_definitions[type_name] = {
            "type_name": type_name,
            "element_type": element_type.upper(),
            "index_by": index_by.upper(),
            "source_table": source_table,
        }

    collection_variables: Dict[str, Dict[str, Any]] = {}
    for variable in local_variables:
        variable_name = variable.get("name", "")
        declared_type = variable.get("type", "").upper()
        if not variable_name:
            continue
        metadata = type_definitions.get(declared_type)
        if metadata:
            collection_variables[variable_name.upper()] = {
                "name": variable_name,
                "declared_type": declared_type,
                **metadata,
            }
            continue
        if re.search(r"(?:ODCI\w+LIST|\bTABLE\b|\bARRAY\b|\bLIST\b)", declared_type, flags=re.IGNORECASE):
            collection_variables[variable_name.upper()] = {
                "name": variable_name,
                "declared_type": declared_type,
                "type_name": declared_type,
                "element_type": declared_type,
                "index_by": "",
                "source_table": "",
            }

    return {
        "type_definitions": list(type_definitions.values()),
        "variables": collection_variables,
    }


def _extract_cursor_definitions(block_text: str) -> List[Dict[str, Any]]:
    declaration_section = _extract_declaration_section(block_text)
    cursor_pattern = re.compile(
        r"\bcursor\s+([A-Za-z_][\w$#]*)\s+is\s+(select\b.*?);",
        flags=re.IGNORECASE | re.DOTALL,
    )
    cursors: List[Dict[str, Any]] = []
    for match in cursor_pattern.finditer(declaration_section):
        cursor_name = _normalize_identifier(match.group(1))
        statement = _normalize_statement_text(match.group(2))
        tables: List[str] = []
        for table_match in re.finditer(r"\b(?:from|join)\s+([`\"\w$#\.]+)", match.group(2), flags=re.IGNORECASE):
            table_name = _normalize_identifier(table_match.group(1)).upper()
            if table_name not in {"DUAL", "TABLE"} and table_name not in tables:
                tables.append(table_name)
        locking_match = re.search(
            r"\bfor\s+update(?:\s+of\s+[\w\s,.$#\"]+)?(?:\s+skip\s+locked)?",
            match.group(2),
            flags=re.IGNORECASE,
        )
        cursors.append(
            {
                "name": cursor_name,
                "statement": statement,
                "tables": tables,
                "locking": _normalize_statement_text(locking_match.group(0)).upper() if locking_match else "",
            }
        )
    return cursors


def _normalize_statement_text(statement: str) -> str:
    return " ".join(statement.strip().rstrip(";").split())


def _format_source_reference(table_name: str, column_name: str) -> str:
    if table_name and column_name:
        return f"{table_name.lower()}.{column_name.lower()}"
    if column_name:
        return column_name.lower()
    return table_name.lower() if table_name else ""


def _extract_aggregate_expression_metadata(
    expression: str,
    alias_map: Dict[str, str],
    default_table: str,
) -> Dict[str, str]:
    match = re.search(
        r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(\s*(?:DISTINCT\s+)?(.*?)\s*\)",
        expression,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return {}

    function_name = match.group(1).upper()
    raw_argument = _normalize_statement_text(match.group(2))
    argument = raw_argument.strip()
    source_table = default_table.upper() if default_table else ""
    source_column = ""

    if argument == "*":
        source_column = "*"
    else:
        qualifier_match = re.search(
            r"([A-Za-z_][\w$#]*)\s*\.\s*([A-Za-z_][\w$#*]*)",
            argument,
            flags=re.IGNORECASE,
        )
        if qualifier_match:
            alias = qualifier_match.group(1).upper()
            source_table = alias_map.get(alias, alias).upper()
            source_column = _normalize_identifier(qualifier_match.group(2)).upper()
        else:
            source_column = _normalize_identifier(argument).upper()

    return {
        "function": function_name,
        "source_table": source_table,
        "source_column": source_column,
        "source": _format_source_reference(source_table, source_column),
    }


def _build_variable_type_index(symbols: Sequence[Dict[str, str]]) -> Dict[str, str]:
    return {
        symbol.get("name", "").upper(): symbol.get("type", "")
        for symbol in symbols
        if symbol.get("name")
    }


def _find_variable_usage_after(block_text: str, variable_name: str, position: int) -> bool:
    remaining = block_text[position:]
    assignment_pattern = re.compile(
        rf"(?<![\w$#]){re.escape(variable_name)}(?![\w$#])\s*:=\s*.*?;",
        flags=re.IGNORECASE | re.DOTALL,
    )
    select_into_pattern = re.compile(
        rf"\binto\s+{re.escape(variable_name)}\b",
        flags=re.IGNORECASE,
    )
    sanitized = assignment_pattern.sub(" ", remaining)
    sanitized = select_into_pattern.sub(" ", sanitized)
    usage_pattern = re.compile(
        rf"(?<![\w$#]){re.escape(variable_name)}(?![\w$#])",
        flags=re.IGNORECASE,
    )
    return bool(usage_pattern.search(sanitized))


def _classify_select_semantic_type(column_expr: str) -> str:
    if re.search(r"\bcount\s*\(", column_expr, flags=re.IGNORECASE):
        return "existence_flag"
    return "lookup_value"


def _select_into_has_row_risk(columns: Sequence[str], statement: str) -> bool:
    statement_upper = statement.upper()
    aggregate_only = bool(columns) and all(
        re.search(r"^\s*(COUNT|SUM|AVG|MIN|MAX)\s*\(", column, flags=re.IGNORECASE)
        for column in columns
    )
    return not (aggregate_only and " GROUP BY " not in statement_upper)


def _classify_assignment_semantic_type(expression: str) -> str:
    if re.search(r"\bcount\s*\(", expression, flags=re.IGNORECASE):
        return "existence_flag"
    return "computed_value"


def _semantic_priority(semantic_type: str) -> int:
    priorities = {
        "existence_flag": 3,
        "lookup_value": 2,
        "computed_value": 1,
    }
    return priorities.get(semantic_type, 0)


def _extract_select_into_assignments(block_text: str) -> List[Dict[str, Any]]:
    assignments: List[Dict[str, Any]] = []
    statement_pattern = re.compile(r"\bselect\b[\s\S]*?;", flags=re.IGNORECASE)
    select_into_pattern = re.compile(
        r"\bselect\s+(?P<select>.*?)\s+into\s+(?P<into>.*?)\s+from\s+(?P<table>[`\"\w$#\.]+)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for stmt_match in statement_pattern.finditer(block_text):
        statement_text = stmt_match.group(0)
        parsed = select_into_pattern.search(statement_text)
        if not parsed:
            continue
        statement = _normalize_statement_text(statement_text)
        aliases = _extract_table_aliases(statement_text)
        columns = [token.strip() for token in _split_top_level_csv(parsed.group("select"))]
        variables = [token.strip() for token in _split_top_level_csv(parsed.group("into"))]
        table = _normalize_identifier(parsed.group("table")).upper()
        row_risk = _select_into_has_row_risk(columns, statement)
        for column, variable in zip(columns, variables):
            column_expr = column.strip()
            source_table = table
            if "." in column_expr:
                prefix = column_expr.split(".", 1)[0].strip('"`').upper()
                source_table = aliases.get(prefix, table)
            source_column = column_expr.split(".")[-1].strip('"`').upper()
            variable_name = _normalize_identifier(variable)
            semantic_type = _classify_select_semantic_type(column_expr)
            aggregate = _extract_aggregate_expression_metadata(column_expr, aliases, table)
            if aggregate.get("source_table"):
                source_table = aggregate.get("source_table", source_table)
            if aggregate.get("source_column"):
                source_column = aggregate.get("source_column", source_column)
            assignments.append(
                {
                    "variable": variable_name,
                    "source": "SELECT INTO",
                    "statement": statement,
                    "source_table": source_table,
                    "source_column": source_column,
                    "column_expression": _normalize_statement_text(column_expr),
                    "aggregation_function": aggregate.get("function", ""),
                    "aggregation_source": aggregate.get("source", ""),
                    "semantic_type": semantic_type,
                    "used": _find_variable_usage_after(block_text, variable_name, stmt_match.end()),
                    "row_risk": row_risk,
                    "start": stmt_match.start(),
                    "end": stmt_match.end(),
                }
            )
    return assignments


def _extract_scalar_assignments(
    block_text: str,
    known_symbol_names: Sequence[str],
) -> List[Dict[str, Any]]:
    known = {name.upper() for name in known_symbol_names if name}
    assignments: List[Dict[str, Any]] = []
    assignment_pattern = re.compile(
        r'(?<![\w$#])(?P<lhs>[A-Za-z_][\w$#]*)\s*:=\s*(?P<rhs>.*?);',
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in assignment_pattern.finditer(block_text):
        variable_name = _normalize_identifier(match.group("lhs"))
        if variable_name.upper() not in known:
            continue
        expression = _normalize_statement_text(match.group("rhs"))
        assignments.append(
            {
                "variable": variable_name,
                "source": ":=",
                "statement": f"{variable_name} := {expression}",
                "expression": expression,
                "semantic_type": _classify_assignment_semantic_type(expression),
                "used": _find_variable_usage_after(block_text, variable_name, match.end()),
                "start": match.start(),
                "end": match.end(),
            }
        )
    return assignments


def _classify_rule_type(condition: str, action: str) -> str:
    action_upper = action.upper()
    condition_upper = condition.upper()
    if "DELETE" in action_upper:
        return "conditional_delete"
    if "INSERT" in action_upper and (
        "COUNT" in condition_upper or re.search(r"=\s*0\b", condition) or "NOT EXISTS" in condition_upper
    ):
        return "existence_insert"
    if "UPDATE" in action_upper and (
        "COUNT" in condition_upper or re.search(r">\s*0\b", condition) or "EXISTS" in condition_upper
    ):
        return "existence_update"
    return "conditional_action"


def _extract_business_rules(block_text: str) -> List[Dict[str, Any]]:
    def summarize_action(action_block: str) -> str:
        matches = re.findall(r"\b(insert|update|delete|select)\b", action_block, flags=re.IGNORECASE)
        if matches:
            ordered = list(dict.fromkeys(item.upper() for item in matches))
            return ", ".join(ordered)
        return " ".join(action_block.split())[:200]

    def build_rule(condition: str, action: str) -> Dict[str, Any]:
        rule_type = _classify_rule_type(condition, action)
        rule: Dict[str, Any] = {
            "condition": condition,
            "action": action,
            "true_action": action,
            "false_action": "",
            "type": rule_type,
        }
        if rule_type == "conditional_delete":
            rule["pattern"] = "conditional_delete"
            rule["severity"] = "high"
        return rule

    rules: List[Dict[str, Any]] = []
    block_pattern = re.compile(
        r"\bif\s+(.*?)\s+then\s+(.*?)\bend\s+if\b\s*;",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in block_pattern.finditer(block_text):
        primary_condition = " ".join(match.group(1).split())
        body = match.group(2)

        split_points: List[Tuple[str, int, int]] = []
        for elsif_match in re.finditer(r"\belsif\s+(.*?)\s+then\b", body, flags=re.IGNORECASE | re.DOTALL):
            split_points.append(("ELSIF", elsif_match.start(), elsif_match.end()))
        else_match = re.search(r"\belse\b", body, flags=re.IGNORECASE)
        if else_match:
            split_points.append(("ELSE", else_match.start(), else_match.end()))
        split_points.sort(key=lambda item: item[1])

        true_block = body if not split_points else body[: split_points[0][1]]
        rules.append(
            build_rule(
                primary_condition,
                summarize_action(true_block),
            )
        )

        elsif_pattern = re.compile(
            r"\belsif\s+(.*?)\s+then\s+(.*?)(?=\belsif\b|\belse\b|$)",
            flags=re.IGNORECASE | re.DOTALL,
        )
        else_block = ""
        if else_match:
            else_block = body[else_match.end() :]
        for elsif_match in elsif_pattern.finditer(body):
            rules.append(
                build_rule(
                    " ".join(elsif_match.group(1).split()),
                    summarize_action(elsif_match.group(2)),
                )
            )
        if else_block.strip():
            rules.append(
                build_rule(
                    "ELSE",
                    summarize_action(else_block),
                )
            )

    return rules


def _canonical_identifier(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", name).upper()


def _looks_like_id_identifier(name: str) -> bool:
    upper_name = name.upper()
    tokens = [token for token in re.split(r"[_\W]+", upper_name) if token]
    return "ID" in tokens or upper_name.endswith("ID")


def _extract_data_flow(block_text: str) -> List[Dict[str, Any]]:
    flows: List[Dict[str, Any]] = []
    for assignment in _extract_select_into_assignments(block_text):
        flows.append(
            {
                "variable": assignment["variable"],
                "source_table": assignment["source_table"],
                "source_column": assignment["source_column"],
                "source": f"{assignment['source_table']}.{assignment['source_column']}",
                "used": assignment["used"],
                "semantic_type": assignment["semantic_type"],
            }
        )
    return flows


def _extract_unused_variables(
    local_variables: Sequence[Dict[str, str]],
    parameters: Sequence[Dict[str, str]],
    data_flow: Sequence[Dict[str, Any]],
    assignments: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, str]]:
    variable_names: Dict[str, str] = {
        item.get("name", "").upper(): item.get("name", "")
        for item in [*local_variables, *parameters]
        if item.get("name")
    }
    variable_types: Dict[str, str] = {
        item.get("name", "").upper(): item.get("type", "")
        for item in [*local_variables, *parameters]
        if item.get("name")
    }
    usage_by_variable: Dict[str, Dict[str, Any]] = {}
    candidate_assignments = list(assignments or [])
    if not candidate_assignments:
        candidate_assignments = [
            {
                "variable": flow.get("variable", ""),
                "source": "SELECT INTO",
                "semantic_type": flow.get("semantic_type", ""),
                "used": flow.get("used", False),
                "end": 0,
            }
            for flow in data_flow
        ]
    for event in candidate_assignments:
        variable_name = event.get("variable", "").upper()
        if not variable_name:
            continue
        current = usage_by_variable.get(variable_name)
        if current and current.get("end", -1) > event.get("end", -1):
            continue
        usage_by_variable[variable_name] = event

    unused: List[Dict[str, str]] = []
    for variable_name, event in sorted(usage_by_variable.items()):
        if event.get("used"):
            continue
        unused.append(
            {
                "name": variable_names.get(variable_name, variable_name),
                "type": variable_types.get(variable_name, ""),
                "reason": "value assigned but never used",
                "source": event.get("source", ""),
            }
        )
    return unused


def _dedupe_relationships(relationships: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: Set[Tuple[str, str, str, str]] = set()
    deduped: List[Dict[str, str]] = []
    for rel in relationships:
        key = (
            rel.get("source_table", ""),
            rel.get("source_column", ""),
            rel.get("target_table", ""),
            rel.get("target_column", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(rel))
    return deduped


def _filter_relationships_for_tables(
    relationships: Sequence[Dict[str, str]],
    tables_used: Sequence[str],
) -> List[Dict[str, str]]:
    table_set = {table.upper() for table in tables_used}
    return [
        rel
        for rel in relationships
        if rel.get("source_table", "").upper() in table_set or rel.get("target_table", "").upper() in table_set
    ]


def _extract_sequence_dependencies(block_text: str, sequence_names: Sequence[str]) -> List[str]:
    known_sequences = {name.upper() for name in sequence_names}
    found: Set[str] = set()
    for match in re.finditer(r"\b([A-Za-z_][\w$#]*)\.(?:nextval|currval)\b", block_text, flags=re.IGNORECASE):
        sequence_name = _normalize_identifier(match.group(1)).upper()
        if not known_sequences or sequence_name in known_sequences:
            found.add(sequence_name)
    return sorted(found)


def _build_dependencies(
    tables_used: Sequence[str],
    sequence_dependencies: Sequence[str],
) -> List[str]:
    return sorted({*tables_used, *sequence_dependencies})


def _clean_dependencies(
    tables_used: Sequence[str],
    sequence_dependencies: Sequence[str],
    known_tables: Sequence[str],
    known_sequences: Sequence[str],
) -> List[str]:
    table_set = {table.upper() for table in known_tables}
    sequence_set = {sequence.upper() for sequence in known_sequences}
    cleaned: Set[str] = set()
    cleaned.update(table.upper() for table in tables_used if table.upper() in table_set)
    cleaned.update(sequence.upper() for sequence in sequence_dependencies if sequence.upper() in sequence_set)
    return sorted(cleaned)


def _merge_bulk_operations_into_operations(
    operations_by_table: Dict[str, List[str]],
    bulk_operations: Sequence[Dict[str, Any]],
) -> Dict[str, List[str]]:
    merged: Dict[str, Set[str]] = {
        table.upper(): {operation.upper() for operation in operations}
        for table, operations in operations_by_table.items()
    }
    for operation in bulk_operations:
        op_type = str(operation.get("type", "")).upper()
        if op_type == "BULK_COLLECT":
            table_name = str(operation.get("source", "")).upper()
            if table_name:
                merged.setdefault(table_name, set()).add("SELECT")
        elif op_type == "FORALL":
            table_name = str(operation.get("table", "")).upper()
            action = str(operation.get("operation", "")).upper()
            if table_name and action:
                merged.setdefault(table_name, set()).add(action)
    return {table: sorted(operations) for table, operations in merged.items()}


def _synchronize_tables_used(
    tables_used: Sequence[str],
    operations_by_table: Dict[str, List[str]],
) -> List[str]:
    normalized = {table.upper() for table in tables_used}
    normalized.update(table.upper() for table in operations_by_table)
    return sorted(normalized)


def _extract_exceptions(block_text: str) -> List[str]:
    found: Set[str] = set()
    for match in re.finditer(r"\bwhen\s+([A-Za-z_][\w$#]*)\s+then\b", block_text, flags=re.IGNORECASE):
        candidate = match.group(1).upper()
        if candidate in TABLE_NAME_BLOCKLIST:
            continue
        found.add(candidate)
    for match in re.finditer(r"\b([A-Za-z_][\w$#]*)\s+exception\s*;", block_text, flags=re.IGNORECASE):
        found.add(match.group(1).upper())
    return sorted(found)


def _extend_exceptions_with_select_into_risks(
    exceptions: Sequence[str],
    data_flow: Sequence[Dict[str, Any]],
) -> List[str]:
    found = {item.upper() for item in exceptions}
    if any(item.get("row_risk", True) for item in data_flow):
        found.update({"NO_DATA_FOUND", "TOO_MANY_ROWS"})
    return sorted(found)


def _extract_procedure_calls(
    block_text: str,
    current_object: str,
    known_tables: Optional[Sequence[str]] = None,
    known_symbols: Optional[Sequence[str]] = None,
) -> List[str]:
    calls: Set[str] = set()
    table_names = {table.upper() for table in (known_tables or [])}
    symbol_names = {symbol.upper() for symbol in (known_symbols or [])}
    for match in re.finditer(r"\b([A-Za-z_][\w$#]*)\s*\(", block_text):
        call_name = match.group(1)
        lowered = call_name.lower()
        upper_name = call_name.upper()
        if lowered in KEYWORD_BLOCKLIST:
            continue
        if lowered == current_object.lower():
            continue
        if upper_name in TYPE_BLOCKLIST or upper_name in table_names or upper_name in symbol_names:
            continue
        prefix = block_text[max(0, match.start() - 32) : match.start()].lower()
        if re.search(r"\b(insert\s+into|update|from|join|delete\s+from|table|references)\s*$", prefix):
            continue
        calls.add(upper_name)
    return sorted(calls)


def _complexity_metrics(block_text: str) -> Dict[str, int]:
    non_empty_lines = [line for line in block_text.splitlines() if line.strip()]
    matched_spans: List[Tuple[int, int]] = []
    executable_match = re.search(r"\bbegin\b([\s\S]*)$", block_text, flags=re.IGNORECASE)
    executable_section = executable_match.group(1) if executable_match else block_text

    def count_pattern(pattern: str) -> int:
        count = 0
        for match in re.finditer(pattern, block_text, flags=re.IGNORECASE | re.DOTALL):
            matched_spans.append(match.span())
            count += 1
        return count

    number_of_loops = 0
    number_of_loops += count_pattern(r"\bfor\s+[A-Za-z_][\w$#]*\s+in\b.*?\bloop\b")
    number_of_loops += count_pattern(r"\bwhile\b.*?\bloop\b")
    number_of_loops += count_pattern(r"\bforall\s+[A-Za-z_][\w$#]*\s+in\b")

    for match in re.finditer(r"\bloop\b", block_text, flags=re.IGNORECASE):
        start, _ = match.span()
        prefix = block_text[max(0, start - 8) : start].lower()
        if "end " in prefix:
            continue
        if any(span_start <= start < span_end for span_start, span_end in matched_spans):
            continue
        number_of_loops += 1

    number_of_conditions = 0
    for match in re.finditer(r"\b(?:if|elsif)\s+(.*?)\s+then\b", executable_section, flags=re.IGNORECASE | re.DOTALL):
        condition = _normalize_statement_text(match.group(1))
        if not condition:
            continue
        boolean_branches = len(re.findall(r"\b(?:and|or)\b", condition, flags=re.IGNORECASE))
        number_of_conditions += 1 + boolean_branches
    number_of_conditions += len(re.findall(r"\bcase\b", executable_section, flags=re.IGNORECASE))

    nesting_depth = 0
    max_nesting_depth = 0
    token_pattern = re.compile(
        r"\b(begin|if|loop|case|end\s+if|end\s+loop|end\s+case|end)\b",
        flags=re.IGNORECASE,
    )
    for token_match in token_pattern.finditer(block_text):
        token = _normalize_statement_text(token_match.group(1)).upper()
        if token in {"BEGIN", "IF", "LOOP", "CASE"}:
            nesting_depth += 1
            max_nesting_depth = max(max_nesting_depth, nesting_depth)
        elif token in {"END IF", "END LOOP", "END CASE", "END"}:
            nesting_depth = max(0, nesting_depth - 1)

    return {
        "linesOfCode": len(non_empty_lines),
        "numberOfQueries": len(
            re.findall(r"\b(?:select|insert|update|delete|merge)\b", block_text, flags=re.IGNORECASE)
        ),
        "numberOfConditions": number_of_conditions,
        "numberOfLoops": number_of_loops,
        "nestedBlocks": max(max_nesting_depth - 1, 0),
        "maxNestingDepth": max_nesting_depth,
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


def _extract_insert_statements(block_text: str) -> List[Dict[str, Any]]:
    statements: List[Dict[str, Any]] = []
    insert_pattern = re.compile(
        r"\binsert\s+into\s+([`\"\w$#\.]+)\s*\((.*?)\)\s*values\s*\((.*?)\)\s*;",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in insert_pattern.finditer(block_text):
        table_name = _normalize_identifier(match.group(1)).upper()
        columns = [_normalize_identifier(token).upper() for token in _split_top_level_csv(match.group(2))]
        values = [token.strip() for token in _split_top_level_csv(match.group(3))]
        statements.append(
            {
                "table": table_name,
                "columns": columns,
                "values": values,
                "statement": _normalize_statement_text(match.group(0)),
            }
        )
    return statements


def detect_bulk_collect(code: str) -> List[Dict[str, Any]]:
    bulk_collects: List[Dict[str, Any]] = []
    cursor_lookup = {
        cursor.get("name", "").upper(): cursor
        for cursor in _extract_cursor_definitions(code)
    }

    select_bulk_pattern = re.compile(
        r"\bselect\b.*?\bbulk\s+collect\s+into\s+([A-Za-z_][\w$#]*)(?:\s*,\s*[A-Za-z_][\w$#]*)*\s+\bfrom\s+([`\"\w$#\.]+).*?;",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in select_bulk_pattern.finditer(code):
        target = _normalize_identifier(match.group(1))
        source = _normalize_identifier(match.group(2)).upper()
        bulk_collects.append(
            {
                "type": "BULK_COLLECT",
                "cursor": "",
                "target": target,
                "limit": "",
                "batch_size": "",
                "source": source,
            }
        )

    fetch_bulk_pattern = re.compile(
        r"\bfetch\s+([A-Za-z_][\w$#]*)\s+bulk\s+collect\s+into\s+([A-Za-z_][\w$#]*)(?:\s*,\s*[A-Za-z_][\w$#]*)*(?:\s+limit\s+(.+?))?\s*;",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in fetch_bulk_pattern.finditer(code):
        cursor_name = _normalize_identifier(match.group(1))
        target = _normalize_identifier(match.group(2))
        limit_value = _normalize_statement_text(match.group(3)) if match.group(3) else ""
        cursor_meta = cursor_lookup.get(cursor_name.upper(), {})
        cursor_tables = cursor_meta.get("tables") or []
        bulk_collects.append(
            {
                "type": "BULK_COLLECT",
                "cursor": cursor_name,
                "target": target,
                "limit": limit_value,
                "batch_size": limit_value,
                "source": cursor_tables[0] if cursor_tables else "",
            }
        )

    return bulk_collects


def detect_forall(code: str) -> List[Dict[str, Any]]:
    forall_operations: List[Dict[str, Any]] = []
    forall_pattern = re.compile(
        r"\bforall\s+([A-Za-z_][\w$#]*)\s+in\s+.*?(save\s+exceptions\s+)?(insert\s+into|update|delete\s+from|merge\s+into)\s+([`\"\w$#\.]+).*?;",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in forall_pattern.finditer(code):
        operation_keyword = match.group(3).upper()
        operation = operation_keyword.split()[0]
        forall_operations.append(
            {
                "type": "FORALL",
                "operation": operation,
                "table": _normalize_identifier(match.group(4)).upper(),
                "save_exceptions": bool(match.group(2)),
            }
        )
    return forall_operations


def detect_cursor(code: str) -> Dict[str, Any]:
    cursor_definitions = _extract_cursor_definitions(code)
    if cursor_definitions:
        locking_values = [cursor.get("locking", "") for cursor in cursor_definitions if cursor.get("locking")]
        locking = locking_values[0] if locking_values else ""
        result: Dict[str, Any] = {
            "type": "explicit_cursor",
            "locking": locking,
        }
        if locking:
            result["purpose"] = "concurrent-safe processing" if "SKIP LOCKED" in locking else "cursor-driven processing"
        return result

    locking_match = re.search(
        r"\bfor\s+update(?:\s+skip\s+locked)?",
        code,
        flags=re.IGNORECASE,
    )
    if not locking_match:
        return {}
    locking = _normalize_statement_text(locking_match.group(0)).upper()
    return {
        "type": "explicit_cursor",
        "locking": locking,
        "purpose": "concurrent-safe processing" if "SKIP LOCKED" in locking else "locked row processing",
    }


def detect_transaction(code: str) -> Dict[str, Any]:
    return {
        "has_savepoint": bool(re.search(r"\bsavepoint\b", code, flags=re.IGNORECASE)),
        "has_partial_rollback": bool(re.search(r"\brollback\s+to(?:\s+savepoint)?\b", code, flags=re.IGNORECASE)),
        "has_commit": bool(re.search(r"\bcommit\b", code, flags=re.IGNORECASE)),
        "has_rollback": bool(re.search(r"\brollback\b", code, flags=re.IGNORECASE)),
    }


def detect_retry(code: str) -> Dict[str, Any]:
    goto_match = re.search(r"\bgoto\s+([A-Za-z_][\w$#]*)\s*;", code, flags=re.IGNORECASE)
    if not goto_match:
        return {
            "uses_goto": False,
            "pattern": "",
        }
    return {
        "uses_goto": True,
        "pattern": _normalize_identifier(goto_match.group(1)),
    }


def detect_collections(code: str) -> List[Dict[str, Any]]:
    local_variables = _extract_local_variables(code)
    collection_definitions = _extract_collection_definitions(code, local_variables)
    collections: List[Dict[str, Any]] = []
    for metadata in collection_definitions.get("variables", {}).values():
        collections.append(
            {
                "name": metadata.get("name", ""),
                "type": "collection",
                "declared_type": metadata.get("declared_type", ""),
                "element_type": metadata.get("element_type", ""),
                "index_by": metadata.get("index_by", ""),
                "source_table": metadata.get("source_table", ""),
            }
        )
    return collections


def detect_bulk_operations(ast: Dict[str, Any]) -> List[Dict[str, Any]]:
    block_text = ast.get("block_text", "")
    return [*detect_bulk_collect(block_text), *detect_forall(block_text)]


def detect_cursor_patterns(ast: Dict[str, Any]) -> Dict[str, Any]:
    return detect_cursor(ast.get("block_text", ""))


def detect_retry_logic(ast: Dict[str, Any]) -> Dict[str, Any]:
    block_text = ast.get("block_text", "")
    retry_summary = detect_retry(block_text)
    if not retry_summary.get("uses_goto"):
        return {"enabled": False, "max_attempts": None, "pattern": ""}

    labels = {
        _normalize_identifier(match.group(1))
        for match in re.finditer(r"<<\s*([A-Za-z_][\w$#]*)\s*>>", block_text, flags=re.IGNORECASE)
    }
    goto_labels = [
        _normalize_identifier(match.group(1))
        for match in re.finditer(r"\bgoto\s+([A-Za-z_][\w$#]*)\s*;", block_text, flags=re.IGNORECASE)
    ]
    max_attempts: Optional[int] = None
    for label in goto_labels:
        retry_pattern = re.compile(
            rf"\bif\s+.*?(?:<|<=)\s*(\d+)\s+then\b.*?\bgoto\s+{re.escape(label)}\s*;",
            flags=re.IGNORECASE | re.DOTALL,
        )
        match = retry_pattern.search(block_text)
        if match:
            max_attempts = int(match.group(1))
            break

    target_label = next((label for label in goto_labels if label in labels), goto_labels[0])
    return {
        "enabled": True,
        "max_attempts": max_attempts,
        "pattern": f"GOTO {target_label}",
        "uses_goto": True,
    }


def detect_bulk_exception_handling(ast: Dict[str, Any]) -> Dict[str, Any]:
    block_text = ast.get("block_text", "")
    bulk_operations = ast.get("bulk_operations", [])
    has_save_exceptions = any(operation.get("save_exceptions") for operation in bulk_operations)
    if not has_save_exceptions and not re.search(r"\bSQL%BULK_EXCEPTIONS\b", block_text, flags=re.IGNORECASE):
        return {}
    return {
        "type": "bulk_exception_handling",
        "mechanism": "SQL%BULK_EXCEPTIONS",
        "behavior": "continue_on_error",
    }


def detect_transaction_patterns(ast: Dict[str, Any]) -> Dict[str, Any]:
    block_text = ast.get("block_text", "")
    base_transaction = _build_transaction_summary(ast.get("operations", {}))
    transaction_flags = detect_transaction(block_text)
    features: List[str] = []

    loop_commit_pattern = re.compile(
        r"\b(?:for\s+\w+\s+in\b.*?\bloop\b|\bwhile\b.*?\bloop\b|\bloop\b).*?\bcommit\b.*?\bend\s+loop\b",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if loop_commit_pattern.search(block_text):
        features.append("COMMIT inside loop")
    elif re.search(r"\bcommit\b", block_text, flags=re.IGNORECASE):
        features.append("COMMIT")

    if re.search(r"\bsavepoint\b", block_text, flags=re.IGNORECASE):
        features.append("SAVEPOINT")
    if re.search(r"\brollback\s+to(?:\s+savepoint)?\b", block_text, flags=re.IGNORECASE):
        features.append("ROLLBACK TO SAVEPOINT")
        features.append("partial rollback")
    elif re.search(r"\brollback\b", block_text, flags=re.IGNORECASE):
        features.append("ROLLBACK")

    features = list(dict.fromkeys(features))
    has_savepoint = any(feature in {"SAVEPOINT", "ROLLBACK TO SAVEPOINT", "partial rollback"} for feature in features)
    risk = "high" if has_savepoint or "COMMIT inside loop" in features else ("medium" if features else "low")

    if has_savepoint:
        tx_type = "batch_with_savepoint"
        reason = "batch processing with explicit savepoint control"
    elif base_transaction.get("required"):
        tx_type = base_transaction.get("type", "multi_step_mutation")
        reason = "multiple dependent DML operations"
    elif features:
        tx_type = "explicit_transaction_control"
        reason = "explicit transaction control statements detected"
    else:
        tx_type = base_transaction.get("type", "single_step")
        reason = base_transaction.get("reason", "")

    return {
        "required": base_transaction.get("required", False) or bool(features),
        "type": tx_type,
        "reason": reason,
        "features": features,
        "risk": risk,
        **transaction_flags,
    }


def detect_collection_data_flow(ast: Dict[str, Any]) -> List[Dict[str, Any]]:
    block_text = ast.get("block_text", "")
    collection_variables = ast.get("collection_definitions", {}).get("variables", {})
    flows: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str]] = set()

    for operation in ast.get("bulk_operations", []):
        if operation.get("type") != "BULK_COLLECT":
            continue
        target = operation.get("target", "")
        source = operation.get("source", "")
        key = ("bulk_collection", source, target)
        if key in seen:
            continue
        seen.add(key)
        flows.append(
            {
                "type": "bulk_collection",
                "source": source,
                "variable": target,
                "target": target,
            }
        )

    for variable_name, metadata in collection_variables.items():
        collection_name = metadata.get("name", variable_name)
        assignment_pattern = re.compile(
            rf"(?<![\w$#]){re.escape(collection_name)}\s*\([^)]*\)\s*:=|(?<![\w$#]){re.escape(collection_name)}\.(?:extend|trim|delete)\b",
            flags=re.IGNORECASE,
        )
        if assignment_pattern.search(block_text):
            key = ("computed_collection", "", collection_name)
            if key not in seen:
                seen.add(key)
                flows.append(
                    {
                        "type": "computed_collection",
                        "source": "",
                        "variable": collection_name,
                        "target": collection_name,
                    }
                )

    assignment_pattern = re.compile(
        r"([A-Za-z_][\w$#]*)(?:\s*\([^)]*\))?(?:\s*\.\s*[A-Za-z_][\w$#]*)?\s*:=\s*(.*?);",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in assignment_pattern.finditer(block_text):
        target_name = _normalize_identifier(match.group(1))
        if target_name.upper() not in collection_variables:
            continue
        expression = _normalize_statement_text(match.group(2))
        source_match = re.search(
            r"([A-Za-z_][\w$#]*)\s*\([^)]*\)\s*\.\s*([A-Za-z_][\w$#]*)",
            expression,
            flags=re.IGNORECASE,
        )
        source = ""
        if source_match:
            source_collection = _normalize_identifier(source_match.group(1))
            source_field = _normalize_identifier(source_match.group(2)).upper()
            source = f"{source_collection}.{source_field}"
        key = ("computed_collection", source, target_name)
        if key in seen:
            continue
        seen.add(key)
        flows.append(
            {
                "type": "computed_collection",
                "source": source,
                "variable": target_name,
                "target": target_name,
            }
        )

    return flows


def classify_complexity(ast: Dict[str, Any]) -> Dict[str, Any]:
    metrics = _complexity_metrics(ast.get("block_text", ""))
    has_advanced_patterns = bool(
        ast.get("cursor")
        or ast.get("bulk_operations")
        or ast.get("transaction", {}).get("features")
    )
    has_batch_shape = (
        bool(ast.get("bulk_operations"))
        and metrics.get("numberOfLoops", 0) > 0
        and metrics.get("numberOfQueries", 0) >= 4
        and metrics.get("numberOfConditions", 0) >= 3
    )
    if has_batch_shape:
        metrics["classification"] = "high_complexity_batch_processing"
    elif has_advanced_patterns:
        metrics["classification"] = "moderate_complexity_transactional_processing"
    else:
        metrics["classification"] = "standard_procedural_logic"
    metrics["level"] = "high" if has_advanced_patterns else ("medium" if metrics["numberOfQueries"] > 2 else "low")
    metrics["type"] = "enterprise_batch_processing" if has_advanced_patterns else "standard_procedural_logic"
    return metrics


def _build_id_generation_summary(
    input_parameters: Sequence[Dict[str, str]],
    sequence_dependencies: Sequence[str],
    operations_by_table: Dict[str, List[str]],
    table_map: Dict[str, Dict[str, Any]],
    insert_statements: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    insert_tables = [
        table_name
        for table_name, ops in operations_by_table.items()
        if "INSERT" in ops
    ]
    primary_keys = {
        pk
        for table_name in insert_tables
        for pk in table_map.get(table_name, {}).get("primary_keys", [])
    }
    canonical_pks = {_canonical_identifier(pk) for pk in primary_keys if pk}

    input_id_provided = False
    for param in input_parameters:
        param_name = param.get("name", "")
        if not param_name:
            continue
        canonical_param = _canonical_identifier(param_name)
        pk_match = any(
            canonical_param == canonical_pk or canonical_param.endswith(canonical_pk)
            for canonical_pk in canonical_pks
        )
        if (canonical_pks and pk_match) or (not canonical_pks and _looks_like_id_identifier(param_name)):
            input_id_provided = True
            break

    uses_sequence = bool(sequence_dependencies)
    conflict = uses_sequence and input_id_provided
    strategy = "sequence_overrides_input" if conflict else ("sequence_generated" if uses_sequence else "input_parameter")

    if insert_statements and canonical_pks:
        for statement in insert_statements:
            columns = statement.get("columns", [])
            values = statement.get("values", [])
            for column_name, value_expr in zip(columns, values):
                if _canonical_identifier(column_name) not in canonical_pks:
                    continue
                if re.search(r"\b[A-Za-z_][\w$#]*\.nextval\b", value_expr, flags=re.IGNORECASE):
                    uses_sequence = True
                    conflict = input_id_provided
                    strategy = "sequence_overrides_input" if conflict else "sequence_generated"
                    break

    return {
        "uses_sequence": uses_sequence,
        "input_id_provided": input_id_provided,
        "conflict": conflict,
        "pattern": strategy,
        "strategy": strategy,
        "impact": "input parameter ignored" if conflict else "",
        "details": "Input parameter ignored in INSERT" if conflict else "",
    }


def _build_transaction_summary(operations_by_table: Dict[str, List[str]]) -> Dict[str, Any]:
    has_select = any("SELECT" in operations for operations in operations_by_table.values())
    ordered_dml = [
        op
        for op in ("INSERT", "UPDATE", "DELETE")
        if any(op in operations for operations in operations_by_table.values())
    ]
    required = has_select and len(ordered_dml) > 1
    return {
        "required": required,
        "type": "multi_step_mutation" if required else "single_step",
        "reason": "Multiple dependent DML operations" if required else "",
    }


def _validate_sequence_mapping(
    sequence_dependencies: Sequence[str],
    sequence_mapping: Sequence[Dict[str, str]],
    operations_by_table: Dict[str, List[str]],
) -> List[Dict[str, str]]:
    mapping_lookup: Dict[str, Set[str]] = {}
    for mapping in sequence_mapping:
        sequence_name = mapping.get("sequence_name", "").upper()
        mapped_table = mapping.get("mapped_table", "").upper()
        if not sequence_name or not mapped_table:
            continue
        mapping_lookup.setdefault(sequence_name, set()).add(mapped_table)

    insert_tables = {
        table_name.upper()
        for table_name, operations in operations_by_table.items()
        if "INSERT" in operations
    }
    issues: List[Dict[str, str]] = []
    seen_messages: Set[Tuple[str, str]] = set()
    for sequence_name in sequence_dependencies:
        mapped_tables = mapping_lookup.get(sequence_name.upper(), set())
        has_matching_mapping = bool(mapped_tables) and (
            not insert_tables or not mapped_tables.isdisjoint(insert_tables)
        )
        if has_matching_mapping:
            continue
        key = ("sequence_mapping_inconsistency", sequence_name.upper())
        if key in seen_messages:
            continue
        seen_messages.add(key)
        issues.append(
            {
                "type": "sequence_mapping_inconsistency",
                "details": f"Sequence {sequence_name.upper()} used but not mapped to table",
            }
        )
    return issues


def _build_dependency_chains(
    tables_used: Sequence[str],
    relationships: Sequence[Dict[str, str]],
) -> List[str]:
    table_set = {table.upper() for table in tables_used}
    adjacency: Dict[str, Set[str]] = {}
    for relationship in relationships:
        source = relationship.get("source_table", "").upper()
        target = relationship.get("target_table", "").upper()
        if source not in table_set or target not in table_set or source == target:
            continue
        adjacency.setdefault(source, set()).add(target)

    chains: Set[str] = set()

    def walk(node: str, path: List[str]) -> None:
        for target in adjacency.get(node, set()):
            if target in path:
                continue
            next_path = [*path, target]
            if len(next_path) >= 3:
                chains.add(" -> ".join(next_path))
            walk(target, next_path)

    for source in sorted(adjacency):
        walk(source, [source])

    return sorted(chains)


def classify_variable_semantics(ast: Dict[str, Any]) -> List[Dict[str, str]]:
    assignments = ast.get("select_assignments", [])
    semantics_by_variable: Dict[str, Dict[str, str]] = {}
    for assignment in assignments:
        variable_name = assignment.get("variable", "")
        semantic_type = assignment.get("semantic_type", "")
        if not variable_name or not semantic_type:
            continue
        current = semantics_by_variable.get(variable_name.upper())
        if current and _semantic_priority(current.get("type", "")) >= _semantic_priority(semantic_type):
            continue
        semantics_by_variable[variable_name.upper()] = {
            "variable": variable_name,
            "type": semantic_type,
        }
    return list(semantics_by_variable.values())


def enhance_data_flow(ast: Dict[str, Any]) -> List[Dict[str, Any]]:
    semantics = {
        entry.get("variable", "").upper(): entry.get("type", "")
        for entry in classify_variable_semantics(ast)
        if entry.get("variable")
    }
    flows: List[Dict[str, Any]] = []
    for assignment in ast.get("select_assignments", []):
        variable_name = assignment.get("variable", "")
        flows.append(
            {
                "variable": variable_name,
                "source_table": assignment.get("source_table", ""),
                "source_column": assignment.get("source_column", ""),
                "source": f"{assignment.get('source_table', '')}.{assignment.get('source_column', '')}",
                "used": bool(assignment.get("used")),
                "semantic_type": semantics.get(variable_name.upper(), assignment.get("semantic_type", "")),
            }
        )
    return flows


def detect_unused_variables(ast: Dict[str, Any]) -> List[Dict[str, str]]:
    return _extract_unused_variables(
        ast.get("variables", []),
        ast.get("parameters", []),
        ast.get("data_flow", []),
        ast.get("assignments", []),
    )


def detect_exception_sources(ast: Dict[str, Any]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for assignment in ast.get("select_assignments", []):
        if not assignment.get("row_risk", True):
            continue
        sources.append(
            {
                "statement": assignment.get("statement", ""),
                "exceptions": ["NO_DATA_FOUND", "TOO_MANY_ROWS"],
                "certainty": "guaranteed",
                "reason": "SELECT INTO requires exactly one row",
            }
        )
    return sources


def detect_id_generation_conflict(ast: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    table_map = {
        table.get("name", "").upper(): table
        for table in schema.get("tables", [])
        if table.get("name")
    }
    return _build_id_generation_summary(
        ast.get("input_parameters", []),
        ast.get("sequence_dependencies", []),
        ast.get("operations", {}),
        table_map,
        ast.get("insert_statements", []),
    )


def detect_id_conflict(ast: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    return detect_id_generation_conflict(ast, schema)


def detect_transaction(code: str) -> Dict[str, Any]:
    return {
        "has_savepoint": bool(re.search(r"\bsavepoint\b", code, flags=re.IGNORECASE)),
        "has_partial_rollback": bool(re.search(r"\brollback\s+to(?:\s+savepoint)?\b", code, flags=re.IGNORECASE)),
        "has_commit": bool(re.search(r"\bcommit\b", code, flags=re.IGNORECASE)),
        "has_rollback": bool(re.search(r"\brollback\b", code, flags=re.IGNORECASE)),
    }


def detect_logic_gaps(ast: Dict[str, Any]) -> List[Dict[str, str]]:
    semantics = {
        entry.get("variable", "").upper(): entry.get("type", "")
        for entry in ast.get("variable_semantics", [])
        if entry.get("variable")
    }
    issues: List[Dict[str, str]] = []
    for variable in ast.get("unused_variables", []):
        variable_name = variable.get("name", "")
        semantic_type = semantics.get(variable_name.upper(), "")
        if variable.get("source") != "SELECT INTO":
            continue
        if semantic_type == "lookup_value":
            issues.append(
                {
                    "type": "unused_lookup",
                    "details": f"Fetched {variable_name} but not used in logic",
                    "impact": "missing validation logic",
                }
            )
        elif semantic_type == "existence_flag":
            issues.append(
                {
                    "type": "unused_lookup",
                    "details": f"Fetched {variable_name} but not used in logic",
                    "impact": "missing existence check",
                }
            )
    return issues


def detect_upsert_semantics(block_text: str) -> List[Dict[str, Any]]:
    upserts: List[Dict[str, Any]] = []
    merge_pattern = re.compile(r"\bmerge\s+into\s+([`\"\w$#\.]+)([\s\S]*?);", flags=re.IGNORECASE)
    for match in merge_pattern.finditer(block_text):
        table_name = _normalize_identifier(match.group(1)).upper()
        statement_body = match.group(2)
        details: List[str] = []
        if re.search(r"\bwhen\s+not\s+matched\b", statement_body, flags=re.IGNORECASE):
            details.append("INSERT")
        if re.search(r"\bwhen\s+matched\b", statement_body, flags=re.IGNORECASE):
            details.append("UPDATE")
        upserts.append(
            {
                "table": table_name,
                "operation": "UPSERT",
                "type": "upsert_operation",
                "details": details or ["UPDATE", "INSERT"],
            }
        )
    return upserts


def detect_aggregation_semantics(ast: Dict[str, Any]) -> Dict[str, Any]:
    functions: Set[str] = set()
    columns: Set[str] = set()
    for assignment in ast.get("select_assignments", []):
        function_name = str(assignment.get("aggregation_function", "")).upper()
        if not function_name:
            continue
        functions.add(function_name)
        source = str(assignment.get("aggregation_source", "")).strip()
        if source:
            columns.add(source)
    if not functions:
        return {}
    return {
        "type": "aggregation",
        "columns": sorted(columns),
        "functions": sorted(functions),
    }


def _extract_expression_identifiers(expression: str) -> List[str]:
    excluded = {
        *(keyword.upper() for keyword in KEYWORD_BLOCKLIST),
        *(dtype.upper() for dtype in TYPE_BLOCKLIST),
        "NULL",
        "TRUE",
        "FALSE",
        "SYSDATE",
        "SQLERRM",
    }
    names: List[str] = []
    for token in re.findall(r"\b([A-Za-z_][\w$#]*)\b", expression):
        normalized = _normalize_identifier(token)
        upper_name = normalized.upper()
        if upper_name in excluded:
            continue
        names.append(normalized)
    # Preserve declaration order while removing duplicates.
    return list(dict.fromkeys(names))


def detect_derived_value_semantics(ast: Dict[str, Any]) -> List[Dict[str, Any]]:
    derived_values: List[Dict[str, Any]] = []
    for assignment in ast.get("assignments", []):
        if assignment.get("source") != ":=":
            continue
        formula = _normalize_statement_text(assignment.get("expression", ""))
        if not formula or not re.search(r"[+\-*/]", formula):
            continue
        variable_name = assignment.get("variable", "")
        identifiers = _extract_expression_identifiers(formula)
        semantic_signal = f"{variable_name} {formula}".upper()
        financial_markers = ("BALANCE", "AMOUNT", "PAYMENT", "PAYMENTS", "ORDER", "ORDERS", "TOTAL", "PRICE", "CREDIT", "DEBIT")
        semantic_type = (
            "financial_calculation"
            if any(marker in semantic_signal for marker in financial_markers)
            else "derived_calculation"
        )
        derived_values.append(
            {
                "variable": variable_name,
                "type": "derived_value",
                "formula": formula,
                "semantic_type": semantic_type,
                "source_variables": identifiers,
            }
        )
    return derived_values


def build_structured_data_flow_semantics(
    ast: Dict[str, Any],
    derived_values: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    flows: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str]] = set()

    for assignment in ast.get("select_assignments", []):
        operation = assignment.get("aggregation_function", "")
        source = assignment.get("aggregation_source", "")
        if not operation or not source:
            continue
        target = assignment.get("variable", "")
        key = (target, str(source), operation)
        if key in seen:
            continue
        seen.add(key)
        flows.append(
            {
                "target": target,
                "source": source,
                "operation": operation,
            }
        )

    for derived in derived_values:
        formula = derived.get("formula", "")
        operation = "computed"
        if "+" in formula and "-" not in formula:
            operation = "addition"
        elif "-" in formula and "+" not in formula:
            operation = "subtraction"
        elif "*" in formula and "/" not in formula:
            operation = "multiplication"
        elif "/" in formula and "*" not in formula:
            operation = "division"
        source_vars = derived.get("source_variables", [])
        source: Any = source_vars if len(source_vars) != 1 else source_vars[0]
        key = (derived.get("variable", ""), str(source), operation)
        if key in seen:
            continue
        seen.add(key)
        flows.append(
            {
                "target": derived.get("variable", ""),
                "source": source,
                "operation": operation,
            }
        )
    return flows


def _summarize_first_action(action_block: str) -> str:
    for candidate in action_block.split(";"):
        statement = _normalize_statement_text(candidate)
        if statement:
            return statement
    return ""


def detect_validation_rule_semantics(block_text: str) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    if_pattern = re.compile(
        r"\bif\s+(?P<condition>.*?)\s+then\s+(?P<body>.*?)(?=\belsif\b|\belse\b|\bend\s+if\b)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in if_pattern.finditer(block_text):
        condition = _normalize_statement_text(match.group("condition"))
        action = _summarize_first_action(match.group("body"))
        if not condition or not action:
            continue
        rule_type = "validation_rule" if re.search(r"\braise\b", action, flags=re.IGNORECASE) else "business_rule"
        rules.append(
            {
                "type": rule_type,
                "condition": condition,
                "action": action,
            }
        )
    return rules


def detect_conditional_transaction_semantics(block_text: str) -> Dict[str, Any]:
    pattern = re.compile(
        r"\bif\s+(?P<condition>.*?)\s+then\s+(?P<true_block>.*?)(?:\belse\s+(?P<false_block>.*?))?\bend\s+if\s*;",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(block_text):
        true_block = match.group("true_block") or ""
        false_block = match.group("false_block") or ""
        true_has_commit = bool(re.search(r"\bcommit\b", true_block, flags=re.IGNORECASE))
        true_has_rollback = bool(re.search(r"\brollback\b", true_block, flags=re.IGNORECASE))
        false_has_commit = bool(re.search(r"\bcommit\b", false_block, flags=re.IGNORECASE))
        false_has_rollback = bool(re.search(r"\brollback\b", false_block, flags=re.IGNORECASE))
        if (true_has_commit and false_has_rollback) or (true_has_rollback and false_has_commit):
            return {
                "type": "conditional_transaction",
                "strategy": "commit_or_rollback",
                "condition": _normalize_statement_text(match.group("condition")),
            }
    return {}


def detect_cursor_semantics(block_text: str, cursor: Dict[str, Any]) -> Dict[str, Any]:
    locking = str((cursor or {}).get("locking", "")).upper()
    if not locking:
        locking_match = re.search(
            r"\bfor\s+update(?:\s+of\s+[\w\s,.$#\"]+)?(?:\s+skip\s+locked)?",
            block_text,
            flags=re.IGNORECASE,
        )
        locking = _normalize_statement_text(locking_match.group(0)).upper() if locking_match else ""
    if "FOR UPDATE" in locking and "SKIP LOCKED" in locking:
        return {
            "type": "concurrent_processing",
            "strategy": "skip_locked_rows",
            "purpose": "parallel_safe_batch_execution",
        }
    if "FOR UPDATE" in locking:
        return {
            "type": "concurrent_processing",
            "strategy": "row_locking",
            "purpose": "serialized_update_processing",
        }
    return {}


def detect_exception_semantics(block_text: str) -> List[Dict[str, str]]:
    exception_section_match = re.search(
        r"\bexception\b([\s\S]*)$",
        block_text,
        flags=re.IGNORECASE,
    )
    exception_section = exception_section_match.group(1) if exception_section_match else ""
    declared_exceptions = {
        _normalize_identifier(match.group(1)).upper()
        for match in re.finditer(r"\b([A-Za-z_][\w$#]*)\s+exception\s*;", block_text, flags=re.IGNORECASE)
    }
    semantics: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    for match in re.finditer(r"\bwhen\s+([A-Za-z_][\w$#]*)\s+then\b", exception_section, flags=re.IGNORECASE):
        handler_name = _normalize_identifier(match.group(1))
        upper_name = handler_name.upper()
        if upper_name in {"MATCHED", "NOT"}:
            continue
        if upper_name == "OTHERS":
            item = {"type": "system_exception", "name": "OTHERS"}
        elif upper_name in declared_exceptions or upper_name.startswith("E_"):
            item = {"type": "business_exception", "name": handler_name}
        else:
            item = {"type": "system_exception", "name": handler_name}
        key = (item["type"], item["name"].upper())
        if key in seen:
            continue
        seen.add(key)
        semantics.append(item)
    return semantics


def classify_process_semantics(ast: Dict[str, Any], aggregation: Dict[str, Any]) -> Dict[str, str]:
    block_text = ast.get("block_text", "")
    bulk_operations = ast.get("bulk_operations", [])
    has_bulk_collect = any(operation.get("type") == "BULK_COLLECT" for operation in bulk_operations)
    base_complexity = ast.get("complexity") or _complexity_metrics(block_text)
    has_loop = base_complexity.get("numberOfLoops", 0) > 0
    has_aggregation = bool(aggregation.get("functions"))
    tx = ast.get("transaction", {})
    has_commit_rollback = bool(tx.get("has_commit") and tx.get("has_rollback"))
    financial_domain = bool(
        re.search(r"\b(balance|payment|order|amount|reconcile|audit)\b", block_text, flags=re.IGNORECASE)
    )
    if has_bulk_collect and has_loop and has_aggregation and has_commit_rollback:
        return {
            "process_type": "batch_reconciliation",
            "domain": "financial_processing" if financial_domain else "transactional_processing",
        }
    if has_bulk_collect and has_loop:
        return {"process_type": "batch_processing", "domain": "financial_processing" if financial_domain else "data_processing"}
    return {"process_type": "procedural_operation", "domain": "financial_processing" if financial_domain else "general_processing"}


def _build_semantic_intent_summary(semantic_analysis: Dict[str, Any]) -> str:
    process_info = semantic_analysis.get("process_classification", {})
    upsert_operations = semantic_analysis.get("upsert_operations", [])
    aggregation = semantic_analysis.get("aggregation", {})
    transaction_strategy = semantic_analysis.get("transaction_strategy", {})
    cursor_semantics = semantic_analysis.get("cursor_semantics", {})
    validation_rules = semantic_analysis.get("business_rules", [])
    if (
        process_info.get("process_type") == "batch_reconciliation"
        and process_info.get("domain") == "financial_processing"
        and upsert_operations
        and aggregation.get("functions")
        and transaction_strategy.get("type") == "conditional_transaction"
        and cursor_semantics.get("strategy") == "skip_locked_rows"
        and any(rule.get("type") == "validation_rule" for rule in validation_rules)
    ):
        return (
            "This procedure performs financial reconciliation using aggregated order and payment data, "
            "applies validation rules, performs upsert operations, and uses conditional transaction "
            "management with concurrency-safe batch processing."
        )
    return "Semantic intent detected from business rules, data flow, transaction strategy, and persistence patterns."


def build_semantic_analysis(ast: Dict[str, Any]) -> Dict[str, Any]:
    upsert_operations = detect_upsert_semantics(ast.get("block_text", ""))
    aggregation = detect_aggregation_semantics(ast)
    derived_values = detect_derived_value_semantics(ast)
    structured_data_flow = build_structured_data_flow_semantics(ast, derived_values)
    business_rules = detect_validation_rule_semantics(ast.get("block_text", ""))
    transaction_strategy = detect_conditional_transaction_semantics(ast.get("block_text", ""))
    cursor_semantics = detect_cursor_semantics(ast.get("block_text", ""), ast.get("cursor", {}))
    error_handling_semantics = detect_exception_semantics(ast.get("block_text", ""))
    process_classification = classify_process_semantics(ast, aggregation)
    semantic_analysis = {
        "upsert_operations": upsert_operations,
        "aggregation": aggregation,
        "derived_values": derived_values,
        "structured_data_flow": structured_data_flow,
        "business_rules": business_rules,
        "transaction_strategy": transaction_strategy,
        "cursor_semantics": cursor_semantics,
        "error_handling_semantics": error_handling_semantics,
        "process_classification": process_classification,
    }
    semantic_analysis["intent_summary"] = _build_semantic_intent_summary(semantic_analysis)
    return semantic_analysis


def _enhance_business_rules(
    block_text: str,
    base_rules: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    begin_match = re.search(r"\bbegin\b", block_text, flags=re.IGNORECASE)
    executable_section = block_text[begin_match.end() :] if begin_match else block_text

    def normalize_rule_expression(expression: str) -> str:
        collapsed = _normalize_statement_text(expression)
        return re.sub(
            r"([A-Za-z_][\w$#]*)\s*\([^)]*\)\s*\.\s*([A-Za-z_][\w$#]*)",
            lambda match: f"{_normalize_identifier(match.group(1))}.{_normalize_identifier(match.group(2)).upper()}",
            collapsed,
            flags=re.IGNORECASE,
        )

    rules: List[Dict[str, Any]] = [dict(rule) for rule in base_rules]
    seen: Set[Tuple[str, str, str]] = {
        (
            str(rule.get("condition", "")),
            str(rule.get("action", "")),
            str(rule.get("type", "")),
        )
        for rule in rules
    }

    retry_pattern = re.compile(
        r"\bif\s+(.*?)\s+then\b.*?\bgoto\s+([A-Za-z_][\w$#]*)\s*;",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in retry_pattern.finditer(executable_section):
        condition = " ".join(match.group(1).split())
        action = f"RETRY { _normalize_identifier(match.group(2)) }"
        key = (condition, action, "retry_condition")
        if key in seen:
            continue
        seen.add(key)
        rules.append(
            {
                "condition": condition,
                "action": action,
                "true_action": action,
                "false_action": "",
                "type": "retry_condition",
            }
        )

    calc_pattern = re.compile(
        r"([A-Za-z_][\w$#]*(?:\s*\([^)]*\))?(?:\s*\.\s*[A-Za-z_][\w$#]*)?)\s*:=\s*(.*?[+\-*/].*?);",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in calc_pattern.finditer(executable_section):
        target = _normalize_identifier(match.group(1).split("(")[0].split(".")[0])
        expression = normalize_rule_expression(match.group(2))
        action = f"{target} = {expression}"
        key = ("", action, "calculation_logic")
        if key in seen:
            continue
        seen.add(key)
        rules.append(
            {
                "condition": "",
                "action": action,
                "true_action": action,
                "false_action": "",
                "type": "calculation_logic",
            }
        )

    return rules


def build_discovery_model(sql_text: str) -> Dict[str, Any]:
    """Build a full-file discovery model for schema + procedure behavior."""
    cleaned = _prepare_sql_text(sql_text)
    table_defs = _extract_table_definitions(cleaned)
    if not table_defs:
        table_defs = infer_tables_from_dml(cleaned)
    table_map = {table["name"]: table for table in table_defs}
    ddl_columns = {table["name"]: [col["name"] for col in table["columns"]] for table in table_defs}
    relationships = _dedupe_relationships([
        {
            "source_table": table["name"],
            "source_column": fk["source_column"],
            "target_table": fk["target_table"],
            "target_column": fk["target_column"],
        }
        for table in table_defs
        for fk in table["foreign_keys"]
    ] + _extract_alter_table_foreign_keys(cleaned))
    sequence_catalog = _extract_sequence_catalog(cleaned)
    sequence_names = sequence_catalog["sequence_names"]
    objects = _extract_objects(cleaned)
    procedures: List[Dict[str, Any]] = []
    for item in objects:
        params = _extract_parameters(item.block_text)
        parameter_names = [param["name"] for param in params["all"]]
        local_variables = _extract_local_variables(item.block_text)
        collections = detect_collections(item.block_text)
        collection_definitions = _extract_collection_definitions(item.block_text, local_variables)
        cursor_definitions = _extract_cursor_definitions(item.block_text)
        operations_tables = _extract_operations_and_tables(item.block_text)
        tables_used = operations_tables["tables"]
        operations_by_table = _extract_operations_by_table(item.block_text)
        preliminary_ast: Dict[str, Any] = {
            "block_text": item.block_text,
            "cursor_definitions": cursor_definitions,
            "collection_definitions": collection_definitions,
        }
        bulk_operations = detect_bulk_operations(preliminary_ast)
        operations_by_table = _merge_bulk_operations_into_operations(operations_by_table, bulk_operations)
        tables_used = _synchronize_tables_used(tables_used, operations_by_table)
        sequence_dependencies = _extract_sequence_dependencies(item.block_text, sequence_names)
        select_assignments = _extract_select_into_assignments(item.block_text)
        scalar_assignments = _extract_scalar_assignments(
            item.block_text,
            [*parameter_names, *(var["name"] for var in local_variables)],
        )
        insert_statements = _extract_insert_statements(item.block_text)
        lookup_keys = _extract_lookup_keys(item.block_text, ddl_columns)
        exceptions = _extend_exceptions_with_select_into_risks(
            _extract_exceptions(item.block_text),
            select_assignments,
        )
        table_columns = _extract_table_columns(item.block_text, tables_used)
        for table in tables_used:
            ddl_cols = ddl_columns.get(table.upper(), [])
            if ddl_cols:
                table_columns.setdefault(table, [])
                table_columns[table] = sorted({*table_columns[table], *ddl_cols})
        table_relationships = _filter_relationships_for_tables(relationships, tables_used)
        analysis_ast: Dict[str, Any] = {
            "name": item.object_name,
            "object_type": item.object_type,
            "block_text": item.block_text,
            "parameters": params["all"],
            "input_parameters": params["in"],
            "output_parameters": params["out"],
            "variables": local_variables,
            "collections": collections,
            "tables_used": tables_used,
            "operations": operations_by_table,
            "lookup_keys": lookup_keys,
            "sequence_dependencies": sequence_dependencies,
            "select_assignments": select_assignments,
            "assignments": [*select_assignments, *scalar_assignments],
            "insert_statements": insert_statements,
            "collection_definitions": collection_definitions,
            "cursor_definitions": cursor_definitions,
            "schema": {
                "tables": table_defs,
                "relationships": relationships,
                "sequences": sequence_catalog["sequences"],
                "sequence_mapping": sequence_catalog["sequence_mapping"],
            },
        }
        analysis_ast["bulk_operations"] = bulk_operations
        cursor = detect_cursor_patterns(analysis_ast)
        analysis_ast["cursor"] = cursor
        collection_data_flow = detect_collection_data_flow(analysis_ast)
        variable_semantics = classify_variable_semantics(analysis_ast)
        analysis_ast["variable_semantics"] = variable_semantics
        data_flow = enhance_data_flow(analysis_ast)
        data_flow.extend(collection_data_flow)
        analysis_ast["data_flow"] = data_flow
        unused_variables = detect_unused_variables(analysis_ast)
        analysis_ast["unused_variables"] = unused_variables
        exception_sources = detect_exception_sources(analysis_ast)
        id_generation = detect_id_generation_conflict(analysis_ast, analysis_ast["schema"])
        transaction = detect_transaction_patterns(analysis_ast)
        analysis_ast["transaction"] = transaction
        analysis_ast["complexity"] = _complexity_metrics(item.block_text)
        retry_logic = detect_retry_logic(analysis_ast)
        error_handling = detect_bulk_exception_handling(analysis_ast)
        performance_patterns = (
            ["bulk_processing", "reduced_context_switching", "high_throughput_batch"]
            if any(op.get("type") == "BULK_COLLECT" for op in bulk_operations)
            and any(op.get("type") == "FORALL" for op in bulk_operations)
            else []
        )
        dependency_chain = _build_dependency_chains(tables_used, relationships)
        business_rules = _enhance_business_rules(
            item.block_text,
            _extract_business_rules(item.block_text),
        )
        issues = [
            *_validate_sequence_mapping(
                sequence_dependencies,
                sequence_catalog["sequence_mapping"],
                operations_by_table,
            ),
        ]
        analysis_ast["issues"] = issues
        issues.extend(detect_logic_gaps(analysis_ast))
        semantic_analysis = build_semantic_analysis(analysis_ast)
        analysis_ast["semantic_analysis"] = semantic_analysis
        complexity = classify_complexity(analysis_ast)
        proc_entry: Dict[str, Any] = {
            "name": item.object_name,
            "object_type": item.object_type,
            "parameters": params["all"],
            "input_parameters": params["in"],
            "output_parameters": params["out"],
            "variables": local_variables,
            "collections": collections,
            "tables_used": tables_used,
            "operations": operations_by_table,
            "business_rules": business_rules,
            "lookup_keys": lookup_keys,
            "data_flow": data_flow,
            "dependencies": _clean_dependencies(
                tables_used,
                sequence_dependencies,
                table_map.keys(),
                sequence_names,
            ),
            "exceptions": exceptions,
            "exception_sources": exception_sources,
            "variable_semantics": variable_semantics,
            "bulk_operations": bulk_operations,
            "cursor": cursor,
            "dependency_graph": {
                "tables_used": tables_used,
                "procedures_called": _extract_procedure_calls(
                    item.block_text,
                    item.object_name,
                    known_tables=tables_used,
                    known_symbols=[*parameter_names, *(var["name"] for var in local_variables)],
                ),
                "sequences_used": sequence_dependencies,
            },
            "table_details": {
                "tables": [
                    {
                        "name": table,
                        "columns": table_columns.get(table, []),
                        "lookup_keys": lookup_keys.get(table, []),
                        "primary_keys": table_map.get(table, {}).get("primary_keys", []),
                        "foreign_keys": table_map.get(table, {}).get("foreign_keys", []),
                    }
                    for table in tables_used
                ],
                "relationships": table_relationships,
            },
            "complexity": complexity,
            "unused_variables": unused_variables,
            "id_generation": id_generation,
            "transaction": transaction,
            "retry_logic": retry_logic,
            "error_handling": error_handling,
            "performance_patterns": performance_patterns,
            "issues": issues,
            "dependency_chain": dependency_chain,
            "semantic_analysis": semantic_analysis,
        }
        procedures.append(proc_entry)

    return {
        "schema": {
            "tables": table_defs,
            "relationships": relationships,
            "sequences": sequence_catalog["sequences"],
            "sequence_mapping": sequence_catalog["sequence_mapping"],
        },
        "procedures": procedures,
    }


def analyze_sql_source(sql_text: str) -> List[Dict[str, Any]]:
    """Analyze SQL/PLSQL text and return backward-compatible object metadata."""
    model = build_discovery_model(sql_text)
    results: List[Dict[str, Any]] = []
    for proc in model.get("procedures", []):
        tables_used = proc.get("tables_used", [])
        entry: Dict[str, Any] = {
            "procedureName": proc.get("name", ""),
            "objectType": proc.get("object_type", "PROCEDURE"),
            "parameters": {
                "in": proc.get("input_parameters", []),
                "out": proc.get("output_parameters", []),
            },
            "tablesUsed": tables_used,
            "operations": sorted({op for ops in proc.get("operations", {}).values() for op in ops}),
            "operationsByTable": proc.get("operations", {}),
            "lookupKeys": proc.get("lookup_keys", {}),
            "localVariables": proc.get("variables", []),
            "collections": proc.get("collections", []),
            "exceptions": proc.get("exceptions", []),
            "exceptionSources": proc.get("exception_sources", []),
            "businessRules": proc.get("business_rules", []),
            "dataFlow": proc.get("data_flow", []),
            "variableSemantics": proc.get("variable_semantics", []),
            "dependencies": proc.get("dependencies", []),
            "complexity": proc.get("complexity", {}),
            "bulkOperations": proc.get("bulk_operations", []),
            "cursor": proc.get("cursor", {}),
            "dependencyGraph": {
                "tablesUsed": proc.get("dependency_graph", {}).get("tables_used", []),
                "proceduresCalled": proc.get("dependency_graph", {}).get("procedures_called", []),
                "sequencesUsed": proc.get("dependency_graph", {}).get("sequences_used", []),
            },
            "tableDetails": proc.get("table_details", {"tables": [], "relationships": []}),
            "conversionPreview": _build_conversion_preview(proc.get("name", ""), tables_used),
            "unusedVariables": proc.get("unused_variables", []),
            "idGeneration": proc.get("id_generation", {}),
            "transaction": proc.get("transaction", {}),
            "retryLogic": proc.get("retry_logic", {}),
            "errorHandling": proc.get("error_handling", {}),
            "performancePatterns": proc.get("performance_patterns", []),
            "issues": proc.get("issues", []),
            "dependencyChain": proc.get("dependency_chain", []),
            "semantic_analysis": proc.get("semantic_analysis", {}),
            "semanticAnalysis": proc.get("semantic_analysis", {}),
        }
        results.append(entry)
    return results
