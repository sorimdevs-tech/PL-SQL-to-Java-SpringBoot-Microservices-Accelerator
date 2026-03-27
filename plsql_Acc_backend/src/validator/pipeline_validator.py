"""
Pipeline-level validation for deterministic PL/SQL -> Spring conversion output.

This validator enforces hard safety rules that are not covered by semantic checks:
- no stub logic
- no empty DTOs
- no null/empty entity saves
- every routine unit has an implementation
- repository custom methods are consumed
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set

from src.utils.naming import normalize_column_name
from src.validator.semantic_enforcement import SemanticEnforcementEngine


STANDARD_REPOSITORY_METHODS = {
    "save",
    "saveAll",
    "saveAndFlush",
    "findById",
    "findAll",
    "existsById",
    "deleteById",
    "delete",
    "flush",
}


@dataclass
class PipelineIssue:
    component: str
    object_name: str
    code: str
    message: str
    severity: str = "error"
    file_name: Optional[str] = None


@dataclass
class PipelineValidationReport:
    passed: bool
    issues: List[PipelineIssue]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [asdict(issue) for issue in self.issues],
        }

    def feedback_by_component(self, component: str) -> Dict[str, List[str]]:
        grouped: Dict[str, List[str]] = {}
        for issue in self.issues:
            if issue.component != component:
                continue
            grouped.setdefault(issue.object_name, []).append(issue.message)
        return grouped


class PipelineValidationEngine:
    def __init__(self, package_name: str = "com.company.project"):
        self.package_name = package_name
        self.semantic_enforcement = SemanticEnforcementEngine()

    def validate(
        self,
        source_units: List[Dict[str, Any]],
        entities: Dict[str, str],
        repositories: Dict[str, str],
        services: Dict[str, str],
        controllers: Dict[str, str],
    ) -> PipelineValidationReport:
        issues: List[PipelineIssue] = []
        issues.extend(self._validate_all_routines_implemented(source_units, services))
        issues.extend(self._validate_service_stub_patterns(services))
        issues.extend(self._validate_entity_save_guards(services))
        issues.extend(self._validate_dto_shapes(services, controllers))
        issues.extend(self._validate_repository_method_usage(repositories, services))
        issues.extend(self._validate_semantic_enforcement(source_units, repositories, services))
        return PipelineValidationReport(
            passed=not any(issue.severity == "error" for issue in issues),
            issues=issues,
        )

    def _service_filename_for_unit(self, unit: Dict[str, Any]) -> str:
        words = [token.capitalize() for token in re.split(r"[^A-Za-z0-9]+", str(unit.get("name", ""))) if token]
        base_name = "".join(words) or "Generated"
        if not base_name.endswith("Service"):
            base_name = f"{base_name}Service"
        return f"{base_name}.java"

    def _service_method_for_unit(self, unit: Dict[str, Any]) -> str:
        return normalize_column_name(str(unit.get("name", "")) or "execute")

    def _validate_all_routines_implemented(
        self,
        source_units: List[Dict[str, Any]],
        services: Dict[str, str],
    ) -> List[PipelineIssue]:
        issues: List[PipelineIssue] = []
        for unit in source_units or []:
            object_type = str(unit.get("object_type", "")).upper()
            if object_type in {"TRIGGER", "PACKAGE"}:
                continue
            service_file = self._service_filename_for_unit(unit)
            service_code = services.get(service_file)
            if not service_code:
                issues.append(
                    PipelineIssue(
                        component="service",
                        object_name=str(unit.get("name", "")),
                        code="missing_routine_service",
                        message=f"Missing service implementation for routine {unit.get('name', '')}",
                        file_name=service_file,
                    )
                )
                continue
            method_name = self._service_method_for_unit(unit)
            method_pattern = re.compile(
                rf"\bpublic\s+(?:static\s+)?[\w<>\[\], ?]+\s+{re.escape(method_name)}\s*\(",
                flags=re.IGNORECASE,
            )
            if not method_pattern.search(service_code):
                issues.append(
                    PipelineIssue(
                        component="service",
                        object_name=str(unit.get("name", "")),
                        code="missing_routine_method",
                        message=f"{service_file} does not expose method {method_name}() for source routine",
                        file_name=service_file,
                    )
                )
        return issues

    def _validate_service_stub_patterns(self, services: Dict[str, str]) -> List[PipelineIssue]:
        issues: List[PipelineIssue] = []
        stub_signatures = [
            (r"\bTODO\b", "todo_stub"),
            (r"\bnot implemented\b", "not_implemented_stub"),
            (r"UnsupportedOperationException", "unsupported_operation_stub"),
            (r"for\s*\(\s*int\s+rowIndex\s*=\s*0\s*;\s*rowIndex\s*<\s*1\s*;", "fake_loop_stub"),
            (r"\bplaceholder\b", "placeholder_stub"),
        ]
        for filename, code in (services or {}).items():
            class_name = filename.replace(".java", "")
            for pattern, issue_code in stub_signatures:
                if re.search(pattern, code, flags=re.IGNORECASE):
                    issues.append(
                        PipelineIssue(
                            component="service",
                            object_name=class_name,
                            code=issue_code,
                            message=f"{filename} contains stub pattern ({issue_code})",
                            file_name=filename,
                        )
                    )
        return issues

    def _validate_entity_save_guards(self, services: Dict[str, str]) -> List[PipelineIssue]:
        issues: List[PipelineIssue] = []
        save_call_pattern = re.compile(r"\b(\w+)\.save\s*\(\s*([A-Za-z_]\w*|null|new\s+\w+\s*\(\s*\))\s*\)")
        for filename, code in (services or {}).items():
            class_name = filename.replace(".java", "")
            for repo_var, argument in save_call_pattern.findall(code):
                arg = argument.strip()
                if arg.lower() == "null":
                    issues.append(
                        PipelineIssue(
                            component="service",
                            object_name=class_name,
                            code="null_entity_save",
                            message=f"{filename} invokes {repo_var}.save(null)",
                            file_name=filename,
                        )
                    )
                    continue

                if arg.startswith("new "):
                    issues.append(
                        PipelineIssue(
                            component="service",
                            object_name=class_name,
                            code="inline_empty_entity_save",
                            message=f"{filename} invokes {repo_var}.save({arg}) without population guard",
                            file_name=filename,
                        )
                    )
                    continue

                constructor_pattern = re.compile(
                    rf"\b\w+\s+{re.escape(arg)}\s*=\s*new\s+\w+\s*\(\s*\)\s*;",
                    flags=re.MULTILINE,
                )
                if not constructor_pattern.search(code):
                    continue
                setter_pattern = re.compile(rf"\b{re.escape(arg)}\.set[A-Z]\w*\s*\(")
                if not setter_pattern.search(code):
                    issues.append(
                        PipelineIssue(
                            component="service",
                            object_name=class_name,
                            code="unpopulated_entity_save",
                            message=f"{filename} saves {arg} without any field assignment",
                            file_name=filename,
                        )
                    )
        return issues

    def _extract_java_classes(self, code: str) -> List[Dict[str, str]]:
        classes: List[Dict[str, str]] = []
        class_pattern = re.compile(r"\bclass\s+([A-Za-z_]\w*)\b")
        for match in class_pattern.finditer(code or ""):
            class_name = match.group(1)
            brace_start = code.find("{", match.end())
            if brace_start < 0:
                continue
            depth = 0
            end = -1
            for index in range(brace_start, len(code)):
                ch = code[index]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = index
                        break
            if end < 0:
                continue
            classes.append({"name": class_name, "body": code[brace_start + 1 : end]})
        return classes

    def _validate_dto_shapes(
        self,
        services: Dict[str, str],
        controllers: Dict[str, str],
    ) -> List[PipelineIssue]:
        issues: List[PipelineIssue] = []
        for filename, code in {**(services or {}), **(controllers or {})}.items():
            for cls in self._extract_java_classes(code):
                class_name = cls["name"]
                if not class_name.endswith("DTO"):
                    continue
                body = cls["body"]
                fields = re.findall(r"\bprivate\s+(?!static)[\w<>, ?]+\s+([A-Za-z_]\w*)\s*;", body)
                if not fields:
                    issues.append(
                        PipelineIssue(
                            component="dto",
                            object_name=class_name,
                            code="empty_dto",
                            message=f"{filename} contains empty DTO class {class_name}",
                            file_name=filename,
                        )
                    )
        return issues

    def _extract_repository_contracts(self, repositories: Dict[str, str]) -> Dict[str, Set[str]]:
        contracts: Dict[str, Set[str]] = {}
        method_pattern = re.compile(
            r"^\s*(?:public\s+)?(?:default\s+)?[\w<>\[\], ?.]+\s+([A-Za-z_]\w*)\s*\([^;{]*\)\s*;",
            flags=re.MULTILINE,
        )
        for filename, code in (repositories or {}).items():
            repo_name = filename.replace(".java", "")
            methods = set(match.group(1) for match in method_pattern.finditer(code))
            contracts[repo_name] = methods
        return contracts

    def _extract_repository_calls(self, services: Dict[str, str]) -> Dict[str, Set[str]]:
        calls: Dict[str, Set[str]] = {}
        for _, code in (services or {}).items():
            field_map: Dict[str, str] = {}
            for repo_type, repo_var in re.findall(r"(?:private|final)\s+(\w+Repository)\s+(\w+)\s*;", code):
                field_map[repo_var] = repo_type
            for repo_type, repo_var in re.findall(r"(\w+Repository)\s+(\w+)(?=[,\)])", code):
                field_map.setdefault(repo_var, repo_type)
            for repo_var, method in re.findall(r"\b([A-Za-z_]\w*)\.(\w+)\s*\(", code):
                repo_type = field_map.get(repo_var)
                if not repo_type:
                    continue
                calls.setdefault(repo_type, set()).add(method)
        return calls

    def _validate_repository_method_usage(
        self,
        repositories: Dict[str, str],
        services: Dict[str, str],
    ) -> List[PipelineIssue]:
        issues: List[PipelineIssue] = []
        contracts = self._extract_repository_contracts(repositories)
        calls = self._extract_repository_calls(services)
        for repo_name, methods in contracts.items():
            custom_methods = {m for m in methods if m not in STANDARD_REPOSITORY_METHODS}
            if not custom_methods:
                continue
            used = calls.get(repo_name, set())
            unused = sorted(custom_methods - used)
            if unused:
                issues.append(
                    PipelineIssue(
                        component="repository",
                        object_name=repo_name,
                        code="unused_repository_methods",
                        message=f"{repo_name} has unused custom methods: {', '.join(unused)}",
                        file_name=f"{repo_name}.java",
                    )
                )
        return issues

    def _validate_semantic_enforcement(
        self,
        source_units: List[Dict[str, Any]],
        repositories: Dict[str, str],
        services: Dict[str, str],
    ) -> List[PipelineIssue]:
        issues: List[PipelineIssue] = []
        for issue in self.semantic_enforcement.validate(source_units, repositories, services):
            issues.append(
                PipelineIssue(
                    component=issue.component,
                    object_name=issue.object_name,
                    code=issue.code,
                    message=issue.message,
                    severity=issue.severity,
                    file_name=issue.file_name,
                )
            )
        return issues
