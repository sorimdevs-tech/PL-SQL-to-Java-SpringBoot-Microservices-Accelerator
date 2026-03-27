"""
Helpers for recovering executable routine units from package bodies and SQL*Plus
substitution variables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.utils.naming import normalize_column_name


CONTROL_END_KEYWORDS = {
    "IF",
    "LOOP",
    "CASE",
    "WHILE",
    "FOR",
    "REPEAT",
    "EXCEPTION",
    "BEGIN",
}

NUMERIC_NAME_HINTS = {
    "id",
    "amount",
    "salary",
    "count",
    "qty",
    "quantity",
    "number",
    "num",
    "total",
    "retry",
    "batch",
}


@dataclass
class RecoveredRoutine:
    name: str
    routine_type: str
    sql: str


def _strip_sql_comments(sql_text: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", " ", sql_text or "", flags=re.DOTALL)
    return re.sub(r"--[^\r\n]*", " ", without_block)


def _find_package_body_region(sql_text: str) -> Optional[str]:
    if not sql_text:
        return None
    lowered = sql_text.lower()
    marker = "package body"
    idx = lowered.find(marker)
    if idx < 0:
        return None
    return sql_text[idx:]


def _match_routine_header(body_sql: str, start_index: int) -> Optional[re.Match[str]]:
    return re.match(
        r"\b(PROCEDURE|FUNCTION)\s+([A-Za-z_][\w$#]*)\b",
        body_sql[start_index:],
        flags=re.IGNORECASE,
    )


def _find_routine_end(body_sql: str, routine_name: str, from_index: int) -> int:
    token_pattern = re.compile(r"\b(PROCEDURE|FUNCTION|END)\b", flags=re.IGNORECASE)
    nested_routines = 0
    for token in token_pattern.finditer(body_sql, from_index):
        keyword = token.group(1).upper()
        if keyword in {"PROCEDURE", "FUNCTION"}:
            nested_routines += 1
            continue

        tail = body_sql[token.end():]
        end_match = re.match(
            r"\s*(?:(?:\"?([A-Za-z_][\w$#]*)\"?)\s*)?;",
            tail,
            flags=re.IGNORECASE,
        )
        if not end_match:
            continue

        end_identifier = (end_match.group(1) or "").upper()
        if end_identifier in CONTROL_END_KEYWORDS:
            continue

        if nested_routines > 0:
            nested_routines -= 1
            continue

        if end_identifier and end_identifier not in {routine_name.upper()}:
            continue

        return token.end() + end_match.end()

    return len(body_sql)


def extract_package_body_routines(sql: str) -> List[Dict[str, str]]:
    """
    Extract top-level PROCEDURE/FUNCTION blocks declared inside a PACKAGE BODY and
    return standalone CREATE OR REPLACE statements for each routine.
    """
    package_region = _find_package_body_region(_strip_sql_comments(sql))
    if not package_region:
        return []

    routine_pattern = re.compile(r"\b(PROCEDURE|FUNCTION)\b", flags=re.IGNORECASE)
    index = 0
    routines: List[RecoveredRoutine] = []
    text_length = len(package_region)

    while index < text_length:
        token = routine_pattern.search(package_region, index)
        if not token:
            break

        header_match = _match_routine_header(package_region, token.start())
        if not header_match:
            index = token.end()
            continue

        routine_type = header_match.group(1).upper()
        routine_name = header_match.group(2)
        header_start = token.start()
        routine_end = _find_routine_end(
            package_region,
            routine_name=routine_name,
            from_index=token.end(),
        )
        routine_block = package_region[header_start:routine_end].strip()

        if not routine_block:
            index = token.end()
            continue

        standalone_sql = f"CREATE OR REPLACE {routine_block}"
        if not standalone_sql.rstrip().endswith(";"):
            standalone_sql = standalone_sql.rstrip() + ";"

        routines.append(
            RecoveredRoutine(
                name=routine_name,
                routine_type=routine_type,
                sql=standalone_sql,
            )
        )
        index = max(routine_end, token.end())

    unique: Dict[tuple[str, str], RecoveredRoutine] = {}
    for routine in routines:
        unique[(routine.name.upper(), routine.routine_type)] = routine

    return [
        {"name": item.name, "routine_type": item.routine_type, "sql": item.sql}
        for item in unique.values()
    ]


def _normalize_substitution_parameter_name(raw_name: str) -> str:
    tokens = [token for token in re.split(r"[^A-Za-z0-9]+", raw_name or "") if token]
    if not tokens:
        return normalize_column_name(raw_name or "param")
    removable_prefixes = {"enter", "new", "delete", "view", "input", "param", "value"}
    if tokens and tokens[0].lower() in removable_prefixes:
        tokens = tokens[1:] or tokens
    return normalize_column_name("_".join(tokens))


def _infer_substitution_type(sql: str, variable_name: str) -> str:
    if not sql or not variable_name:
        return "VARCHAR2"

    quoted_pattern = re.compile(rf"['\"]\s*&{re.escape(variable_name)}\s*['\"]", flags=re.IGNORECASE)
    if quoted_pattern.search(sql):
        return "VARCHAR2"

    assignment_pattern = re.compile(
        rf"\b([A-Za-z_][\w$#]*)\s*:=\s*&{re.escape(variable_name)}\b",
        flags=re.IGNORECASE,
    )
    assignment = assignment_pattern.search(sql)
    if assignment:
        lhs = assignment.group(1)
        declaration_pattern = re.compile(
            rf"\b{re.escape(lhs)}\s+(NUMBER(?:\([^)]*\))?|INTEGER|FLOAT|DECIMAL|NUMERIC)\b",
            flags=re.IGNORECASE,
        )
        if declaration_pattern.search(sql):
            return "NUMBER"

    lower_name = variable_name.lower()
    if any(hint in lower_name for hint in NUMERIC_NAME_HINTS):
        return "NUMBER"

    numeric_use_pattern = re.compile(
        rf"[=<>+\-*/]\s*&{re.escape(variable_name)}\b|\b&{re.escape(variable_name)}\s*[=<>+\-*/]",
        flags=re.IGNORECASE,
    )
    if numeric_use_pattern.search(sql):
        return "NUMBER"

    return "VARCHAR2"


def extract_substitution_vars(sql: str) -> List[Dict[str, str]]:
    """
    Extract SQL*Plus substitution variables (&Enter_Name, &X, ...) and infer a basic
    input type for routine parameter recovery.
    """
    cleaned_sql = _strip_sql_comments(sql or "")
    pattern = re.compile(r"(?<![\w$#])&([A-Za-z_][\w$#]*)")
    results: Dict[str, Dict[str, str]] = {}

    for match in pattern.finditer(cleaned_sql):
        raw_name = match.group(1)
        key = raw_name.upper()
        parameter_name = _normalize_substitution_parameter_name(raw_name)
        inferred_type = _infer_substitution_type(cleaned_sql, raw_name)
        results[key] = {
            "raw_name": raw_name,
            "parameter_name": parameter_name,
            "type": inferred_type,
        }

    return list(results.values())


def merge_substitution_vars_into_unit(unit: Dict[str, Any]) -> None:
    raw_plsql = str(unit.get("raw_plsql", ""))
    extracted = extract_substitution_vars(raw_plsql)
    if not extracted:
        return

    input_params = list(unit.get("input_parameters") or [])
    existing = {str(param.get("name", "")).upper() for param in input_params if param.get("name")}

    for item in extracted:
        name = item.get("parameter_name", "")
        if not name or name.upper() in existing:
            continue
        inferred_type = item.get("type", "VARCHAR2")
        input_params.append(
            {
                "name": name,
                "type": inferred_type,
                "direction": "IN",
                "source": "substitution_var",
                "raw_name": item.get("raw_name", name),
            }
        )
        existing.add(name.upper())

    unit["input_parameters"] = input_params
    unit.setdefault("recovered_parameters", [])
    unit["recovered_parameters"].extend(extracted)


def classify_routine_type(unit: Dict[str, Any]) -> str:
    operations = {
        str(op).upper()
        for ops in (unit.get("operations_by_table") or {}).values()
        for op in (ops or [])
    }
    raw_plsql = str(unit.get("raw_plsql", ""))
    transaction = unit.get("transaction") or {}
    has_batch_indicators = bool(
        unit.get("bulk_operations")
        or unit.get("cursor")
        or transaction.get("has_savepoint")
        or transaction.get("has_partial_rollback")
        or re.search(r"\b(BULK\s+COLLECT|SKIP\s+LOCKED|SAVEPOINT|ROLLBACK|COMMIT)\b", raw_plsql, flags=re.IGNORECASE)
    )
    if has_batch_indicators:
        return "BATCH_PROCESSING"

    write_ops = {"INSERT", "UPDATE", "DELETE", "MERGE"}
    if operations and operations.issubset({"SELECT"}):
        return "REPORTING"
    if operations.intersection(write_ops):
        return "CRUD"
    if "SELECT" in operations:
        return "REPORTING"
    return "CRUD"
