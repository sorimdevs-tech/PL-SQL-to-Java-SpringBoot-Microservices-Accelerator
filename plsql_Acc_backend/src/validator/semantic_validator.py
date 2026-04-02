"""
Semantic validation for generated Spring Boot code.

This layer validates repository contracts, entity field usage, import coverage,
and required behavioral preservation from the source PL/SQL semantics before
generated files are written to disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Set, Tuple

from src.utils.naming import normalize_column_name, to_pascal_case


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
class SemanticIssue:
    component: str
    object_name: str
    code: str
    message: str
    severity: str = "error"
    file_name: Optional[str] = None


@dataclass
class SemanticValidationReport:
    passed: bool
    issues: List[SemanticIssue]

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


class SemanticValidator:
    """Validate generated Spring Boot code against raw PL/SQL semantics."""

    def __init__(self, package_name: str = "com.company.project"):
        self.package_name = package_name

    def validate(
        self,
        source_units: List[Dict[str, Any]],
        entities: Dict[str, str],
        repositories: Dict[str, str],
        services: Dict[str, str],
    ) -> SemanticValidationReport:
        entity_contracts = self._extract_entity_contracts(entities)
        repository_contracts = self._extract_repository_contracts(repositories)
        issues: List[SemanticIssue] = []

        issues.extend(self._validate_repository_files(repositories))
        issues.extend(self._validate_service_files(services))
        unit_by_service = {self._derive_service_filename(unit): unit for unit in source_units}
        for service_file, service_code in services.items():
            issues.extend(
                self._validate_service_behavioral_completeness(
                    service_file,
                    service_code,
                    unit_by_service.get(service_file),
                )
            )
        issues.extend(
            self._validate_repository_usage(
                source_units=source_units,
                services=services,
                entity_contracts=entity_contracts,
                repository_contracts=repository_contracts,
            )
        )
        issues.extend(
            self._validate_deterministic_repository_contracts(
                source_units=source_units,
                repository_contracts=repository_contracts,
                repositories=repositories,
            )
        )
        issues.extend(
            self._validate_behavioral_semantics(
                source_units=source_units,
                services=services,
                repositories=repositories,
            )
        )

        return SemanticValidationReport(
            passed=not any(issue.severity == "error" for issue in issues),
            issues=issues,
        )

    def _extract_entity_contracts(self, entities: Dict[str, str]) -> Dict[str, Dict[str, Set[str]]]:
        contracts: Dict[str, Dict[str, Set[str]]] = {}
        for filename, code in entities.items():
            class_name = filename.replace(".java", "")
            fields = set(re.findall(r"private\s+(?!static)(?:[\w<>?,\s]+)\s+(\w+);", code))
            setters = set(re.findall(r"\bset([A-Z]\w*)\s*\(", code))
            getters = set(re.findall(r"\bget([A-Z]\w*)\s*\(", code))
            contracts[class_name] = {
                "fields": fields,
                "setters": setters,
                "getters": getters,
            }
        return contracts

    def _extract_repository_contracts(self, repositories: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        contracts: Dict[str, Dict[str, Any]] = {}
        for filename, code in repositories.items():
            interface_name = filename.replace(".java", "")
            method_pattern = re.compile(
                r"^\s*(?:public\s+)?(?:default\s+)?[\w<>\[\], ?.]+\s+([A-Za-z_]\w*)\s*\([^;{]*\)\s*;",
                flags=re.MULTILINE,
            )
            custom_methods = set(
                match.group(1)
                for match in method_pattern.finditer(code)
            )
            contracts[interface_name] = {
                "methods": custom_methods | STANDARD_REPOSITORY_METHODS,
                "code": code,
            }
        return contracts

    def _validate_repository_files(self, repositories: Dict[str, str]) -> List[SemanticIssue]:
        issues: List[SemanticIssue] = []
        for filename, code in repositories.items():
            interface_name = filename.replace(".java", "")
            if "JpaRepository" not in code:
                issues.append(
                    SemanticIssue(
                        component="repository",
                        object_name=interface_name,
                        code="missing_jpa_repository",
                        message=f"{interface_name} does not extend JpaRepository",
                        file_name=filename,
                    )
                )
            if "@Query" in code and "import org.springframework.data.jpa.repository.Query;" not in code:
                issues.append(
                    SemanticIssue(
                        component="repository",
                        object_name=interface_name,
                        code="missing_query_import",
                        message=f"{interface_name} uses @Query without importing Query",
                        file_name=filename,
                    )
                )
            if "@Param" in code and "import org.springframework.data.repository.query.Param;" not in code:
                issues.append(
                    SemanticIssue(
                        component="repository",
                        object_name=interface_name,
                        code="missing_param_import",
                        message=f"{interface_name} uses @Param without importing Param",
                        file_name=filename,
                    )
                )
            if "Page<" in code and "import org.springframework.data.domain.Page;" not in code:
                issues.append(
                    SemanticIssue(
                        component="repository",
                        object_name=interface_name,
                        code="missing_page_import",
                        message=f"{interface_name} uses Page without importing it",
                        file_name=filename,
                    )
                )
            if "Pageable" in code and "import org.springframework.data.domain.Pageable;" not in code:
                issues.append(
                    SemanticIssue(
                        component="repository",
                        object_name=interface_name,
                        code="missing_pageable_import",
                        message=f"{interface_name} uses Pageable without importing it",
                        file_name=filename,
                    )
                )
            if "Collection<" in code and "import java.util.Collection;" not in code:
                issues.append(
                    SemanticIssue(
                        component="repository",
                        object_name=interface_name,
                        code="missing_collection_import",
                        message=f"{interface_name} uses Collection without importing it",
                        file_name=filename,
                    )
                )
            if "LocalDateTime" in code and "import java.time.LocalDateTime;" not in code:
                issues.append(
                    SemanticIssue(
                        component="repository",
                        object_name=interface_name,
                        code="missing_localdatetime_import",
                        message=f"{interface_name} uses LocalDateTime without importing it",
                        file_name=filename,
                    )
                )
        return issues

    def _validate_service_files(self, services: Dict[str, str]) -> List[SemanticIssue]:
        issues: List[SemanticIssue] = []
        for filename, code in services.items():
            class_name = filename.replace(".java", "")
            if "@Service" in code and "import org.springframework.stereotype.Service;" not in code:
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=class_name,
                        code="missing_service_import",
                        message=f"{class_name} uses @Service without importing Service",
                        file_name=filename,
                    )
                )
            if "@Transactional" in code and "import org.springframework.transaction.annotation.Transactional;" not in code:
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=class_name,
                        code="missing_transactional_import",
                        message=f"{class_name} uses @Transactional without importing Transactional",
                        file_name=filename,
                    )
                )
            if "PageRequest" in code and "import org.springframework.data.domain.PageRequest;" not in code:
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=class_name,
                        code="missing_page_request_import",
                        message=f"{class_name} uses PageRequest without importing it",
                        file_name=filename,
                    )
                )
            if "Page<" in code and "import org.springframework.data.domain.Page;" not in code:
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=class_name,
                        code="missing_page_import",
                        message=f"{class_name} uses Page without importing it",
                        file_name=filename,
                    )
                )
            if "Pageable" in code and "import org.springframework.data.domain.Pageable;" not in code:
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=class_name,
                        code="missing_pageable_import",
                        message=f"{class_name} uses Pageable without importing it",
                        file_name=filename,
                    )
                )
            if "BigDecimal" in code and "import java.math.BigDecimal;" not in code:
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=class_name,
                        code="missing_bigdecimal_import",
                        message=f"{class_name} uses BigDecimal without importing it",
                        file_name=filename,
                    )
                )
            if "LocalDateTime" in code and "import java.time.LocalDateTime;" not in code:
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=class_name,
                        code="missing_localdatetime_import",
                        message=f"{class_name} uses LocalDateTime without importing it",
                        file_name=filename,
                    )
                )
        return issues

    def _validate_service_behavioral_completeness(
        self,
        service_file: str,
        service_code: str,
        source_unit: Optional[Dict[str, Any]] = None,
    ) -> List[SemanticIssue]:
        """Check that a generated service contains real executable behavior."""
        issues: List[SemanticIssue] = []
        object_name = service_file.replace(".java", "")
        required_operations = self._extract_required_operations(source_unit or {})
        raw_plsql = str((source_unit or {}).get('raw_plsql', ''))
        has_db_semantics = bool(required_operations) or bool((source_unit or {}).get("operations_by_table")) or bool(
            re.search(r"\b(INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|SELECT\b|MERGE\s+INTO)\b", raw_plsql, re.IGNORECASE)
        )
        has_repo_calls = self._service_has_repository_call(service_code)

        if has_db_semantics and not has_repo_calls:
            issues.append(SemanticIssue("service", object_name, "missing_repo_calls",
                                        f"{service_file}: Service method has no repository calls - method body is likely empty or stub",
                                        file_name=service_file))

        if re.search(r'findById\s*\(\s*0L\s*\)', service_code):
            issues.append(SemanticIssue("service", object_name, "stub_findbyid",
                                        f"{service_file}: findById(0L) hardcoded stub - lookup key was not resolved",
                                        file_name=service_file))

        if self._service_has_stub_transaction_comment(service_code):
            issues.append(SemanticIssue("service", object_name, "stub_transaction",
                                        f"{service_file}: Transaction boundary is a comment stub - must be real code",
                                        file_name=service_file))

        has_error_declared = bool(re.search(r'boolean\s+hasError\s*=', service_code))
        has_error_used = bool(
            re.search(r'if\s*\(\s*(?:has|batch)Error\s*\)', service_code)
            or re.search(r'\bhasError\s*=\s*hasError\s*\|\|', service_code)
            or re.search(r'\blog\w*\([^;\n]*hasError', service_code)
        )
        if has_error_declared and not has_error_used:
            issues.append(SemanticIssue("service", object_name, "unused_haserror",
                                        f"{service_file}: hasError flag is declared but never checked - post-loop logic missing",
                                        severity="warning", file_name=service_file))

        if re.search(r'for\s*\(\s*int\s+rowIndex\s*=\s*0\s*;\s*rowIndex\s*<\s*1\s*;', service_code):
            issues.append(SemanticIssue("service", object_name, "fake_loop",
                                        f"{service_file}: Fake single-iteration loop detected - should fetch real data or use proper loop",
                                        file_name=service_file))

        if re.search(r'\bMERGE\s+INTO\b', raw_plsql, re.IGNORECASE):
            if 'isPresent' not in service_code and 'orElse' not in service_code:
                issues.append(SemanticIssue("service", object_name, "missing_upsert_logic",
                                            f"{service_file}: SQL has MERGE INTO but service has no Optional-based UPSERT logic",
                                            file_name=service_file))
        if re.search(r'\bEXCEPTION\b', raw_plsql, re.IGNORECASE) and not self._service_has_catch_block(service_code):
            issues.append(SemanticIssue("service", object_name, "missing_catch",
                                        f"{service_file}: SQL has EXCEPTION block but service has no try/catch",
                                        file_name=service_file))
        return issues

    def _validate_repository_usage(
        self,
        source_units: List[Dict[str, Any]],
        services: Dict[str, str],
        entity_contracts: Dict[str, Dict[str, Set[str]]],
        repository_contracts: Dict[str, Dict[str, Any]],
    ) -> List[SemanticIssue]:
        issues: List[SemanticIssue] = []
        for unit in source_units:
            service_filename = self._derive_service_filename(unit)
            service_code = services.get(service_filename, "")
            if not service_code:
                # Skip validation for source units that don't have a corresponding service file
                # This can happen for utility functions or procedures that are merged into other services
                continue

            repo_vars = self._extract_repository_variables(service_code)
            entity_vars = self._extract_entity_variables(service_code, entity_contracts.keys())

            for repo_var, repo_type in repo_vars.items():
                contract = repository_contracts.get(repo_type)
                if not contract:
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=unit.get("name", ""),
                            code="missing_repository_type",
                            message=f"{service_filename} references unknown repository type {repo_type}",
                            file_name=service_filename,
                        )
                    )
                    continue

                call_pattern = re.compile(rf"\b{re.escape(repo_var)}\.(\w+)\s*\(")
                for match in call_pattern.finditer(service_code):
                    method_name = match.group(1)
                    if method_name not in contract["methods"]:
                        issues.append(
                            SemanticIssue(
                                component="service",
                                object_name=unit.get("name", ""),
                                code="missing_repository_method",
                                message=f"{service_filename} calls {repo_type}.{method_name}() but that method is not declared",
                                file_name=service_filename,
                            )
                        )

            # TEMPORARILY DISABLED: Re-enabled entity field validation found real issues.
            # The LLM is generating code like row.getVideoid() for fields that don't exist
            # in BookEntity. With the improved LLM prompts and enhanced table metadata now
            # available, future iterations can fix the LLM to not generate these calls.
            # 
            # RE-ENABLED (December 21): Metadata integration now provides entity field information
            # Services receive table metadata and validate field access. This validation catches
            # invalid field references before they reach clients.
            
            setter_pattern = re.compile(r"\b(\w+)\.set([A-Z]\w*)\s*\(")
            getter_pattern = re.compile(r"\b(\w+)\.get([A-Z]\w*)\s*\(")
            for match in setter_pattern.finditer(service_code):
                var_name, setter_suffix = match.groups()
                entity_name = entity_vars.get(var_name)
                if not entity_name:
                    # Skip if the variable is not a declared entity (could be a transient object)
                    continue
                if setter_suffix not in entity_contracts.get(entity_name, {}).get("setters", set()):
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=unit.get("name", ""),
                            code="invalid_entity_setter",
                            message=f"{service_filename} calls {var_name}.set{setter_suffix}() but {entity_name} does not define it",
                            file_name=service_filename,
                       )
                    )
            for match in getter_pattern.finditer(service_code):
                var_name, getter_suffix = match.groups()
                entity_name = entity_vars.get(var_name)
                if not entity_name:
                    # Skip if the variable is not a declared entity (could be a transient object)
                    continue
                if getter_suffix not in entity_contracts.get(entity_name, {}).get("getters", set()):
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=unit.get("name", ""),
                            code="invalid_entity_getter",
                            message=f"{service_filename} calls {var_name}.get{getter_suffix}() but {entity_name} does not define it",
                            file_name=service_filename,
                        )
                    )
        return issues

    def _validate_behavioral_semantics(
        self,
        source_units: List[Dict[str, Any]],
        services: Dict[str, str],
        repositories: Dict[str, str],
    ) -> List[SemanticIssue]:
        issues: List[SemanticIssue] = []
        for unit in source_units:
            service_filename = self._derive_service_filename(unit)
            service_code = services.get(service_filename, "")
            if not service_code:
                # Skip validation for source units that don't have a corresponding service file
                # This can happen for utility functions or procedures that are merged into other services
                continue
            object_name = unit.get("name", "")
            raw_plsql = unit.get("raw_plsql", "")
            expected_method_name = self._to_camel_case(
                str(unit.get("subprogram_name") or unit.get("name") or "")
            )
            has_exception_block = bool(re.search(r"\bexception\b", raw_plsql, flags=re.IGNORECASE))
            semantic = unit.get("semantic_analysis") or {}
            required_operations = self._extract_required_operations(unit)
            driving_table = str(unit.get("driving_table", "")).upper()
            target_tables = {str(table).upper() for table in (unit.get("target_tables") or []) if table}
            for ref in semantic.get("aggregation", {}).get("columns", []) or []:
                parts = str(ref).split(".", 1)
                if len(parts) == 2 and parts[0].strip():
                    target_tables.add(parts[0].strip().upper())
            if driving_table:
                target_tables.add(driving_table)

            if expected_method_name and not re.search(
                rf"\bpublic\s+\w+\s+{re.escape(expected_method_name)}\s*\(",
                service_code,
            ):
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=object_name,
                        code="missing_expected_service_method",
                        message=f"{service_filename} is missing expected method {expected_method_name}(...)",
                        file_name=service_filename,
                    )
                )

            if required_operations and "No SQL operations" in service_code:
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=object_name,
                        code="placeholder_logic_for_dml_unit",
                        message=f"{service_filename} contains placeholder utility logic despite PL/SQL DML operations",
                        file_name=service_filename,
                    )
                )

            if required_operations and re.search(
                r"\b(TODO|UnsupportedOperationException|not\s+implemented)\b",
                service_code,
                flags=re.IGNORECASE,
            ):
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=object_name,
                        code="unimplemented_logic_detected",
                        message=f"{service_filename} contains TODO/not-implemented logic for an executable PL/SQL unit",
                        file_name=service_filename,
                    )
                )

            if required_operations:
                repository_vars = self._extract_repository_variables(service_code)
                has_repository_call = any(
                    re.search(rf"\b{re.escape(repo_var)}\.\w+\s*\(", service_code)
                    for repo_var in repository_vars
                )
                if not has_repository_call:
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="missing_repository_calls_for_dml",
                            message=f"{service_filename} has DML semantics but no repository method invocations",
                            file_name=service_filename,
                        )
                    )

                operation_patterns = {
                    "INSERT": [r"\.\s*(insert\w*|save|saveAndFlush)\s*\("],
                    "UPDATE": [r"\.\s*(update\w*|save|saveAndFlush)\s*\("],
                    "DELETE": [r"\.\s*(delete\w*|remove\w*)\s*\("],
                    "SELECT": [r"\.\s*(find\w*|sumBy\w*|count\w*)\s*\("],
                }
                for operation in sorted(required_operations):
                    if operation not in operation_patterns:
                        continue
                    patterns = operation_patterns[operation]
                    if not any(re.search(pattern, service_code) for pattern in patterns):
                        issues.append(
                            SemanticIssue(
                                component="service",
                                object_name=object_name,
                                code=f"operation_not_preserved_{operation.lower()}",
                                message=(
                                    f"{service_filename} does not preserve required {operation} behavior "
                                    f"from the source PL/SQL unit"
                                ),
                                file_name=service_filename,
                            )
                        )

            for table_name in sorted(target_tables):
                repository_name = self._derive_repository_name_from_table(table_name)
                repository_filename = f"{repository_name}.java"
                if repository_filename not in repositories:
                    continue
                if repository_name not in service_code:
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="missing_repository_injection",
                            message=f"{service_filename} is missing repository injection for {repository_name}",
                            file_name=service_filename,
                        )
                    )

            aggregation_tables = {
                str(ref).split(".", 1)[0].strip().upper()
                for ref in (semantic.get("aggregation", {}).get("columns", []) or [])
                if "." in str(ref)
            }
            for table_name in sorted(aggregation_tables):
                repository_name = self._derive_repository_name_from_table(table_name)
                repository_filename = f"{repository_name}.java"
                repository_code = repositories.get(repository_filename, "")
                if not repository_code:
                    continue
                repository_var = self._lower_first(repository_name)
                if "sumBy" not in repository_code:
                    issues.append(
                        SemanticIssue(
                            component="repository",
                            object_name=object_name,
                            code="missing_aggregation_repository_method",
                            message=f"{repository_filename} must expose SUM aggregation methods (sumBy...)",
                            file_name=repository_filename,
                        )
                    )
                if not re.search(rf"\b{re.escape(repository_var)}\.sumBy\w*\s*\(", service_code):
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="aggregation_not_preserved",
                            message=f"{service_filename} must use repository sumBy... methods for table {table_name}",
                            file_name=service_filename,
                        )
                    )
                if re.search(rf"\b{re.escape(repository_var)}\.findBy\w+\s*\(", service_code):
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="aggregation_entity_fetch_misuse",
                            message=f"{service_filename} should not use findBy... for aggregation table {table_name}",
                            file_name=service_filename,
                        )
                    )

            if driving_table and (
                bool(unit.get("cursor"))
                or any(str(op.get("type", "")).upper() == "BULK_COLLECT" for op in (unit.get("bulk_operations") or []))
            ):
                driving_repo_name = self._derive_repository_name_from_table(driving_table)
                driving_repo_var = self._lower_first(driving_repo_name)
                if not re.search(
                    rf"\b{re.escape(driving_repo_var)}\.(findPageForUpdateSkipLocked\w*|findAll)\s*\(",
                    service_code,
                ):
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="wrong_driving_table_used",
                            message=f"{service_filename} does not page over driving table {driving_table}",
                            file_name=service_filename,
                        )
                    )

            if re.search(r"\bmerge\s+into\b", raw_plsql, flags=re.IGNORECASE):
                has_find_by = bool(re.search(r"\.findBy\w+\s*\(", service_code))
                has_is_present = ".isPresent()" in service_code
                has_if_else = bool(re.search(r"\bif\s*\(.*?isPresent\s*\(\).*?\)\s*\{[\s\S]*?\}\s*else\s*\{", service_code))
                if not (has_find_by and has_is_present and has_if_else):
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="merge_not_preserved",
                            message=f"{service_filename} must implement MERGE using findBy + if(existing.isPresent()) + else",
                            file_name=service_filename,
                        )
                    )

            bulk_operations = unit.get("bulk_operations", []) or []
            if any(str(item.get("type", "")).upper() == "BULK_COLLECT" for item in bulk_operations):
                has_page_request = "PageRequest" in service_code
                has_loop = bool(re.search(r"\b(while|for)\b", service_code))
                uses_find_all_no_paging = bool(re.search(r"\.findAll\s*\(\s*\)", service_code))
                if not has_page_request:
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="missing_page_request_import",
                            message=f"{service_filename} must use PageRequest for BULK COLLECT conversion",
                            file_name=service_filename,
                        )
                    )
                if not (has_page_request and has_loop):
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="bulk_collect_not_preserved",
                            message=f"{service_filename} does not preserve BULK COLLECT as batched pagination logic",
                            file_name=service_filename,
                        )
                    )
                if uses_find_all_no_paging:
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="findall_misuse",
                            message=f"{service_filename} uses findAll() without paging for BULK COLLECT",
                            file_name=service_filename,
                        )
                    )

            cursor = unit.get("cursor", {}) or {}
            locking = str(cursor.get("locking", "")).upper()
            if cursor:
                uses_stream_or_paging = (
                    "PageRequest" in service_code
                    or bool(re.search(r"\bStream<", service_code))
                    or bool(re.search(r"\.findPageForUpdateSkipLocked\w*\s*\(", service_code))
                )
                if not uses_stream_or_paging:
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="cursor_not_preserved",
                            message=f"{service_filename} must map cursor processing to pagination or streaming",
                            file_name=service_filename,
                        )
                    )
                if re.search(r"\.findAll\s*\(\s*\)", service_code):
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="findall_misuse",
                            message=f"{service_filename} uses full-table findAll() for cursor workflow",
                            file_name=service_filename,
                        )
                    )
            if "SKIP LOCKED" in locking:
                expected_table = driving_table or str(next(iter((unit.get("operations_by_table") or {}).keys()), "")).upper()
                expected_repo = self._derive_repository_name_from_table(expected_table) if expected_table else ""
                repo_code = repositories.get(f"{expected_repo}.java", "") if expected_repo else ""
                if "findPageForUpdateSkipLocked" not in repo_code:
                    issues.append(
                        SemanticIssue(
                            component="repository",
                            object_name=object_name,
                            code="skip_locked_not_preserved",
                            message=f"{object_name} requires SKIP LOCKED on driving table {expected_table}",
                            file_name=f"{expected_repo}.java" if expected_repo else None,
                        )
                    )

            transaction = unit.get("transaction", {}) or {}
            has_transaction_boundary = (
                "@Transactional" in service_code
                or "TransactionTemplate" in service_code
                or "setRollbackOnly" in service_code
                or "PlatformTransactionManager" in service_code
                or ("hasError" in service_code and "batchHasError" in service_code)
            )
            if transaction.get("has_savepoint") and not has_transaction_boundary:
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=object_name,
                        code="transaction_not_preserved",
                        message=f"{service_filename} does not preserve PL/SQL transaction boundaries",
                        file_name=service_filename,
                    )
                )
            has_iterative_semantics = (
                bool(unit.get("cursor"))
                or any(str(item.get("type", "")).upper() == "BULK_COLLECT" for item in (unit.get("bulk_operations") or []))
                or bool(re.search(r"\b(for|while)\b.+\bloop\b", raw_plsql, flags=re.IGNORECASE | re.DOTALL))
            )
            if transaction.get("has_savepoint") or (has_exception_block and has_iterative_semantics):
                has_loop = bool(re.search(r"\b(for|while)\s*\(", service_code, flags=re.IGNORECASE))
                has_try = "try {" in service_code or bool(re.search(r"\btry\s*\{", service_code))
                has_catch = self._service_has_catch_block(service_code)
                has_continue = "continue;" in service_code
                has_row_level_try = bool(
                    re.search(
                        r"\b(for|while)\s*\([^\)]*\)\s*\{[\s\S]{0,800}?\btry\s*\{",
                        service_code,
                        flags=re.IGNORECASE,
                    )
                )
                if not ((has_row_level_try and has_catch and has_continue) or (has_loop and has_try and has_catch and has_continue)):
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="missing_row_level_try_catch",
                            message=f"{service_filename} must preserve SAVEPOINT/EXCEPTION semantics with row-level try/catch + continue",
                            file_name=service_filename,
                        )
                    )
            elif has_exception_block:
                has_try = "try {" in service_code or bool(re.search(r"\btry\s*\{", service_code))
                has_catch = self._service_has_catch_block(service_code)
                if not (has_try and has_catch):
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="missing_exception_mapping",
                            message=f"{service_filename} must preserve EXCEPTION handling with try/catch",
                            file_name=service_filename,
                        )
                    )

            if self._uses_crud_switch_for_mode(unit, service_code):
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=object_name,
                        code="mode_flag_misused",
                        message=f"{service_filename} treats a mode flag as a CRUD operation switch",
                        file_name=service_filename,
                    )
                )
            if self._has_run_mode_parameter(unit) and "FULL" in raw_plsql.upper() and "\"FULL\"" not in service_code:
                issues.append(
                    SemanticIssue(
                        component="service",
                        object_name=object_name,
                        code="run_mode_not_preserved",
                        message=f"{service_filename} does not preserve run_mode FULL guard semantics",
                        file_name=service_filename,
                    )
                )

            # RC4 FIX: if source has raise_application_error, Java must throw BusinessException
            programmatic_raises = unit.get("programmatic_raises") or []
            if programmatic_raises:
                has_throw = bool(re.search(r"\bthrow\s+new\s+\w*[Ee]xception\b", service_code))
                if not has_throw:
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="raise_application_error_not_preserved",
                            message=(
                                f"{service_filename} source has RAISE_APPLICATION_ERROR but "
                                f"no 'throw new ...Exception' found in generated service"
                            ),
                            file_name=service_filename,
                        )
                    )

            # RC8 FIX: if source has PRAGMA AUTONOMOUS_TRANSACTION, Java must use REQUIRES_NEW
            if unit.get("autonomous_transaction"):
                has_requires_new = "Propagation.REQUIRES_NEW" in service_code
                if not has_requires_new:
                    issues.append(
                        SemanticIssue(
                            component="service",
                            object_name=object_name,
                            code="autonomous_transaction_not_preserved",
                            message=(
                                f"{service_filename} source uses PRAGMA AUTONOMOUS_TRANSACTION but "
                                f"generated service is missing @Transactional(propagation = Propagation.REQUIRES_NEW)"
                            ),
                            file_name=service_filename,
                        )
                    )
        return issues

    def _extract_required_operations(self, unit: Dict[str, Any]) -> Set[str]:
        required: Set[str] = set()
        for operations in (unit.get("operations_by_table") or {}).values():
            for operation in (operations or []):
                op = str(operation).upper()
                if op in {"SELECT", "INSERT", "UPDATE", "DELETE", "MERGE"}:
                    required.add(op)
        for upsert in (unit.get("semantic_analysis") or {}).get("upsert_operations", []) or []:
            if str(upsert.get("operation", "")).upper() == "UPSERT":
                required.add("MERGE")
        return required

    def _service_has_repository_call(self, service_code: str) -> bool:
        repo_vars = self._extract_repository_variables(service_code)
        for repo_var in repo_vars:
            if re.search(rf"\b{re.escape(repo_var)}\.\w+\s*\(", service_code):
                return True
        return bool(
            re.search(
                r'\.(save(?:All|AndFlush)?|find\w*|exists\w*|delete\w*|update\w*|insert\w*|flush|sum\w*|count\w*)\s*\(',
                service_code,
            )
        )

    def _service_has_catch_block(self, service_code: str) -> bool:
        return bool(re.search(r"\bcatch\s*\([^\)]+\)", service_code, flags=re.IGNORECASE))

    def _service_has_stub_transaction_comment(self, service_code: str) -> bool:
        return bool(
            re.search(
                r'//\s*(?:commit|rollback)\s+boundary\s+handled\s+per\s+batch',
                service_code,
                flags=re.IGNORECASE,
            )
        )

    def _validate_deterministic_repository_contracts(
        self,
        source_units: List[Dict[str, Any]],
        repository_contracts: Dict[str, Dict[str, Any]],
        repositories: Dict[str, str],
    ) -> List[SemanticIssue]:
        issues: List[SemanticIssue] = []
        for unit in source_units:
            object_name = unit.get("name", "")
            lookup_map = unit.get("lookup_keys") or {}
            operations_by_table = {
                str(table_name).upper()
                for table_name in (unit.get("operations_by_table") or {}).keys()
                if table_name
            }
            skip_locked_tables = {
                str(table).upper()
                for table in (unit.get("skip_locked_tables") or [])
                if table
            }
            driving_table = str(unit.get("driving_table", "")).upper()
            if not skip_locked_tables and re.search(r"\bSKIP\s+LOCKED\b", str(unit.get("raw_plsql", "")), flags=re.IGNORECASE):
                if driving_table:
                    skip_locked_tables.add(driving_table)
            for table_name, lookup_keys in lookup_map.items():
                if not lookup_keys:
                    continue
                normalized_table = str(table_name).upper()
                if normalized_table not in operations_by_table and normalized_table not in skip_locked_tables:
                    # Ignore lookup hints from joined/read-only tables that are not directly
                    # represented as repository operations for this unit.
                    continue
                repository_name = self._derive_repository_name_from_table(str(table_name))
                repository_code = repositories.get(f"{repository_name}.java", "")
                contract = repository_contracts.get(repository_name)
                if not contract:
                    issues.append(
                        SemanticIssue(
                            component="repository",
                            object_name=object_name,
                            code="missing_repository_for_table",
                            message=f"Missing deterministic repository {repository_name} for table {table_name}",
                            file_name=f"{repository_name}.java",
                        )
                    )
                    continue
                expected_method = self._expected_lookup_method_name(list(lookup_keys))
                if not self._has_lookup_method_for_keys(contract.get("methods", set()), list(lookup_keys)):
                    issues.append(
                        SemanticIssue(
                            component="repository",
                            object_name=object_name,
                            code="missing_lookup_repository_method",
                            message=f"{repository_name} must declare {expected_method}(...) derived from lookup_keys",
                            file_name=f"{repository_name}.java",
                        )
                    )
                if str(table_name).upper() in skip_locked_tables:
                    if "findPageForUpdateSkipLocked" not in repository_code:
                        issues.append(
                            SemanticIssue(
                                component="repository",
                                object_name=object_name,
                                code="missing_skip_locked_method",
                                message=f"{repository_name} must declare findPageForUpdateSkipLocked(Pageable pageable)",
                                file_name=f"{repository_name}.java",
                            )
                        )
        return issues

    def _extract_repository_variables(self, service_code: str) -> Dict[str, str]:
        repo_vars: Dict[str, str] = {}
        field_pattern = re.compile(r"(?:private|final)\s+(\w+Repository)\s+(\w+)\s*;")
        constructor_pattern = re.compile(r"(\w+Repository)\s+(\w+)(?=[,\)])")
        for repo_type, repo_var in field_pattern.findall(service_code):
            repo_vars[repo_var] = repo_type
        for repo_type, repo_var in constructor_pattern.findall(service_code):
            repo_vars.setdefault(repo_var, repo_type)
        return repo_vars

    def _extract_entity_variables(
        self,
        service_code: str,
        entity_names: Set[str],
    ) -> Dict[str, str]:
        entity_vars: Dict[str, str] = {}
        declaration_pattern = re.compile(r"\b(\w+Entity)\s+(\w+)\s*=")
        for entity_type, var_name in declaration_pattern.findall(service_code):
            if entity_type in entity_names:
                entity_vars[var_name] = entity_type
        return entity_vars

    def _uses_crud_switch_for_mode(self, unit: Dict[str, Any], service_code: str) -> bool:
        mode_params = [
            param.get("name", "")
            for param in unit.get("input_parameters", [])
            if "mode" in str(param.get("name", "")).lower()
        ]
        if not mode_params:
            return False
        for param_name in mode_params:
            legacy_parts = [token for token in re.split(r"[^A-Za-z0-9]+", param_name or "") if token]
            legacy_camel = (
                legacy_parts[0][:1].lower() + legacy_parts[0][1:] + "".join(
                    token[:1].upper() + token[1:]
                    for token in legacy_parts[1:]
                )
                if legacy_parts else param_name
            )
            variants = {
                param_name,
                self._to_camel_case(param_name),
                legacy_camel,
            }
            for variant in variants:
                if re.search(
                    rf"\bswitch\s*\(\s*{re.escape(variant)}\s*\)\s*\{{[\s\S]*?\bcase\s+\"?(INSERT|UPDATE|DELETE|SELECT)\"?",
                    service_code,
                    flags=re.IGNORECASE,
                ):
                    return True
                if re.search(
                    rf"\bif\s*\([^)]*{re.escape(variant)}[^)]*(?:==|!=|equals|equalsIgnoreCase)\s*\"?(INSERT|UPDATE|DELETE|SELECT)\"?[^)]*\)",
                    service_code,
                    flags=re.IGNORECASE,
                ):
                    return True
                if re.search(
                    rf"\bif\s*\([^)]*\"?(INSERT|UPDATE|DELETE|SELECT)\"?[^)]*(?:==|!=|equals|equalsIgnoreCase)\s*{re.escape(variant)}[^)]*\)",
                    service_code,
                    flags=re.IGNORECASE,
                ):
                    return True
        return False

    def _expected_lookup_method_name(self, lookup_keys: List[str]) -> str:
        suffix = "And".join(
            normalize_column_name(key)[:1].upper() + normalize_column_name(key)[1:]
            for key in lookup_keys
            if normalize_column_name(key)
        )
        return f"findBy{suffix}" if suffix else "findById"

    def _lookup_method_parts(self, method_name: str) -> List[str]:
        if not method_name.startswith("findBy"):
            return []
        suffix = method_name[len("findBy"):]
        if not suffix:
            return []
        return [part.lower() for part in suffix.split("And") if part]

    def _has_lookup_method_for_keys(self, methods: Set[str], lookup_keys: List[str]) -> bool:
        expected_parts = [
            normalize_column_name(key).lower()
            for key in (lookup_keys or [])
            if normalize_column_name(key)
        ]
        if not expected_parts:
            return True
        expected_method = self._expected_lookup_method_name(lookup_keys)
        if expected_method in methods:
            return True
        for method_name in methods:
            parts = self._lookup_method_parts(method_name)
            if not parts:
                continue
            if all(part in parts for part in expected_parts):
                return True
        return False

    def _derive_repository_name_from_table(self, table_name: str) -> str:
        base = to_pascal_case(table_name)
        return f"{base}Repository" if base else "GeneratedRepository"

    def _has_run_mode_parameter(self, unit: Dict[str, Any]) -> bool:
        return any(
            "mode" in str(param.get("name", "")).lower()
            for param in (unit.get("input_parameters") or [])
        )

    def _to_camel_case(self, value: str) -> str:
        return normalize_column_name(value)

    def _lower_first(self, value: str) -> str:
        if not value:
            return value
        return value[:1].lower() + value[1:]

    def _derive_service_filename(self, unit: Dict[str, Any]) -> str:
        words = [token.capitalize() for token in re.split(r"[^A-Za-z0-9]+", unit.get("name", "")) if token]
        base_name = "".join(words) or "Generated"
        if not base_name.endswith("Service"):
            base_name = f"{base_name}Service"
        return f"{base_name}.java"
