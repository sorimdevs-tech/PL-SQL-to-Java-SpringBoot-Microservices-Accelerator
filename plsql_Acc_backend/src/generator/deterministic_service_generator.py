"""Deterministic service generation helpers for repository/service alignment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class ServiceCallPlan:
    repository_var: str
    method_name: str
    args: List[str]
    result_var: str = ""
    result_type: str = ""

    def render_assignment(self) -> str:
        call = f"{self.repository_var}.{self.method_name}({', '.join(self.args)})"
        if self.result_var and self.result_type:
            return f"{self.result_type} {self.result_var} = {call};"
        return f"{call};"


class DeterministicServiceGenerator:
    """Small reusable helpers for logic-preserving service snippets."""

    def render_loop_with_try_catch(self, entity_type: str, source_expr: str, body_lines: List[str]) -> List[str]:
        lines = [f"for ({entity_type} e : {source_expr}) {{", "    try {"]
        lines.extend(f"        {line}" for line in body_lines)
        lines.extend(["    } catch (Exception ex) {", "        throw new RuntimeException(ex);", "    }", "}"])
        return lines

    def transactional_annotation_needed(self, has_dml: bool, has_skip_locked: bool, operation_count: int) -> bool:
        return bool(has_dml or has_skip_locked or operation_count > 1)

    def rollback_line(self) -> str:
        return 'throw new RuntimeException("PL/SQL rollback requested");'

    def render_repository_call(self, repository_var: str, method_name: str, args: List[str], result: Tuple[str, str] = ("", "")) -> str:
        result_type, result_var = result
        return ServiceCallPlan(repository_var, method_name, args, result_var, result_type).render_assignment()
