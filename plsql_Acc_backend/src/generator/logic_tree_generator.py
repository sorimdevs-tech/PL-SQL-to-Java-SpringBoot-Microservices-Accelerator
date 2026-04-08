"""
Prompt builder for structured logic-tree -> Java service conversion.

This module is intentionally separate from raw PL/SQL prompt generation:
- input is already a structured logic tree
- generation should follow the tree exactly
- no SQL parsing assumptions should be introduced by the model
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LogicTreeGenerationRequest:
    logic_tree: Dict[str, Any]
    method_name: str
    package_name: str = "com.company.project"
    service_name: str = "GeneratedService"
    repositories: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    entity_fields: Dict[str, List[str]] = field(default_factory=dict)
    notes: Optional[str] = None


class LogicTreePromptBuilder:
    """Builds a strict prompt for converting a structured logic tree to Java."""

    def build_prompt(self, request: LogicTreeGenerationRequest) -> str:
        logic_tree_json = json.dumps(request.logic_tree, ensure_ascii=True, indent=2, default=str)
        repositories = ", ".join(request.repositories) if request.repositories else "(not provided)"
        entities = ", ".join(request.entities) if request.entities else "(not provided)"
        fields = self._format_entity_fields(request.entity_fields)
        notes = request.notes.strip() if request.notes else "(none)"

        return f"""
You are an expert code generator that converts a structured logic tree into Java Spring Boot service-layer code.

You are NOT converting raw SQL.
You are given a structured logic tree that already represents the business logic.

Your job is to generate clean, correct, and executable Java code.

INPUT CONTEXT:
- Package: {request.package_name}
- Service class: {request.service_name}
- Method name: {request.method_name}
- Available repositories: {repositories}
- Available entities: {entities}
- Entity fields:
{fields}
- Additional notes: {notes}

LOGIC TREE (SOURCE OF TRUTH):
{logic_tree_json}

GOAL:
- Generate one Java service-layer method that exactly follows the logic tree structure.

STRICT RULES:
1. FOLLOW LOGIC TREE EXACTLY
   - Do NOT modify logic.
   - Do NOT add or remove conditions.
   - Maintain execution order strictly.

2. CONTROL FLOW MAPPING
   - IF -> if
   - ELSEIF / ELSIF -> else if
   - ELSE -> else

3. OPERATION MAPPING
   - COUNT -> repository.countBy... and store in numeric variable (long/int)
   - SELECT -> repository.findBy... and use Optional if needed
   - INSERT -> create entity, set fields, save()
   - UPDATE -> fetch entity, update fields, save()
   - DELETE -> repository.deleteBy...

4. VARIABLE HANDLING
   - Declare variables before usage.
   - Use names from the logic tree.
   - Maintain type correctness.

5. CONDITION CONVERSION
   - Convert SQL "=" into Java equality checks.
   - Convert LIKE into equals comparison only when the logic tree clearly represents exact-match semantics.
   - Preserve numeric comparisons (>, <, >=, <=).

6. NO TEMPLATE CODE
   - Do NOT generate generic or placeholder code.
   - Every line must come from the logic tree or required Java syntax.

7. REPOSITORY RULES
   - Use only valid repository methods:
     findBy<Field>()
     countBy<Field>()
     deleteBy<Field>()
     existsBy<Field>()
   - Do NOT use findOne(null).
   - Do NOT use LIKE in Java repository calls.
   - Do NOT fetch full entities for COUNT logic.

8. CLEAN CODE REQUIREMENTS
   - Proper indentation.
   - No duplicate variables.
   - No unused variables.
   - Compile-ready Java code.

SELF-VALIDATION:
- Ensure all logic tree nodes are implemented.
- Ensure IF/ELSE structure is correct.
- Ensure no operation is skipped.
- If the logic tree is incomplete, do not guess; explicitly mention the missing parts.

OUTPUT FORMAT:
- Return exactly one Java method only.
- No markdown fences.
- No prose before the method.
- If the logic tree is incomplete, return a short Java comment above the method describing the missing mapping.
"""

    def _format_entity_fields(self, entity_fields: Dict[str, List[str]]) -> str:
        if not entity_fields:
            return "(not provided)"
        lines = []
        for entity_name, fields in entity_fields.items():
            ordered_fields = ", ".join(fields or [])
            lines.append(f"- {entity_name}: {ordered_fields}")
        return "\n".join(lines)


def create_logic_tree_prompt(
    logic_tree: Dict[str, Any],
    method_name: str,
    package_name: str = "com.company.project",
    service_name: str = "GeneratedService",
    repositories: Optional[List[str]] = None,
    entities: Optional[List[str]] = None,
    entity_fields: Optional[Dict[str, List[str]]] = None,
    notes: Optional[str] = None,
) -> str:
    builder = LogicTreePromptBuilder()
    return builder.build_prompt(
        LogicTreeGenerationRequest(
            logic_tree=logic_tree,
            method_name=method_name,
            package_name=package_name,
            service_name=service_name,
            repositories=repositories or [],
            entities=entities or [],
            entity_fields=entity_fields or {},
            notes=notes,
        )
    )
