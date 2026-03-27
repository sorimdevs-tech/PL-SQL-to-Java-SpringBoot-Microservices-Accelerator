"""
Hard semantic enforcement rules for PL/SQL-to-Java behavioral parity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set


@dataclass
class EnforcementIssue:
    component: str
    object_name: str
    code: str
    message: str
    severity: str = "error"
    file_name: Optional[str] = None


class SemanticEnforcementEngine:
    def validate(
        self,
        source_units: List[Dict[str, Any]],
        repositories: Dict[str, str],
        services: Dict[str, str],
    ) -> List[EnforcementIssue]:
        issues: List[EnforcementIssue] = []
        issues.extend(self._validate_native_query_risks(repositories))
        for unit in source_units or []:
            service_filename = self._service_filename_for_unit(unit)
            service_code = services.get(service_filename, "")
            if not service_code:
                continue
            object_name = str(unit.get("name", ""))
            raw_plsql = str(unit.get("raw_plsql", ""))
            transaction = unit.get("transaction") or {}

            if self._has_batch_transaction_controls(raw_plsql, transaction):
                if re.search(r"(?m)^\s*@Transactional\b", service_code):
                    issues.append(
                        EnforcementIssue(
                            component="service",
                            object_name=object_name,
                            code="savepoint_method_transactional_forbidden",
                            message=(
                                f"{service_filename} uses method-level @Transactional for SAVEPOINT/COMMIT/ROLLBACK TO flow"
                            ),
                            file_name=service_filename,
                        )
                    )
                if not self._has_per_batch_transaction_logic(service_code):
                    issues.append(
                        EnforcementIssue(
                            component="service",
                            object_name=object_name,
                            code="savepoint_batch_transaction_missing",
                            message=(
                                f"{service_filename} must enforce independent per-batch transactions with rollback-only current batch"
                            ),
                            file_name=service_filename,
                        )
                    )

            cursor = unit.get("cursor") or {}
            locking = str(cursor.get("locking", "")).upper()
            has_skip_locked = bool(
                "SKIP LOCKED" in locking
                or re.search(r"\bFOR\s+UPDATE\s+SKIP\s+LOCKED\b", raw_plsql, flags=re.IGNORECASE)
            )
            if has_skip_locked:
                if re.search(r"\bpage\s*\+\+", service_code):
                    issues.append(
                        EnforcementIssue(
                            component="service",
                            object_name=object_name,
                            code="skip_locked_page_increment",
                            message=f"{service_filename} must not increment page index for SKIP LOCKED cursor flow",
                            file_name=service_filename,
                        )
                    )
                if re.search(r"PageRequest\s*\.\s*of\s*\(\s*page\b", service_code):
                    issues.append(
                        EnforcementIssue(
                            component="service",
                            object_name=object_name,
                            code="skip_locked_offset_pagination",
                            message=f"{service_filename} must not use offset pagination for SKIP LOCKED cursor flow",
                            file_name=service_filename,
                        )
                    )
                if not re.search(r"PageRequest\s*\.\s*of\s*\(\s*0\s*,", service_code):
                    issues.append(
                        EnforcementIssue(
                            component="service",
                            object_name=object_name,
                            code="skip_locked_missing_zero_page",
                            message=f"{service_filename} must fetch SKIP LOCKED batches using PageRequest.of(0, batchSize)",
                            file_name=service_filename,
                        )
                    )
                if re.search(r"\bOFFSET\b", service_code, flags=re.IGNORECASE):
                    issues.append(
                        EnforcementIssue(
                            component="service",
                            object_name=object_name,
                            code="cursor_offset_pagination",
                            message=f"{service_filename} replaces cursor progression with OFFSET pagination",
                            file_name=service_filename,
                        )
                    )

            plsql_literals = self._extract_plsql_error_literals(raw_plsql)
            if plsql_literals:
                java_literals = set(self._extract_java_string_literals(service_code))
                for literal in plsql_literals:
                    if literal in java_literals:
                        continue
                    issues.append(
                        EnforcementIssue(
                            component="service",
                            object_name=object_name,
                            code="literal_message_mismatch",
                            message=f'{service_filename} must preserve literal error message exactly: "{literal}"',
                            file_name=service_filename,
                        )
                    )
        return issues

    def _validate_native_query_risks(self, repositories: Dict[str, str]) -> List[EnforcementIssue]:
        issues: List[EnforcementIssue] = []
        query_pattern = re.compile(
            r"@Query\s*\((?P<args>[\s\S]*?)\)\s*(?:public\s+)?(?:default\s+)?[\w<>\[\], ?]+\s+(?P<method>[A-Za-z_]\w*)\s*\((?P<params>[^\)]*)\)",
            flags=re.IGNORECASE,
        )
        for filename, code in (repositories or {}).items():
            repository_name = filename.replace(".java", "")
            for match in query_pattern.finditer(code):
                args = match.group("args") or ""
                params = match.group("params") or ""
                if not re.search(r"\bnativeQuery\s*=\s*true\b", args, flags=re.IGNORECASE):
                    continue
                sql_match = re.search(r'value\s*=\s*"(?P<sql>(?:\\.|[^"\\])*)"', args, flags=re.IGNORECASE)
                if not sql_match:
                    continue
                sql_text = sql_match.group("sql") or ""
                if "FOR UPDATE" not in sql_text.upper():
                    continue
                if "Pageable" not in params:
                    continue
                method_name = match.group("method")
                issues.append(
                    EnforcementIssue(
                        component="repository",
                        object_name=repository_name,
                        code="native_query_for_update_pageable_risky",
                        message=(
                            f"{filename}.{method_name} is RISKY (native FOR UPDATE with Pageable). "
                            "Use custom query without Pageable OR manual fetch loop."
                        ),
                        severity="warning",
                        file_name=filename,
                    )
                )
        return issues

    def _service_filename_for_unit(self, unit: Dict[str, Any]) -> str:
        words = [token.capitalize() for token in re.split(r"[^A-Za-z0-9]+", str(unit.get("name", ""))) if token]
        base_name = "".join(words) or "Generated"
        if not base_name.endswith("Service"):
            base_name = f"{base_name}Service"
        return f"{base_name}.java"

    def _has_batch_transaction_controls(self, raw_plsql: str, transaction: Dict[str, Any]) -> bool:
        return bool(
            transaction.get("has_savepoint")
            or transaction.get("has_commit")
            or transaction.get("has_partial_rollback")
            or re.search(r"\bsavepoint\b", raw_plsql, flags=re.IGNORECASE)
            or re.search(r"\bcommit\b", raw_plsql, flags=re.IGNORECASE)
            or re.search(r"\brollback\s+to(?:\s+savepoint)?\b", raw_plsql, flags=re.IGNORECASE)
        )

    def _has_per_batch_transaction_logic(self, service_code: str) -> bool:
        return bool(
            "TransactionTemplate" in service_code
            and "executeWithoutResult" in service_code
            and "setRollbackOnly" in service_code
        )

    def _extract_plsql_error_literals(self, raw_plsql: str) -> List[str]:
        literals: List[str] = []
        for match in re.finditer(
            r"\braise_application_error\s*\(\s*[^,]+,\s*([\s\S]*?)\)",
            raw_plsql or "",
            flags=re.IGNORECASE,
        ):
            arg_expr = match.group(1) or ""
            for literal_match in re.finditer(r"'((?:''|[^'])*)'", arg_expr):
                text = literal_match.group(1).replace("''", "'")
                if text and text not in literals:
                    literals.append(text)
        return literals

    def _extract_java_string_literals(self, service_code: str) -> List[str]:
        literals: List[str] = []
        seen: Set[str] = set()
        for token in re.findall(r'"(?:\\.|[^"\\])*"', service_code or ""):
            decoded = self._decode_java_literal(token)
            if decoded in seen:
                continue
            seen.add(decoded)
            literals.append(decoded)
        return literals

    def _decode_java_literal(self, token: str) -> str:
        inner = (token or "")[1:-1]
        try:
            return bytes(inner, "utf-8").decode("unicode_escape")
        except Exception:
            return inner.replace('\\"', '"').replace("\\\\", "\\")
