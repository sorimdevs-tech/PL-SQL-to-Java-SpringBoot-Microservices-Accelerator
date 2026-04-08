"""
Logic tree builder for PL/SQL procedural blocks.

The builder preserves executable nesting so downstream generation can reason
about loops, conditions, exception scopes, SQL semantics, and transaction
controls without flattening PL/SQL into an ordered list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


AGGREGATION_FUNCTIONS = ("SUM", "COUNT", "AVG", "MIN", "MAX")
SQL_START_PATTERN = re.compile(
    r"^\s*(select|insert\s+into|update|delete\s+from|merge\s+into)\b",
    flags=re.IGNORECASE | re.DOTALL,
)
TRANSACTION_START_PATTERN = re.compile(
    r"^\s*(savepoint|rollback(?:\s+to(?:\s+savepoint)?)?|commit)\b",
    flags=re.IGNORECASE | re.DOTALL,
)


@dataclass
class LogicNode:
    type: str
    children: List["LogicNode"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def node_type(self) -> str:
        return self.type

    def add_child(self, node: "LogicNode") -> "LogicNode":
        self.children.append(node)
        return node

    def to_dict(self) -> Dict[str, Any]:
        sequence = [child.to_dict() for child in self.children]
        result = {
            "type": self.type,
            "node_type": self.type,
            "metadata": dict(self.metadata),
            "children": sequence,
            "sequence": sequence,
        }
        if self.metadata.get("node_class") == "ProgramNode":
            result["sequence"] = [node.to_dict() for node in self.walk() if node is not self]
            result["features"] = self._features()
            result["metrics"] = self._metrics()
            result["branches"] = [
                child.to_dict()
                for child in self.walk()
                if child is not self and child.type in {"if", "elsif", "else"}
            ]
        return result

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def walk(self) -> Iterable["LogicNode"]:
        yield self
        for child in self.children:
            yield from child.walk()

    def _features(self) -> Dict[str, bool]:
        nodes = list(self.walk())
        return {
            "dynamic_sql": any(node.type == "execute_immediate" for node in nodes),
            "exception_block": any(node.type == "try" for node in nodes),
            "transaction_control": any(node.type == "transaction" for node in nodes),
            "loop": any(node.type == "loop" for node in nodes),
            "conditional": any(node.type in {"if", "elsif", "else"} for node in nodes),
        }

    def _metrics(self) -> Dict[str, int]:
        nodes = [node for node in self.walk() if node is not self]
        return {
            "sequence_length": len(nodes),
            "branch_count": sum(1 for node in nodes if node.type in {"if", "elsif", "else"}),
            "loop_count": sum(1 for node in nodes if node.type == "loop"),
            "sql_count": sum(1 for node in nodes if node.type in {"select", "insert", "update", "delete", "merge", "aggregation", "count_into"}),
            "transaction_count": sum(1 for node in nodes if node.type == "transaction"),
        }


class ProgramNode(LogicNode):
    def __init__(self, children: Optional[List[LogicNode]] = None, metadata: Optional[Dict[str, Any]] = None):
        super().__init__("program", children or [], {"node_class": "ProgramNode", **(metadata or {})})


class LoopNode(LogicNode):
    def __init__(self, condition: str, children: Optional[List[LogicNode]] = None, metadata: Optional[Dict[str, Any]] = None):
        super().__init__("loop", children or [], {"condition": condition, "node_class": "LoopNode", **(metadata or {})})


class ConditionNode(LogicNode):
    def __init__(self, condition: str, children: Optional[List[LogicNode]] = None, metadata: Optional[Dict[str, Any]] = None, node_type: str = "if"):
        super().__init__(node_type, children or [], {"condition": condition, "node_class": "ConditionNode", **(metadata or {})})


class TryCatchNode(LogicNode):
    def __init__(self, children: Optional[List[LogicNode]] = None, metadata: Optional[Dict[str, Any]] = None):
        super().__init__("try", children or [], {"node_class": "TryCatchNode", **(metadata or {})})


class ExceptionNode(LogicNode):
    def __init__(self, body: str = "", children: Optional[List[LogicNode]] = None, metadata: Optional[Dict[str, Any]] = None):
        super().__init__("catch", children or [], {"body": body, "action": _parse_exception_action(body), "node_class": "ExceptionNode", **(metadata or {})})


class SQLNode(LogicNode):
    def __init__(self, query: str, semantic: Optional[Dict[str, Any]] = None, children: Optional[List[LogicNode]] = None):
        semantic = semantic or classify_query(query)
        node_type = _sql_node_type(query, semantic)
        super().__init__(
            node_type,
            children or [],
            {
                "sql": query,
                "query": query,
                "semantic_type": semantic.get("semantic_type", "UNKNOWN"),
                "is_transactional": bool(semantic.get("is_transactional", False)),
                "has_join": bool(semantic.get("has_join", False)),
                "aggregations": semantic.get("aggregations", []),
                "node_class": "SQLNode",
            },
        )


class TransactionNode(LogicNode):
    def __init__(self, statement: str, children: Optional[List[LogicNode]] = None, metadata: Optional[Dict[str, Any]] = None):
        operation = _transaction_operation(statement)
        super().__init__(
            "transaction",
            children or [],
            {"statement": statement, "operation": operation, "node_class": "TransactionNode", **(metadata or {})},
        )


def classify_query(sql: str, is_transactional: bool = False) -> Dict[str, Any]:
    """Classify a SQL statement for logic-tree and RAG consumers."""
    text = " ".join((sql or "").strip().split())
    upper = text.upper()
    aggregations = []
    for function_name in AGGREGATION_FUNCTIONS:
        for match in re.finditer(rf"\b{function_name}\s*\(\s*([^)]+)\)", text, flags=re.IGNORECASE):
            aggregations.append({"function": function_name, "field": match.group(1).strip()})

    if aggregations:
        semantic_type = "AGGREGATION"
    elif re.search(r"\bselect\b.*\binto\b", upper, flags=re.DOTALL):
        semantic_type = "SINGLE_ROW"
    elif re.match(r"\s*(insert|update|delete|merge)\b", upper):
        semantic_type = "DML"
    elif re.search(r"\bcursor\b|\bfor\s+\w+\s+in\s*\(", upper):
        semantic_type = "CURSOR_LOOP"
    else:
        semantic_type = "QUERY" if upper.startswith("SELECT") else "UNKNOWN"

    return {
        "query": text,
        "semantic_type": semantic_type,
        "is_transactional": bool(is_transactional),
        "has_join": bool(re.search(r"\bjoin\b", upper)),
        "aggregations": aggregations,
    }


class LogicTreeBuilder:
    """Build a hierarchical execution tree from PL/SQL source text or IR."""

    def build(self, source: Any) -> LogicNode:
        if isinstance(source, dict):
            root = ProgramNode(metadata={"source": "structured_ir"})
            self._append_ir_node(source, root)
            return root
        if isinstance(source, list):
            root = ProgramNode(metadata={"source": "structured_ir"})
            for item in source:
                self._append_ir_node(item, root)
            return root

        text = (source or "").strip()
        root = ProgramNode()
        if not text:
            root.metadata["empty"] = True
            return root
        if re.search(r"\bcreate\s+(?:or\s+replace\s+)?(?:procedure|function|trigger|package)\b", text, flags=re.IGNORECASE):
            begin_match = re.search(r"\bbegin\b", text, flags=re.IGNORECASE)
            if begin_match:
                text = text[begin_match.start():]
        root.children = self._parse_sequence(text, 0, stop_tokens=())[0]
        return root

    def _parse_sequence(
        self,
        text: str,
        pos: int,
        stop_tokens: Sequence[str],
        transaction_depth: int = 0,
    ) -> Tuple[List[LogicNode], int, Optional[str]]:
        nodes: List[LogicNode] = []
        length = len(text)
        current_transaction_depth = transaction_depth

        while pos < length:
            pos = self._skip_noise(text, pos)
            if pos >= length:
                break
            matched_stop = self._match_stop_token(text, pos, stop_tokens)
            if matched_stop:
                return nodes, pos, matched_stop

            if self._keyword_at(text, pos, "BEGIN"):
                node, pos = self._parse_begin_block(text, pos, current_transaction_depth)
                nodes.append(node)
                continue
            if self._keyword_at(text, pos, "IF"):
                node, pos = self._parse_if(text, pos, current_transaction_depth)
                nodes.append(node)
                continue
            if self._loop_starts_at(text, pos):
                node, pos = self._parse_loop(text, pos, current_transaction_depth)
                nodes.append(node)
                continue

            statement, pos = self._read_statement(text, pos)
            node = self._statement_to_node(statement, current_transaction_depth)
            if node is not None:
                nodes.append(node)
                if node.type == "transaction":
                    operation = str(node.metadata.get("operation", "")).upper()
                    if operation == "SAVEPOINT":
                        current_transaction_depth = max(1, current_transaction_depth)
                    elif operation in {"COMMIT", "ROLLBACK"}:
                        current_transaction_depth = 0

        return nodes, pos, None

    def _parse_begin_block(self, text: str, pos: int, transaction_depth: int) -> Tuple[LogicNode, int]:
        body_start = pos + len("BEGIN")
        body, pos, stop = self._parse_sequence(text, body_start, ("EXCEPTION", "END"), transaction_depth)
        if stop == "EXCEPTION":
            exception_start = pos + len("EXCEPTION")
            exception_nodes, pos, _ = self._parse_sequence(text, exception_start, ("END",), transaction_depth)
            pos = self._consume_end(text, pos)
            exception_text = self._slice_before_end(text, exception_start, pos)
            node = TryCatchNode(body, {"has_exception": True})
            node.children.append(ExceptionNode(exception_text, exception_nodes))
            return node, pos

        pos = self._consume_end(text, pos)
        block = LogicNode("block", body, {"node_class": "BlockNode"})
        return block, pos

    def _parse_loop(self, text: str, pos: int, transaction_depth: int) -> Tuple[LogicNode, int]:
        loop_keyword = self._find_keyword(text, "LOOP", pos)
        header = text[pos : loop_keyword + len("LOOP")].strip() if loop_keyword >= 0 else text[pos:].strip()
        body_start = loop_keyword + len("LOOP") if loop_keyword >= 0 else pos
        body, pos, _ = self._parse_sequence(text, body_start, ("END LOOP",), transaction_depth)
        pos = self._consume_phrase(text, pos, "END LOOP")
        return LoopNode(header, body), pos

    def _parse_if(self, text: str, pos: int, transaction_depth: int) -> Tuple[LogicNode, int]:
        then_pos = self._find_keyword(text, "THEN", pos)
        condition = text[pos + len("IF") : then_pos].strip() if then_pos >= 0 else ""
        body_start = then_pos + len("THEN") if then_pos >= 0 else pos + len("IF")
        body, pos, stop = self._parse_sequence(text, body_start, ("ELSIF", "ELSE", "END IF"), transaction_depth)
        node = ConditionNode(condition, body)

        while stop == "ELSIF":
            elsif_then = self._find_keyword(text, "THEN", pos)
            elsif_condition = text[pos + len("ELSIF") : elsif_then].strip() if elsif_then >= 0 else ""
            elsif_body, pos, stop = self._parse_sequence(
                text,
                (elsif_then + len("THEN")) if elsif_then >= 0 else pos + len("ELSIF"),
                ("ELSIF", "ELSE", "END IF"),
                transaction_depth,
            )
            node.children.append(ConditionNode(elsif_condition, elsif_body, node_type="elsif"))

        if stop == "ELSE":
            else_body, pos, stop = self._parse_sequence(text, pos + len("ELSE"), ("END IF",), transaction_depth)
            node.children.append(ConditionNode("", else_body, node_type="else"))

        if stop == "END IF":
            pos = self._consume_phrase(text, pos, "END IF")
        return node, pos

    def _statement_to_node(self, statement: str, transaction_depth: int) -> Optional[LogicNode]:
        statement = statement.strip()
        if not statement:
            return None

        if re.match(r"^\s*execute\s+immediate\b", statement, flags=re.IGNORECASE):
            return LogicNode("execute_immediate", metadata={"statement": statement})

        if TRANSACTION_START_PATTERN.match(statement):
            return TransactionNode(statement)

        if SQL_START_PATTERN.match(statement):
            return SQLNode(statement, classify_query(statement, transaction_depth > 0))

        assignment = re.match(r"^\s*([A-Za-z_][\w$#]*)\s*:=\s*(.*?)\s*;?\s*$", statement, flags=re.IGNORECASE | re.DOTALL)
        if assignment:
            return LogicNode(
                "assignment",
                metadata={"target": assignment.group(1).strip(), "expression": assignment.group(2).strip()},
            )

        return LogicNode("statement", metadata={"statement": statement})

    def _append_ir_node(self, item: Dict[str, Any], parent: LogicNode) -> None:
        node_type = str(item.get("type", "")).upper()
        if node_type in {"PROGRAM", "BLOCK"}:
            target = parent if node_type == "PROGRAM" else parent.add_child(LogicNode("block", metadata={"node_class": "BlockNode"}))
            for child in item.get("body", []) or item.get("children", []) or []:
                self._append_ir_node(child, target)
        elif node_type == "TRY_BLOCK":
            try_node = TryCatchNode()
            parent.children.append(try_node)
            for child in item.get("body", []) or []:
                self._append_ir_node(child, try_node)
            exception = ExceptionNode(str(item.get("exception_text", "")))
            try_node.children.append(exception)
            for child in item.get("exception", []) or []:
                self._append_ir_node(child, exception)
        elif node_type == "LOOP":
            loop_node = LoopNode(str(item.get("condition") or item.get("header") or "LOOP"))
            parent.children.append(loop_node)
            for child in item.get("body", []) or []:
                self._append_ir_node(child, loop_node)
        elif node_type == "IF":
            if_node = ConditionNode(str(item.get("condition", "")))
            parent.children.append(if_node)
            for child in item.get("then", []) or item.get("body", []) or []:
                self._append_ir_node(child, if_node)
            if item.get("else"):
                else_node = ConditionNode("", node_type="else")
                if_node.children.append(else_node)
                for child in item.get("else", []) or []:
                    self._append_ir_node(child, else_node)
        elif node_type == "TRANSACTION":
            parent.children.append(TransactionNode(str(item.get("statement", ""))))
        elif node_type == "SQL":
            parent.children.append(SQLNode(str(item.get("query") or item.get("text") or ""), item.get("metadata") or {}))
        else:
            parent.children.append(LogicNode(node_type.lower() or "statement", metadata=dict(item)))

    def _skip_noise(self, text: str, pos: int) -> int:
        while pos < len(text):
            if text[pos].isspace():
                pos += 1
                continue
            if text.startswith("--", pos):
                newline = text.find("\n", pos)
                pos = len(text) if newline < 0 else newline + 1
                continue
            if text.startswith("/*", pos):
                end = text.find("*/", pos + 2)
                pos = len(text) if end < 0 else end + 2
                continue
            if text[pos] == ";":
                pos += 1
                continue
            break
        return pos

    def _read_statement(self, text: str, pos: int) -> Tuple[str, int]:
        in_string = False
        index = pos
        while index < len(text):
            char = text[index]
            if char == "'":
                if in_string and index + 1 < len(text) and text[index + 1] == "'":
                    index += 2
                    continue
                in_string = not in_string
            elif char == ";" and not in_string:
                return text[pos : index + 1], index + 1
            index += 1
        return text[pos:index], index

    def _find_keyword(self, text: str, keyword: str, pos: int) -> int:
        pattern = re.compile(rf"\b{re.escape(keyword)}\b", flags=re.IGNORECASE)
        in_string = False
        index = pos
        while index < len(text):
            char = text[index]
            if char == "'":
                if in_string and index + 1 < len(text) and text[index + 1] == "'":
                    index += 2
                    continue
                in_string = not in_string
            if not in_string:
                match = pattern.match(text, index)
                if match:
                    return index
            index += 1
        return -1

    def _keyword_at(self, text: str, pos: int, keyword: str) -> bool:
        return bool(re.match(rf"\b{re.escape(keyword)}\b", text[pos:], flags=re.IGNORECASE))

    def _loop_starts_at(self, text: str, pos: int) -> bool:
        return bool(re.match(r"\b(for\b.*?\bloop\b|while\b.*?\bloop\b|loop\b)", text[pos:], flags=re.IGNORECASE | re.DOTALL))

    def _match_stop_token(self, text: str, pos: int, stop_tokens: Sequence[str]) -> Optional[str]:
        for token in stop_tokens:
            pattern = r"\b" + r"\s+".join(re.escape(part) for part in token.split()) + r"\b"
            if re.match(pattern, text[pos:], flags=re.IGNORECASE):
                return token
        return None

    def _consume_phrase(self, text: str, pos: int, phrase: str) -> int:
        pattern = r"\s*" + r"\s+".join(re.escape(part) for part in phrase.split()) + r"\b\s*;?"
        match = re.match(pattern, text[pos:], flags=re.IGNORECASE)
        return pos + match.end() if match else pos

    def _consume_end(self, text: str, pos: int) -> int:
        return self._consume_phrase(text, pos, "END")

    def _slice_before_end(self, text: str, start: int, end: int) -> str:
        snippet = text[start:end]
        return re.sub(r"\bend\b\s*;?\s*$", "", snippet, flags=re.IGNORECASE).strip()


def _parse_exception_action(exception_body: str) -> str:
    body = (exception_body or "").lower()
    if "rollback" in body:
        return "rollback"
    if "continue" in body or re.search(r"\bnull\s*;", body):
        return "continue"
    return "log"


def _transaction_operation(statement: str) -> str:
    upper = (statement or "").upper()
    if "SAVEPOINT" in upper:
        return "SAVEPOINT"
    if "ROLLBACK" in upper:
        return "ROLLBACK"
    if "COMMIT" in upper:
        return "COMMIT"
    return "TRANSACTION"


def _sql_node_type(query: str, semantic: Dict[str, Any]) -> str:
    upper = (query or "").upper()
    if semantic.get("semantic_type") == "AGGREGATION":
        if re.search(r"\bCOUNT\s*\(", upper):
            return "count_into"
        return "aggregation"
    if upper.lstrip().startswith("SELECT"):
        return "select"
    if upper.lstrip().startswith("INSERT"):
        return "insert"
    if upper.lstrip().startswith("UPDATE"):
        return "update"
    if upper.lstrip().startswith("DELETE"):
        return "delete"
    if upper.lstrip().startswith("MERGE"):
        return "merge"
    return "sql"


def build_logic_tree(source: Any) -> LogicNode:
    """Build the logic tree from PL/SQL source or structured parser output."""
    return LogicTreeBuilder().build(source)
