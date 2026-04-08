"""
Logic tree builder for PL/SQL procedural blocks.

Creates a hierarchical execution tree that preserves:
- Control flow (LOOP, IF, EXCEPTION)
- SQL operations with aggregation detection
- Execution order and nesting

This provides a normalized semantic structure for code generation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LogicNode:
    type: str
    children: List["LogicNode"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LogicTreeBuilder:
    """Build a hierarchical execution tree from PL/SQL source text."""

    # Patterns for different constructs
    _LOOP_PATTERN = re.compile(
        r'\b(for\s+.*?\s+loop|while\s+.*?\s+loop)\s+(.*?)\s+end\s+loop\s*;',
        flags=re.IGNORECASE | re.DOTALL
    )
    _IF_PATTERN = re.compile(
        r'\bif\s+(.*?)\s+then\s+(.*?)\s+end\s+if\s*;',
        flags=re.IGNORECASE | re.DOTALL
    )
    _EXCEPTION_PATTERN = re.compile(
        r'\bbegin\s+(.*?)\s+exception\s+(.*?)\s+end\s*;',
        flags=re.IGNORECASE | re.DOTALL
    )
    _SQL_PATTERN = re.compile(
        r'\b(select|insert\s+into|update|delete\s+from|merge\s+into)\s+.*?;',
        flags=re.IGNORECASE | re.DOTALL
    )
    _ASSIGNMENT_PATTERN = re.compile(
        r'([A-Za-z_][\w$#]*)\s*:=\s*(.*?);',
        flags=re.IGNORECASE | re.DOTALL
    )
    _AGGREGATION_FUNCTIONS = ['SUM', 'COUNT', 'AVG', 'MIN', 'MAX']

    def build(self, source: str) -> LogicNode:
        """Build the hierarchical logic tree from PL/SQL source."""
        source = source.strip()
        if not source:
            return LogicNode(type="empty")

        # Start with a root sequence node
        root = LogicNode(type="sequence")
        self._parse_block(source, root)
        return root

    def _parse_block(self, block: str, parent: LogicNode) -> None:
        """Recursively parse a block of PL/SQL code."""
        # Remove leading/trailing whitespace
        block = block.strip()

        # Find all top-level constructs in order
        constructs = self._find_constructs(block)

        for construct_type, start, end, content in constructs:
            if construct_type == "loop":
                loop_node = LogicNode(type="loop", metadata={"condition": content[0]})
                parent.children.append(loop_node)
                self._parse_block(content[1], loop_node)
            elif construct_type == "if":
                if_node = LogicNode(type="if", metadata={"condition": content[0]})
                parent.children.append(if_node)
                self._parse_block(content[1], if_node)
            elif construct_type == "exception":
                try_node = LogicNode(type="try")
                parent.children.append(try_node)
                self._parse_block(content[0], try_node)
                # Add exception handling
                exception_node = LogicNode(type="catch", metadata={"action": self._parse_exception_action(content[1])})
                try_node.children.append(exception_node)
            elif construct_type == "sql":
                sql_node = self._parse_sql(content)
                parent.children.append(sql_node)
            elif construct_type == "assignment":
                assignment_node = LogicNode(type="assignment", metadata={
                    "target": content[0],
                    "expression": content[1]
                })
                parent.children.append(assignment_node)

    def _find_constructs(self, block: str) -> List[tuple[str, int, int, Any]]:
        """Find all constructs in the block and return them in order."""
        constructs = []

        # Find loops
        for match in self._LOOP_PATTERN.finditer(block):
            condition = match.group(1).strip()
            body = match.group(2).strip()
            constructs.append(("loop", match.start(), match.end(), (condition, body)))

        # Find if statements
        for match in self._IF_PATTERN.finditer(block):
            condition = match.group(1).strip()
            body = match.group(2).strip()
            constructs.append(("if", match.start(), match.end(), (condition, body)))

        # Find exception blocks
        for match in self._EXCEPTION_PATTERN.finditer(block):
            try_body = match.group(1).strip()
            exception_body = match.group(2).strip()
            constructs.append(("exception", match.start(), match.end(), (try_body, exception_body)))

        # Find SQL statements
        for match in self._SQL_PATTERN.finditer(block):
            sql = match.group(0).strip()
            constructs.append(("sql", match.start(), match.end(), sql))

        # Find assignments
        for match in self._ASSIGNMENT_PATTERN.finditer(block):
            target = match.group(1).strip()
            expr = match.group(2).strip()
            constructs.append(("assignment", match.start(), match.end(), (target, expr)))

        # Sort by start position
        constructs.sort(key=lambda x: x[1])

        # Remove overlapping constructs (keep the outermost)
        filtered = []
        for construct in constructs:
            if not filtered or construct[1] >= filtered[-1][2]:
                filtered.append(construct)

        return filtered

    def _parse_sql(self, sql: str) -> LogicNode:
        """Parse a SQL statement and detect aggregations."""
        sql_upper = sql.upper()

        # Determine SQL type
        if sql_upper.startswith('SELECT'):
            sql_type = 'select'
        elif sql_upper.startswith('INSERT'):
            sql_type = 'insert'
        elif sql_upper.startswith('UPDATE'):
            sql_type = 'update'
        elif sql_upper.startswith('DELETE'):
            sql_type = 'delete'
        elif sql_upper.startswith('MERGE'):
            sql_type = 'merge'
        else:
            sql_type = 'sql'

        # Check for aggregations
        aggregations = []
        for func in self._AGGREGATION_FUNCTIONS:
            if func + '(' in sql_upper:
                # Extract field from aggregation
                pattern = rf'{func}\s*\(\s*([^)]+)\s*\)'
                matches = re.findall(pattern, sql, flags=re.IGNORECASE)
                for match in matches:
                    aggregations.append({
                        "function": func,
                        "field": match.strip()
                    })

        metadata = {"sql": sql}
        if aggregations:
            metadata["aggregations"] = aggregations
            return LogicNode(type="aggregation", metadata=metadata)
        else:
            return LogicNode(type=sql_type, metadata=metadata)

    def _parse_exception_action(self, exception_body: str) -> str:
        """Parse exception body to determine action."""
        if 'rollback' in exception_body.lower():
            return 'rollback'
        elif 'continue' in exception_body.lower():
            return 'continue'
        else:
            return 'log'  # Default action


def build_logic_tree(source: str) -> LogicNode:
    """Build the logic tree from PL/SQL source."""
    return LogicTreeBuilder().build(source)
