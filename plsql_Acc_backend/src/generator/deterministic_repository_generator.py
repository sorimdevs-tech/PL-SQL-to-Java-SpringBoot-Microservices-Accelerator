"""Deterministic Spring Data repository generation helpers.

These helpers encode the conversion rules that should not be left to an LLM:
aggregation uses @Query, joins use @Query, and FOR UPDATE / SKIP LOCKED always
uses native SQL rather than Spring Data derived method parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.utils.naming import normalize_column_name, to_pascal_case


SQL_KEYWORDS_FOR_METHODS = ("Join", "Update", "ForUpdate", "SkipLocked")


@dataclass
class RepositoryMethodPlan:
    name: str
    return_type: str
    params: List[Tuple[str, str, str]] = field(default_factory=list)
    query: str = ""
    native_query: bool = False
    read_only: bool = False

    def render(self) -> str:
        method_params = []
        for param_name, java_type, query_name in self.params:
            if query_name:
                method_params.append(f'@Param("{query_name}") {java_type} {param_name}')
            else:
                method_params.append(f"{java_type} {param_name}")
        params_blob = ", ".join(method_params)
        lines: List[str] = []
        if self.read_only:
            lines.append("    @Transactional(readOnly = true)")
        if self.query:
            if self.native_query:
                lines.append(f'    @Query(value = "{self.query}", nativeQuery = true)')
            else:
                lines.append(f'    @Query("{self.query}")')
        lines.append(f"    {self.return_type} {self.name}({params_blob});")
        return "\n".join(lines)


class DeterministicRepositoryGenerator:
    """Generate repository methods from semantic SQL intent."""

    def __init__(self, package_name: str = "com.company.project"):
        self.package_name = package_name

    def is_transactional_sql(self, sql: str) -> bool:
        return bool(re.search(r"\bFOR\s+UPDATE\b|\bSKIP\s+LOCKED\b", sql or "", flags=re.IGNORECASE))

    def sanitize_method_name(self, method_name: str) -> str:
        clean = method_name or "findRecords"
        for keyword in SQL_KEYWORDS_FOR_METHODS:
            clean = clean.replace(keyword, "")
        clean = re.sub(r"__+", "_", clean)
        clean = re.sub(r"\bfindPage\b", "find", clean)
        return clean or "findRecords"

    def extract_where_params(
        self,
        sql: str,
        entity_field_types: Optional[Dict[str, str]] = None,
    ) -> List[Tuple[str, str, str]]:
        entity_field_types = entity_field_types or {}
        where_match = re.search(
            r"\bWHERE\b\s+(.*?)(?:\bFOR\s+UPDATE\b|\bORDER\s+BY\b|\bGROUP\s+BY\b|$)",
            sql or "",
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not where_match:
            return []
        params: List[Tuple[str, str, str]] = []
        seen = set()
        for match in re.finditer(r"(?:\b\w+\.)?([A-Za-z_][\w$#]*)\s*=\s*(?::([A-Za-z_]\w*)|[A-Za-z_][\w$#]*|'[^']*')", where_match.group(1)):
            column_name = match.group(1)
            query_name = match.group(2) or normalize_column_name(column_name)
            param_name = normalize_column_name(query_name)
            if param_name in seen:
                continue
            seen.add(param_name)
            java_type = self._resolve_type(column_name, entity_field_types)
            params.append((param_name, java_type, query_name))
        return params

    def generate_native_query_method(
        self,
        sql: str,
        entity_name: str,
        params: Optional[List[Tuple[str, str, str]]] = None,
        method_name: Optional[str] = None,
        pageable: bool = False,
        single_row: bool = False,
        return_type: Optional[str] = None,
    ) -> RepositoryMethodPlan:
        clean_sql = " ".join((sql or "").strip().rstrip(";").split())
        params = list(params or [])
        safe_name = method_name or self.locked_method_name(entity_name, params)
        safe_name = self.sanitize_method_name(safe_name)
        method_return_type = return_type or (f"Optional<{entity_name}>" if single_row else f"List<{entity_name}>")
        if pageable:
            params = [*params, ("pageable", "Pageable", "")]
        return RepositoryMethodPlan(
            name=safe_name,
            return_type=method_return_type,
            params=params,
            query=clean_sql,
            native_query=True,
        )

    def aggregation_method(
        self,
        function_name: str,
        entity_name: str,
        field_name: str,
        lookup_params: Optional[List[Tuple[str, str, str]]] = None,
    ) -> RepositoryMethodPlan:
        function = (function_name or "SUM").upper()
        field = normalize_column_name(field_name or "value")
        method_prefix = "count" if function == "COUNT" else "getTotal"
        method_name = f"{method_prefix}{to_pascal_case(field)}"
        return_type = "Long" if function == "COUNT" else "Double"
        params = list(lookup_params or [])
        where = ""
        if params:
            where = " WHERE " + " AND ".join(f"e.{param_name} = :{query_name}" for param_name, _, query_name in params)
            method_name += "By" + "And".join(to_pascal_case(param_name) for param_name, _, _ in params)
        return RepositoryMethodPlan(
            name=method_name,
            return_type=return_type,
            params=params,
            query=f"SELECT {function}(e.{field}) FROM {entity_name} e{where}",
            read_only=True,
        )

    def locked_method_name(self, entity_name: str, params: Sequence[Tuple[str, str, str]]) -> str:
        base = entity_name[:-6] if entity_name.endswith("Entity") else entity_name
        suffix = ""
        if params:
            suffix = "By" + "And".join(to_pascal_case(param_name) for param_name, _, _ in params if param_name != "pageable")
        return f"findLocked{base}{suffix}"

    def required_imports(self, methods: Iterable[RepositoryMethodPlan]) -> List[str]:
        imports = {"import org.springframework.data.jpa.repository.JpaRepository;", "import org.springframework.stereotype.Repository;"}
        for method in methods:
            if method.query:
                imports.add("import org.springframework.data.jpa.repository.Query;")
            if any(query_name for _, _, query_name in method.params):
                imports.add("import org.springframework.data.repository.query.Param;")
            if "Pageable" in method.render():
                imports.add("import org.springframework.data.domain.Pageable;")
            if "Page<" in method.return_type:
                imports.add("import org.springframework.data.domain.Page;")
            if "List<" in method.return_type or "List<Object[]>" in method.return_type:
                imports.add("import java.util.List;")
            if "Optional<" in method.return_type:
                imports.add("import java.util.Optional;")
            if method.read_only:
                imports.add("import org.springframework.transaction.annotation.Transactional;")
        return sorted(imports)

    def _resolve_type(self, column_name: str, entity_field_types: Dict[str, str]) -> str:
        normalized = normalize_column_name(column_name)
        for field_name, java_type in entity_field_types.items():
            if normalize_column_name(field_name).lower() == normalized.lower():
                return java_type
        return "String"
