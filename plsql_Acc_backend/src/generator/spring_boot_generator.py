"""
Spring Boot Project Generator for PL/SQL Modernization Platform
Generates complete Spring Boot projects from converted Java code

FIXES APPLIED:
  SBG-1  : server.port wrong key in application.properties
  SBG-2  : server.port nested under spring: in application.yml
  SBG-3  : No Spring Boot version validation
  SBG-4  : Artifact ID truncated for short coordinate strings
  SBG-5  : java_version hardcoded to 25 in generateStructuredPom()
  SBG-6  : Test files never generated despite report claiming 18
  SBG-7  : \\b word-boundary broken inside f-strings
  SBG-8  : Literal '\\n' join in _normalize_controller_code()
  SBG-9  : Literal '\\n\\n' join in _generate_controller() CRUD branch
  SBG-10 : Entity check precedes repository check in _classify_java_file()
  SBG-11 : Service CRUD bodies never populated
  SBG-12 : Duplicate repository interfaces for same entity
  SBG-13 : build.gradle missing from summary for Gradle projects
  SBG-14 : GenerationType.IDENTITY incompatible with Oracle sequences
  SBG-15 : README.md written twice by two separate methods
  SBG-16 : Wrong entity import in services whose class names don't match table
             names (e.g. ManageCustomerService -> ManageCustomer,
             OrderProcessingService -> OrderProcessing). Root causes:
             (a) _derive_entity_name() stripped 'Service' and returned the raw
                 remainder without ever consulting _ddl_table_map, so procedure-
                 named services always got a non-existent entity class imported.
             (b) _ddl_table_map was never populated before service files were
                 processed in _generate_java_files() / generate_services(),
                 so even the DDL-aware resolution path was always skipped.
             Fix: _derive_entity_name() now always tries _resolve_entity_from_ddl
             first and only falls back to the raw base when no table matches.
             _generate_java_files() and generate_services() both pre-populate
             _ddl_table_map from entity class names before touching any service.
  SBG-17 : Controller files never generated — folder created but always empty.
             Root cause: generate_controllers() is a standalone public method
             that was never called from generate_project() / _generate_java_files().
             Fix: _generate_java_files() now calls _generate_controllers_from_services()
             after all service files are written. For standard CRUD services it
             delegates to the existing _generate_controller(). For procedure-style
             action-switch services (INSERT/UPDATE/DELETE/SELECT) that returned ""
             from _generate_controller(), a new _generate_action_dispatch_controller()
             generates a POST /action endpoint with an inner ActionRequest DTO.
  SBG-19 : bootJar task fails with 'getDirMode()' error on Gradle < 8.8.
             Root cause: io.spring.dependency-management 1.1.7 was hardcoded in
             generateGradleBuild(). Version 1.1.7 calls the getDirMode() API
             introduced in Gradle 8.8, so any earlier Gradle install throws
             'java.lang.Integer getDirMode()' at the bootJar task and aborts the
             build — even though compileJava and processResources succeed.
             Fix: downgraded to 1.1.4, the last version compatible with both
             Gradle 7.x and all 8.x releases. Also added _generate_gradle_wrapper()
             called from _generate_additional_configs() for Gradle projects, which
             writes gradle/wrapper/gradle-wrapper.properties pinned to Gradle 8.7
             so the build is self-contained and version-stable on any machine.
  SBG-23 : Repositories and services written in Stage 5 (generate_project) remain
             incomplete even after Stage 6 (generate_entities) populates _ddl_columns
             and _ddl_table_map, because Stages 7-8 skip files already on disk.
             Root cause: the pipeline writes repos/services in Stage 5 with empty
             state, then Stages 7-8 detect those files as "already existing" and
             skip them entirely — _audit_and_complete_repository and
             _inject_crud_repository_calls never get a second chance to run with
             the fully-populated DDL data.
             Fix (a): generate_repositories() now re-reads every .java file already
             on disk in the repository directory, runs _normalize_repository_code()
             (which includes the full audit) again with populated _ddl_columns, and
             overwrites the file if anything changed — adding missing INSERT/DELETE,
             fixing incomplete UPDATE SET clauses, and correcting missing @Param.
             Fix (b): generate_services() now re-reads every .java file already on
             disk in the service directory, runs _normalize_service_code() again with
             populated _ddl_table_map, and overwrites if changed — fixing wrong entity
             imports, injecting @Autowired repos, and replacing stub switch cases.
             Fix (c): added _ensure_repo_params() helper that adds @Param("name")
             to any @Query method parameter that is missing it.
             (a) _audit_and_complete_repository silently bailed when _ddl_columns
                 was empty. _ddl_columns is only set in generate_entities() (Stage 6)
                 but repository normalisation runs in Stage 5 generate_project().
                 Fix: _generate_java_files() and generate_repositories() now call
                 the new _extract_columns_from_entity_code() helper to populate
                 _ddl_columns from entity Java source before any repository runs.
             (b) _inject_crud_repository_calls missed the mixed stub pattern where
                 the LLM writes '// TODO: ...' comment followed by a throw on the
                 next line — Pattern A needs a break;, Pattern B needs no comment.
                 Fix: added Pattern C that matches // TODO + throw together.
             (c) UPDATE audit regex only matched native SQL table names (e.g.
                 'UPDATE customers SET') but LLM often generates JPQL (e.g.
                 'UPDATE CustomersEntity c SET'). Fix: update_match now tests
                 both the table_lower form and the EntityClass Pascal form, and
                 rebuilds the corrected query in the same style (JPQL vs native)
                 as the original.
             (a) FK entity field names generated as 'customersentity'/'ordersentity'
                 instead of 'customersEntity'/'ordersEntity'. Root cause:
                 _generate_entity_from_ddl() used _to_lower_camel_case(ref_entity)
                 which calls _to_camel_case() internally — this lowercases every
                 character except the first of each underscore-split token, so
                 'CustomersEntity' (no underscores) became 'customersentity'.
                 Fix: use _lower_first(ref_entity) which only lowercases the very
                 first character, preserving interior PascalCase.
             (b) LLM generates bare entity class names ('Customer', 'Order') that
                 don't exist instead of the correct DDL-derived names
                 ('CustomersEntity', 'OrdersEntity') in service bodies and
                 lowercase entity names ('paymentsEntity') in repository JPQL.
                 Fix: _normalize_service_code() now replaces every wrong raw name
                 with its DDL-resolved entity class after body extraction.
                 _normalize_repository_code() now corrects any lowercase entity
                 class name in JPQL queries and JpaRepository<> generics.
             (1-3) Services had no @Autowired repository and no real logic.
                   Root cause A: _inject_crud_repository_calls only triggered on
                   '// TODO' — when LLM threw BusinessException("not implemented")
                   instead of a TODO comment, the injector skipped the entire
                   method body. Root cause B: @Autowired repo field was never
                   injected into the class even when the injector did fire.
                   Fix: _inject_crud_repository_calls now detects both TODO stubs
                   and throw-not-implemented stubs, always injects the @Autowired
                   repo field, and replaces both stub patterns with real repo calls.
             (4)   OrdersRepository.updateOrderStatus() only set status, missing
                   the amount column that the SQL procedure also updates.
                   Root cause: LLM generated incomplete UPDATE and generator had
                   no validation. Fix: new _audit_and_complete_repository() method
                   called from _normalize_repository_code() rebuilds the UPDATE
                   SET clause to include every non-PK non-CREATED_AT column.
             (5)   PaymentsRepository had no insertPayment() or deletePayment().
                   Root cause: LLM omitted operations and generator had no safety
                   net. Fix: _audit_and_complete_repository() detects missing
                   INSERT/DELETE operations and generates them from DDL column data.
             (6)   Entities used plain Long for FK columns with no @ManyToOne/
                   @JoinColumn. Root cause: ALTER TABLE FK constraints were never
                   parsed — sql_table_discovery.py only reads CREATE TABLE bodies.
                   Fix: new parse_fk_constraints() static method parses ALTER TABLE
                   FOREIGN KEY statements; generate_entities() accepts an fk_map
                   parameter and passes per-table FK lists to _generate_entity_from_ddl()
                   which now emits @ManyToOne(fetch=LAZY) + @JoinColumn instead of
                   a plain Long field for every FK column.
             generate_controllers) produced 0 results when called standalone
             after generate_project() because shared state was never populated.
             Three root causes:
             (a) generate_repositories(): _latest_java_code was only set inside
                 generate_project(), so the referenced-repository scan always
                 returned an empty set, and _ddl_table_map was empty so entity
                 name resolution was skipped.
             (b) generate_controllers(): only called _generate_controller() which
                 returns "" for procedure-style action-switch services, so all
                 3 services were silently skipped every time.
             Fix (a): generate_repositories() now rebuilds _ddl_table_map from
             on-disk entity files AND the passed entities dict, and rebuilds
             _latest_java_code by reading already-written service/repository Java
             files from disk before the referenced-repository scan runs.
             Fix (b): generate_controllers() now mirrors the two-path logic of
             _generate_controllers_from_services(): standard CRUD first, then
             action-dispatch fallback for procedure-style services.
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
import logging

from ..utils.logger import get_logger
from ..utils.config import get_config_value

logger = get_logger(__name__)

# ── SBG-3: known stable Spring Boot versions ─────────────────────────────────
_KNOWN_STABLE_SPRING_BOOT = "3.2.5"
_MAX_SUPPORTED_SPRING_BOOT_MAJOR = 3


@dataclass
class ProjectStructure:
    project_name: str
    package_name: str
    java_version: str
    spring_boot_version: str
    base_path: Path
    modules: List[str]
    dependencies: List[str]


@dataclass
class BuildDependency:
    group: str
    artifact: str
    scope: Optional[str] = None
    version: Optional[str] = None
    optional: bool = False
    gradle_configuration: Optional[str] = None
    annotation_processor: bool = False

    def key(self) -> tuple:
        return (self.group, self.artifact)


def _dedupe_annotation_block(code: str) -> str:
    """
    SBG-26 FIX: Remove duplicate @Modifying / @Transactional annotations from a
    repository body. The LLM (and the re-audit pipeline) sometimes writes both
    annotations twice in a row before a single @Query:

        @Modifying
        @Transactional
            @Modifying       <- duplicate
        @Transactional       <- duplicate
        @Query(...)

    Strategy: scan lines sequentially; track which Spring-Data annotations have
    already appeared in the current consecutive annotation block (reset on any
    non-annotation, non-blank line). Skip a line if its annotation was already
    seen in this block.
    """
    REPO_ANNOTATIONS = {'@Modifying', '@Transactional', '@Query', '@Repository'}
    lines = code.splitlines(keepends=True)
    result = []
    # Set of bare annotation names (@Modifying etc.) seen in the current block
    block_seen: set = set()

    for line in lines:
        stripped = line.strip()
        bare = stripped.split('(')[0].strip()  # "@Modifying" from "@Modifying(clearAutomatically=true)"

        if bare in ('@Modifying', '@Transactional'):
            if bare in block_seen:
                continue  # drop duplicate within this consecutive annotation block
            block_seen.add(bare)
        else:
            # Any non-annotation or blank line ends the current block
            if stripped:
                block_seen = set()
        result.append(line)
    return ''.join(result)


def _collapse_repository_query_annotations(code: str) -> str:
    """
    Deterministically normalize any modifier/transaction annotation block that
    appears immediately before a repository @Query method.

    This is stricter than _dedupe_annotation_block(): for every consecutive
    annotation run that ends in @Query, force the prefix to contain at most one
    @Modifying and at most one @Transactional, in that order.
    """
    pattern = re.compile(
        r'(?P<prefix>(?:[ \t]*@(?:Modifying|Transactional)[^\n]*\n)+)(?P<query>[ \t]*@Query\s*\()',
        re.MULTILINE,
    )

    def repl(match: re.Match) -> str:
        prefix = match.group('prefix')
        query = match.group('query')
        indent_match = re.search(r'(^[ \t]*)@', prefix, re.MULTILINE)
        indent = indent_match.group(1) if indent_match else ''
        lines = []
        if re.search(r'^[ \t]*@Modifying\b', prefix, re.MULTILINE):
            lines.append(f'{indent}@Modifying\n')
        if re.search(r'^[ \t]*@Transactional\b', prefix, re.MULTILINE):
            lines.append(f'{indent}@Transactional\n')
        return ''.join(lines) + query

    return pattern.sub(repl, code)


def _strip_llm_trailing_garbage(code: str) -> str:
    """
    SBG-27 FIX: The LLM sometimes appends extra content after the closing brace
    of the class (e.g. placeholder imports, bare @Entity annotations, comments).
    This is illegal Java and causes compile errors.

    Strategy: find the last '}' that closes a top-level class/interface declaration
    by tracking brace depth from the first 'public class/interface' line.
    Everything after that closing brace is discarded.
    """
    lines = code.splitlines(keepends=True)
    depth = 0
    in_class = False
    last_close_line = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Detect start of top-level type declaration
        if not in_class:
            if re.search(r'\b(class|interface|enum|record)\b', stripped):
                in_class = True
        if in_class:
            depth += line.count('{') - line.count('}')
            if depth <= 0 and '{'  in code[:sum(len(l) for l in lines[:i+1])]:
                last_close_line = i
                break  # found the closing brace of the outermost type

    if last_close_line >= 0 and last_close_line < len(lines) - 1:
        return ''.join(lines[:last_close_line + 1])
    return code


class SpringBootGenerator:
    """Generates complete Spring Boot projects"""

    RESERVED_ENTITY_NAMES = {
        'Order', 'User', 'Group', 'Table', 'Column',
        'Index', 'Key', 'Value', 'Constraint',
    }

    EXTRA_DEPENDENCY_COORDINATES = {
        "spring-retry": {
            "group": "org.springframework.retry",
            "artifact": "spring-retry",
            "gradle": "implementation",
        },
        "mapstruct": {
            "group": "org.mapstruct",
            "artifact": "mapstruct",
            "gradle": "implementation",
        },
        "flyway-core": {
            "group": "org.flywaydb",
            "artifact": "flyway-core",
            "gradle": "implementation",
        },
        "micrometer-registry-prometheus": {
            "group": "io.micrometer",
            "artifact": "micrometer-registry-prometheus",
            "gradle": "runtimeOnly",
        },
        "spring-boot-starter-security": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-security",
            "gradle": "implementation",
        },
        "spring-boot-starter-cache": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-cache",
            "gradle": "implementation",
        },
        "spring-boot-starter-batch": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-batch",
            "gradle": "implementation",
        },
        "spring-boot-starter-mail": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-mail",
            "gradle": "implementation",
        },
        "spring-boot-starter-webflux": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-webflux",
            "gradle": "implementation",
        },
        "spring-boot-starter-data-redis": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-data-redis",
            "gradle": "implementation",
        },
        "spring-boot-starter-data-mongodb": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-data-mongodb",
            "gradle": "implementation",
        },
        "spring-boot-starter-amqp": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-amqp",
            "gradle": "implementation",
        },
        "spring-boot-starter-quartz": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-quartz",
            "gradle": "implementation",
        },
        "spring-boot-starter-actuator": {
            "group": "org.springframework.boot",
            "artifact": "spring-boot-starter-actuator",
            "gradle": "implementation",
        },
        "lombok": {
            "group": "org.projectlombok",
            "artifact": "lombok",
            "gradle": "compileOnly",
            "annotationProcessor": True,
            "scope": "provided",
            "optional": True,
        },
    }

    BASE_DEPENDENCY_IDS = {
        "spring-boot-starter-web",
        "spring-boot-starter-data-jpa",
        "spring-boot-starter-validation",
        "springdoc-openapi-starter-webmvc-ui",
        "ojdbc8",
        "mysql-connector-j",
        "postgresql",
        "spring-boot-starter-test",
        "testcontainers",
        "junit-jupiter",
        "spring-boot-devtools",
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_name = config.get('project_name', 'converted-app')
        self.group_id = config.get('group_id', 'com.company')
        self.artifact_id = config.get('artifact_id', self.project_name)
        self.package_name = config.get('package_name', 'com.company.project')
        self.description = config.get('description', 'PL/SQL to Java Modernization Project')
        self.java_version = config.get('java_version', '17')
        # SBG-3: validate and clamp spring_boot_version
        self.spring_boot_version = self._validate_spring_boot_version(
            config.get('spring_boot_version', _KNOWN_STABLE_SPRING_BOOT)
        )
        self.build_tool = self._normalize_build_tool(config.get('build_tool', 'maven'))
        self.packaging = self._normalize_packaging(config.get('packaging', 'jar'))
        self.config_format = self._normalize_config_format(config.get('config_format', 'properties'))
        self.target_directory = Path(config.get('target_directory', './output'))
        self.extra_dependencies = self._normalize_extra_dependencies(config.get('dependencies', []))
        self.dependency_versions = config.get('dependency_versions', {}) or {}
        self.llm_recommended_dependencies = (
            config.get('recommended_dependencies')
            or config.get('llm_recommended_dependencies')
            or []
        )
        self.enable_llm_recommended_dependencies = bool(
            config.get('enable_llm_recommended_dependencies', False)
            or config.get('llm_recommended_dependencies_enabled', False)
            or self.llm_recommended_dependencies
        )
        self._existing_repositories: Set[str] = set()
        self._ddl_table_map: Dict[str, str] = {}
        self._entity_name_index: Dict[str, str] = {}
        self._ddl_columns: Dict[str, List[Dict[str, str]]] = {}   # SBG-20: table -> columns
        self._fk_map: Dict[str, List[Dict[str, str]]] = {}        # SBG-20: table -> FK list

        self.base_path = self.target_directory / 'src' / 'main' / 'java'
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.resources_path = self.target_directory / 'src' / 'main' / 'resources'
        self.test_base_path = self.target_directory / 'src' / 'test' / 'java'

        self.package_path = self.base_path / self.package_name.replace('.', '/')

        logger.info(f"Spring Boot Generator initialized for project: {self.project_name}")

    # ── SBG-3: version guard ──────────────────────────────────────────────────
    def _validate_spring_boot_version(self, version: str) -> str:
        """Clamp spring_boot_version to a known-stable value if unsupported."""
        try:
            major = int(str(version).split(".")[0])
        except (ValueError, AttributeError):
            logger.warning("Invalid spring_boot_version '%s'; using %s", version, _KNOWN_STABLE_SPRING_BOOT)
            return _KNOWN_STABLE_SPRING_BOOT
        if major > _MAX_SUPPORTED_SPRING_BOOT_MAJOR:
            logger.warning(
                "spring_boot_version '%s' (major=%d) is unsupported; clamping to %s",
                version, major, _KNOWN_STABLE_SPRING_BOOT,
            )
            return _KNOWN_STABLE_SPRING_BOOT
        return str(version).strip()

    def _normalize_extra_dependencies(self, dependencies: List[str]) -> List[str]:
        normalized: List[str] = []
        for dep in dependencies or []:
            if not dep:
                continue
            dep_id = str(dep).strip()
            if not dep_id or dep_id in self.BASE_DEPENDENCY_IDS:
                continue
            if ":" in dep_id:
                # SBG-4: validate artifact part is non-trivial
                parts = dep_id.split(":")
                if len(parts) >= 2 and len(parts[1]) > 1 and dep_id not in normalized:
                    normalized.append(dep_id)
                elif len(parts) >= 2 and len(parts[1]) <= 1:
                    logger.warning("Ignoring suspiciously short artifact in coordinate '%s'", dep_id)
                continue
            if dep_id in self.EXTRA_DEPENDENCY_COORDINATES and dep_id not in normalized:
                normalized.append(dep_id)
        return normalized

    def _render_extra_maven_dependencies(self) -> str:
        if not self.extra_dependencies:
            return ""
        blocks: List[str] = []
        for dep_id in self.extra_dependencies:
            info = self.EXTRA_DEPENDENCY_COORDINATES.get(dep_id)
            if not info:
                coordinate_parts = dep_id.split(":")
                if len(coordinate_parts) >= 2:
                    group_id = coordinate_parts[0]
                    artifact_id = coordinate_parts[1]
                    lines = [
                        "<dependency>",
                        f"    <groupId>{group_id}</groupId>",
                        f"    <artifactId>{artifact_id}</artifactId>",
                        "</dependency>",
                    ]
                    blocks.append("\n        ".join(lines))
                continue
            scope = info.get("scope")
            optional = info.get("optional")
            lines = [
                "<dependency>",
                f"    <groupId>{info['group']}</groupId>",
                f"    <artifactId>{info['artifact']}</artifactId>",
            ]
            if scope:
                lines.append(f"    <scope>{scope}</scope>")
            if optional:
                lines.append("    <optional>true</optional>")
            lines.append("</dependency>")
            blocks.append("\n        ".join(lines))
        if not blocks:
            return ""
        return "\n        " + "\n        ".join(blocks)

    def _render_extra_gradle_dependencies(self) -> str:
        if not self.extra_dependencies:
            return ""
        lines: List[str] = []
        for dep_id in self.extra_dependencies:
            info = self.EXTRA_DEPENDENCY_COORDINATES.get(dep_id)
            if not info:
                coordinate_parts = dep_id.split(":")
                # SBG-4: guard against short/truncated artifact
                if len(coordinate_parts) >= 2 and len(coordinate_parts[1]) > 1:
                    coordinate = f"{coordinate_parts[0]}:{coordinate_parts[1]}"
                    lines.append(f"implementation '{coordinate}'")
                continue
            coordinate = f"{info['group']}:{info['artifact']}"
            if dep_id == "lombok":
                lines.append(f"compileOnly '{coordinate}'")
                if info.get("annotationProcessor"):
                    lines.append(f"annotationProcessor '{coordinate}'")
                continue
            config = info.get("gradle", "implementation")
            lines.append(f"{config} '{coordinate}'")
        if not lines:
            return ""
        return "\n    " + "\n    ".join(lines)

    def _parse_java_version(self, value: Any) -> int:
        if isinstance(value, int):
            return value
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return 0

    def _spring_boot_major(self, value: Any) -> int:
        try:
            return int(str(value).split(".")[0])
        except (TypeError, ValueError, IndexError):
            return 0

    def isJava25AndBoot4(self, config: Dict[str, Any]) -> bool:
        java_version = self._parse_java_version(config.get("java_version", self.java_version))
        spring_boot_version = str(config.get("spring_boot_version", self.spring_boot_version))
        return java_version >= 25 and spring_boot_version.startswith("4.")

    def generateProject(self, config: Dict[str, Any]) -> str:
        build_tool = self._normalize_build_tool(config.get("build_tool", self.build_tool))
        if build_tool == "maven":
            if self.isJava25AndBoot4(config):
                return self.generateStructuredPom(config)
            return self.generateMinimalPom(config)
        if build_tool == "gradle":
            return self.generateGradleBuild(config)
        return self.generateMinimalPom(config)

    def _get_database_type(self, config: Dict[str, Any]) -> str:
        if isinstance(config.get("database"), dict):
            db_type = config.get("database", {}).get("type")
            if db_type:
                return str(db_type).lower()
        for key in ("database_type", "db_type"):
            if config.get(key):
                return str(config.get(key)).lower()
        return "oracle"

    def _is_boot_managed_dependency(self, dep: BuildDependency) -> bool:
        if dep.group == "org.springframework.boot":
            return True
        if dep.artifact.startswith("spring-boot-starter"):
            return True
        if dep.group == "org.springframework" and dep.artifact.startswith("spring-"):
            return True
        return False

    def _normalize_dependency_input(self, dep: Any) -> Optional[BuildDependency]:
        if not dep:
            return None
        if isinstance(dep, dict):
            group = dep.get("group") or dep.get("groupId")
            artifact = dep.get("artifact") or dep.get("artifactId")
            if not group or not artifact:
                return None
            return BuildDependency(
                group=str(group).strip(),
                artifact=str(artifact).strip(),
                scope=dep.get("scope"),
                version=dep.get("version"),
                optional=bool(dep.get("optional", False)),
                gradle_configuration=dep.get("gradle") or dep.get("gradle_configuration"),
                annotation_processor=bool(dep.get("annotationProcessor", False)),
            )

        dep_id = str(dep).strip()
        if not dep_id:
            return None

        alias_map = {
            "web": "spring-boot-starter-web",
            "webmvc": "spring-boot-starter-web",
            "webflux": "spring-boot-starter-webflux",
            "data-jpa": "spring-boot-starter-data-jpa",
            "mysql": "mysql-connector-j",
            "postgres": "postgresql",
            "postgresql": "postgresql",
            "oracle": "ojdbc8",
        }
        dep_id = alias_map.get(dep_id, dep_id)

        info = self.EXTRA_DEPENDENCY_COORDINATES.get(dep_id)
        if info:
            return BuildDependency(
                group=info["group"],
                artifact=info["artifact"],
                scope=info.get("scope"),
                optional=bool(info.get("optional", False)),
                gradle_configuration=info.get("gradle"),
                annotation_processor=bool(info.get("annotationProcessor", False)),
            )

        driver_map = {
            "ojdbc8": BuildDependency(
                group="com.oracle.database.jdbc", artifact="ojdbc8",
                scope="runtime", gradle_configuration="runtimeOnly",
            ),
            "ojdbc11": BuildDependency(
                group="com.oracle.database.jdbc", artifact="ojdbc11",
                scope="runtime", gradle_configuration="runtimeOnly",
            ),
            "mysql-connector-j": BuildDependency(
                group="com.mysql", artifact="mysql-connector-j",
                scope="runtime", gradle_configuration="runtimeOnly",
            ),
            "postgresql": BuildDependency(
                group="org.postgresql", artifact="postgresql",
                scope="runtime", gradle_configuration="runtimeOnly",
            ),
        }
        if dep_id in driver_map:
            return driver_map[dep_id]

        parts = dep_id.split(":")
        if len(parts) >= 2:
            group = parts[0]
            artifact = parts[1]
            version = parts[2] if len(parts) >= 3 else None
            return BuildDependency(group=group, artifact=artifact, version=version)

        return None

    def _resolve_dependency_version(self, dep: BuildDependency, config: Dict[str, Any]) -> Optional[str]:
        if dep.version:
            return dep.version
        if self._is_boot_managed_dependency(dep):
            return None
        key = f"{dep.group}:{dep.artifact}"
        if key in self.dependency_versions:
            return str(self.dependency_versions[key]).strip()
        compatibility_versions = {
            "org.springdoc:springdoc-openapi-starter-webmvc-ui": "2.5.0",
            "org.mapstruct:mapstruct": "1.5.5.Final",
            "org.springframework.retry:spring-retry": "2.0.5",
            "org.flywaydb:flyway-core": "10.10.0",
            "io.micrometer:micrometer-registry-prometheus": "1.13.6",
        }
        return compatibility_versions.get(key)

    def _is_dependency_compatible(self, dep: BuildDependency, config: Dict[str, Any]) -> bool:
        java_version = self._parse_java_version(config.get("java_version", self.java_version))
        boot_major = self._spring_boot_major(config.get("spring_boot_version", self.spring_boot_version))
        compat = {
            ("org.springframework.retry", "spring-retry"): {"min_java": 8, "min_boot_major": 2},
            ("org.mapstruct", "mapstruct"): {"min_java": 8, "min_boot_major": 2},
            ("org.flywaydb", "flyway-core"): {"min_java": 8, "min_boot_major": 2},
            ("io.micrometer", "micrometer-registry-prometheus"): {"min_java": 8, "min_boot_major": 2},
            ("org.springdoc", "springdoc-openapi-starter-webmvc-ui"): {"min_java": 17, "min_boot_major": 3},
        }
        rule = compat.get(dep.key())
        if not rule:
            return True
        min_java = rule.get("min_java")
        if min_java and java_version < min_java:
            return False
        min_boot_major = rule.get("min_boot_major")
        if min_boot_major and boot_major < min_boot_major:
            return False
        max_boot_major = rule.get("max_boot_major")
        if max_boot_major and boot_major > max_boot_major:
            return False
        return True

    def _select_database_dependency(self, config: Dict[str, Any]) -> Optional[BuildDependency]:
        db_type = self._get_database_type(config)
        java_version = self._parse_java_version(config.get("java_version", self.java_version))
        if db_type == "oracle":
            artifact = "ojdbc11" if java_version >= 25 else "ojdbc8"
            return BuildDependency(
                group="com.oracle.database.jdbc", artifact=artifact,
                scope="runtime", gradle_configuration="runtimeOnly",
            )
        if db_type == "mysql":
            return BuildDependency(
                group="com.mysql", artifact="mysql-connector-j",
                scope="runtime", gradle_configuration="runtimeOnly",
            )
        if db_type in ("postgresql", "postgres"):
            return BuildDependency(
                group="org.postgresql", artifact="postgresql",
                scope="runtime", gradle_configuration="runtimeOnly",
            )
        return None

    def _dedupe_dependencies(self, deps: List[BuildDependency]) -> List[BuildDependency]:
        scope_priority = {"compile": 3, None: 3, "runtime": 2, "provided": 1, "test": 0}
        gradle_priority = {
            "implementation": 3, "api": 3, None: 3,
            "runtimeOnly": 2, "developmentOnly": 2,
            "compileOnly": 1, "testImplementation": 0,
        }
        ordered: List[BuildDependency] = []
        seen: Dict[tuple, BuildDependency] = {}
        for dep in deps:
            key = dep.key()
            existing = seen.get(key)
            if not existing:
                seen[key] = dep
                ordered.append(dep)
                continue
            if dep.version and not existing.version:
                existing.version = dep.version
            if dep.optional:
                existing.optional = True
            if dep.annotation_processor:
                existing.annotation_processor = True
            if scope_priority.get(dep.scope, 0) > scope_priority.get(existing.scope, 0):
                existing.scope = dep.scope
            if gradle_priority.get(dep.gradle_configuration, 0) > gradle_priority.get(existing.gradle_configuration, 0):
                existing.gradle_configuration = dep.gradle_configuration
        return ordered

    def _resolve_conflicts(self, deps: List[BuildDependency]) -> List[BuildDependency]:
        keys = {dep.key(): dep for dep in deps}
        web_key = ("org.springframework.boot", "spring-boot-starter-web")
        webflux_key = ("org.springframework.boot", "spring-boot-starter-webflux")
        if web_key in keys and webflux_key in keys:
            deps = [dep for dep in deps if dep.key() != web_key]
        return deps

    def _build_dependency_list(self, config: Dict[str, Any]) -> List[BuildDependency]:
        deps: List[BuildDependency] = []
        deps.extend([
            BuildDependency("org.springframework.boot", "spring-boot-starter-web", gradle_configuration="implementation"),
            BuildDependency("org.springframework.boot", "spring-boot-starter-data-jpa", gradle_configuration="implementation"),
            BuildDependency("org.springframework.boot", "spring-boot-starter-validation", gradle_configuration="implementation"),
            BuildDependency("org.springdoc", "springdoc-openapi-starter-webmvc-ui", version="2.5.0", gradle_configuration="implementation"),
            BuildDependency("org.springframework.boot", "spring-boot-starter-test", scope="test", gradle_configuration="testImplementation"),
            BuildDependency("org.testcontainers", "testcontainers", scope="test", gradle_configuration="testImplementation"),
            BuildDependency("org.testcontainers", "junit-jupiter", scope="test", gradle_configuration="testImplementation"),
            # SBG-24: H2 in-memory DB for context-load tests (avoids Oracle DDL during test)
            BuildDependency("com.h2database", "h2", scope="test", gradle_configuration="testRuntimeOnly"),
            BuildDependency("org.springframework.boot", "spring-boot-devtools", scope="runtime", optional=True, gradle_configuration="developmentOnly"),
        ])

        db_dep = self._select_database_dependency(config)
        if db_dep:
            deps.append(db_dep)
        selected_driver_key = db_dep.key() if db_dep else None

        for dep_id in self.extra_dependencies:
            dep = self._normalize_dependency_input(dep_id)
            if dep:
                deps.append(dep)

        if self.enable_llm_recommended_dependencies:
            for rec in self.llm_recommended_dependencies or []:
                dep = self._normalize_dependency_input(rec)
                if not dep:
                    continue
                if not self._is_dependency_compatible(dep, config):
                    logger.warning("Skipping incompatible LLM dependency: %s:%s", dep.group, dep.artifact)
                    continue
                dep.version = self._resolve_dependency_version(dep, config)
                if not dep.version and not self._is_boot_managed_dependency(dep):
                    logger.warning("Skipping LLM dependency without managed version: %s:%s", dep.group, dep.artifact)
                    continue
                deps.append(dep)

        if selected_driver_key:
            driver_keys = {
                ("com.oracle.database.jdbc", "ojdbc8"),
                ("com.oracle.database.jdbc", "ojdbc11"),
                ("com.mysql", "mysql-connector-j"),
                ("org.postgresql", "postgresql"),
            }
            deps = [
                dep for dep in deps
                if dep.key() not in driver_keys or dep.key() == selected_driver_key
            ]
        deps = self._resolve_conflicts(self._dedupe_dependencies(deps))
        return deps

    def _categorize_dependency(self, dep: BuildDependency) -> str:
        if dep.scope == "test" or (dep.gradle_configuration or "").startswith("test"):
            return "testing"
        if dep.artifact in ("spring-boot-devtools",):
            return "devtools"
        if dep.group in ("com.oracle.database.jdbc", "com.mysql", "org.postgresql"):
            return "database"
        return "core"

    def _render_maven_dependency_block(self, dep: BuildDependency, indent: str = "        ") -> str:
        lines = [
            f"{indent}<dependency>",
            f"{indent}    <groupId>{dep.group}</groupId>",
            f"{indent}    <artifactId>{dep.artifact}</artifactId>",
        ]
        if dep.version:
            lines.append(f"{indent}    <version>{dep.version}</version>")
        if dep.scope:
            lines.append(f"{indent}    <scope>{dep.scope}</scope>")
        if dep.optional:
            lines.append(f"{indent}    <optional>true</optional>")
        lines.append(f"{indent}</dependency>")
        return "\n".join(lines)

    def _render_maven_dependencies(self, deps: List[BuildDependency], grouped: bool = False) -> str:
        if not deps:
            return ""
        if not grouped:
            return "\n".join(self._render_maven_dependency_block(dep) for dep in deps)

        sections = {"core": [], "database": [], "testing": [], "devtools": []}
        for dep in deps:
            sections[self._categorize_dependency(dep)].append(dep)

        parts: List[str] = []
        if sections["core"]:
            parts.append("        <!-- Core -->")
            parts.extend(self._render_maven_dependency_block(dep) for dep in sections["core"])
        if sections["database"]:
            parts.append("        <!-- Database -->")
            parts.extend(self._render_maven_dependency_block(dep) for dep in sections["database"])
        if sections["testing"]:
            parts.append("        <!-- Testing -->")
            parts.extend(self._render_maven_dependency_block(dep) for dep in sections["testing"])
        if sections["devtools"]:
            parts.append("        <!-- DevTools -->")
            parts.extend(self._render_maven_dependency_block(dep) for dep in sections["devtools"])
        return "\n".join(parts)

    def _render_gradle_dependencies(self, deps: List[BuildDependency], grouped: bool = False) -> str:
        if not deps:
            return ""
        sections = {"core": [], "database": [], "testing": [], "devtools": []}
        for dep in deps:
            sections[self._categorize_dependency(dep)].append(dep)

        def gradle_line(dep: BuildDependency) -> List[str]:
            conf = dep.gradle_configuration or "implementation"
            coordinate = f"{dep.group}:{dep.artifact}"
            if dep.version:
                coordinate = f"{coordinate}:{dep.version}"
            lines = [f"    {conf} '{coordinate}'"]
            if dep.annotation_processor:
                lines.append(f"    annotationProcessor '{coordinate}'")
            return lines

        if not grouped:
            lines: List[str] = []
            for dep in deps:
                lines.extend(gradle_line(dep))
            return "\n".join(lines)

        parts: List[str] = []
        if sections["core"]:
            parts.append("    // Core")
            for dep in sections["core"]:
                parts.extend(gradle_line(dep))
        if sections["database"]:
            parts.append("    // Database")
            for dep in sections["database"]:
                parts.extend(gradle_line(dep))
        if sections["testing"]:
            parts.append("    // Testing")
            for dep in sections["testing"]:
                parts.extend(gradle_line(dep))
        if sections["devtools"]:
            parts.append("    // DevTools")
            for dep in sections["devtools"]:
                parts.extend(gradle_line(dep))
        return "\n".join(parts)

    async def generate_project(self, java_code: Dict[str, str]) -> Dict[str, Any]:
        logger.info("Starting Spring Boot project generation...")
        self._latest_java_code = dict(java_code or {})

        self._create_project_structure()
        self._generate_build_config()
        self._generate_application_config()

        java_files = self._generate_java_files(java_code)

        repo_dir = self.package_path / 'repository'
        for reserved in ('JpaRepository.java', 'CrudRepository.java'):
            reserved_path = repo_dir / reserved
            if reserved_path.exists():
                reserved_path.unlink()

        self._generate_additional_configs()
        # SBG-15: only generate README once, here
        self._generate_readme()

        project_summary = self._generate_project_summary(java_files)

        logger.info(f"Spring Boot project generation completed. Generated {len(java_files)} files.")
        return {
            'project_name': self.project_name,
            'package_name': self.package_name,
            'base_path': str(self.base_path),
            'java_files': java_files,
            'project_structure': project_summary
        }

    def _create_project_structure(self):
        for sub in ('controller', 'service', 'repository', 'entity', 'dto', 'exception', 'config'):
            (self.package_path / sub).mkdir(parents=True, exist_ok=True)

        test_path = self.test_base_path / self.package_name.replace('.', '/')
        for sub in ('service', 'repository', 'controller', 'entity', 'integration'):
            (test_path / sub).mkdir(parents=True, exist_ok=True)

        self.resources_path.mkdir(parents=True, exist_ok=True)
        logger.info("Project structure created successfully")

    def _generate_build_config(self):
        build_content = self.generateProject(self.config)
        if self.build_tool == "gradle":
            gradle_path = self.target_directory / 'build.gradle'
            with open(gradle_path, 'w', encoding='utf-8') as f:
                f.write(build_content)
        else:
            pom_path = self.target_directory / 'pom.xml'
            with open(pom_path, 'w', encoding='utf-8') as f:
                f.write(build_content)
        logger.info("Build configuration files generated")

    def _generate_pom_content(self) -> str:
        return self.generateMinimalPom(self.config)

    def generateMinimalPom(self, config: Dict[str, Any]) -> str:
        deps = self._build_dependency_list(config)
        dependency_block = self._render_maven_dependencies(deps, grouped=False)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>{self.spring_boot_version}</version>
        <relativePath/>
    </parent>

    <groupId>{self.group_id}</groupId>
    <artifactId>{self.artifact_id}</artifactId>
    <version>1.0.0</version>
    <name>{self.project_name}</name>
    <description>{self.description}</description>
    <packaging>{self.packaging}</packaging>

    <properties>
        <java.version>{self.java_version}</java.version>
        <maven.compiler.source>{self.java_version}</maven.compiler.source>
        <maven.compiler.target>{self.java_version}</maven.compiler.target>
    </properties>

    <dependencies>
{dependency_block}
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.11.0</version>
                <configuration>
                    <source>{self.java_version}</source>
                    <target>{self.java_version}</target>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
"""

    def generateStructuredPom(self, config: Dict[str, Any]) -> str:
        deps = self._build_dependency_list(config)
        dependency_block = self._render_maven_dependencies(deps, grouped=True)
        license_name = config.get("license_name", "UNLICENSED")
        license_url = config.get("license_url", "https://example.com/license")
        developer_name = config.get("developer_name", "PL/SQL Modernization Team")
        developer_email = config.get("developer_email", "dev-team@example.com")
        scm_url = config.get("scm_url", "https://example.com/repo")
        # SBG-5: use self.java_version, never hardcode 25
        java_version = self.java_version
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>{self.spring_boot_version}</version>
        <relativePath/>
    </parent>

    <groupId>{self.group_id}</groupId>
    <artifactId>{self.artifact_id}</artifactId>
    <version>1.0.0</version>
    <packaging>{self.packaging}</packaging>

    <name>{self.project_name}</name>
    <description>{self.description}</description>
    <licenses>
        <license>
            <name>{license_name}</name>
            <url>{license_url}</url>
        </license>
    </licenses>
    <developers>
        <developer>
            <name>{developer_name}</name>
            <email>{developer_email}</email>
        </developer>
    </developers>
    <scm>
        <url>{scm_url}</url>
    </scm>

    <properties>
        <java.version>{java_version}</java.version>
    </properties>

    <dependencies>
{dependency_block}
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.11.0</version>
                <configuration>
                    <release>{java_version}</release>
                    <annotationProcessorPaths>
                        <path>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </path>
                        <path>
                            <groupId>org.springframework.boot</groupId>
                            <artifactId>spring-boot-configuration-processor</artifactId>
                        </path>
                    </annotationProcessorPaths>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
"""

    def _generate_gradle_content(self) -> str:
        return self.generateGradleBuild(self.config)

    def generateGradleBuild(self, config: Dict[str, Any]) -> str:
        deps = self._build_dependency_list(config)
        dependency_block = self._render_gradle_dependencies(deps, grouped=True)
        war_plugin = "    id 'war'\n" if self.packaging == "war" else ""
        war_tasks = ""
        if self.packaging == "war":
            war_tasks = """
bootJar {
    enabled = false
}

bootWar {
    enabled = true
}
"""
        # SBG-19 FIX: io.spring.dependency-management 1.1.7 requires Gradle 8.8+
        # and its getDirMode() API change breaks bootJar on older Gradle installs.
        # 1.1.4 is the last version compatible with Gradle 7.x and all 8.x releases.
        return f"""plugins {{
    id 'org.springframework.boot' version '{self.spring_boot_version}'
    id 'io.spring.dependency-management' version '1.1.4'
    id 'java'
{war_plugin}}}

group = '{self.group_id}'
version = '1.0.0'
description = '{self.description}'

java {{
    sourceCompatibility = JavaVersion.VERSION_{self.java_version}
    targetCompatibility = JavaVersion.VERSION_{self.java_version}
}}

repositories {{
    mavenCentral()
}}

configurations {{
    compileOnly {{
        extendsFrom annotationProcessor
    }}
}}

dependencies {{
{dependency_block}
}}

tasks.named('test') {{
    useJUnitPlatform()
}}
{war_tasks}
"""

    def _generate_application_config(self):
        if self.config_format == "yaml":
            app_config = self._generate_application_yml()
            config_path = self.resources_path / 'application.yml'
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(app_config)
        else:
            app_props = self._generate_application_properties()
            props_path = self.resources_path / 'application.properties'
            with open(props_path, 'w', encoding='utf-8') as f:
                f.write(app_props)
        logger.info("Application configuration files generated")

    def _generate_application_yml(self) -> str:
        # SBG-2: server: is a top-level key, NOT nested under spring:
        return f"""# Spring Boot Application Configuration
spring:
  application:
    name: {self.project_name}

  # Database Configuration
  datasource:
    url: jdbc:oracle:thin:@localhost:1521:xe
    username: your_username
    password: your_password
    driver-class-name: oracle.jdbc.OracleDriver

  # JPA Configuration
  jpa:
    hibernate:
      ddl-auto: update
    show-sql: true
    properties:
      hibernate:
        dialect: org.hibernate.dialect.OracleDialect
        format_sql: true

# SBG-2 FIX: server is top-level, not under spring:
server:
  port: 8080

# Logging Configuration
logging:
  level:
    {self.package_name}: DEBUG
    org.hibernate.SQL: DEBUG
    org.springframework.data.jpa.repository: DEBUG

# Custom Application Properties
app:
  version: 1.0.0
  description: {self.description}
  build-time: {self._get_current_time()}
"""

    def _generate_application_properties(self) -> str:
        # SBG-1: correct key is server.port, not spring.server.port
        return f"""# Spring Boot Application Configuration
spring.application.name={self.project_name}

# Database Configuration
spring.datasource.url=jdbc:oracle:thin:@localhost:1521:xe
spring.datasource.username=your_username
spring.datasource.password=your_password
spring.datasource.driver-class-name=oracle.jdbc.OracleDriver

# JPA Configuration
spring.jpa.hibernate.ddl-auto=update
spring.jpa.show-sql=true
spring.jpa.properties.hibernate.dialect=org.hibernate.dialect.OracleDialect
spring.jpa.properties.hibernate.format_sql=true

# SBG-1 FIX: correct key (was spring.server.port)
server.port=8080

# Logging Configuration
logging.level.{self.package_name}=DEBUG
logging.level.org.hibernate.SQL=DEBUG
logging.level.org.springframework.data.jpa.repository=DEBUG

# Custom Application Properties
app.version=1.0.0
app.description={self.description}
app.build-time={self._get_current_time()}
"""

    def _normalize_build_tool(self, value: str) -> str:
        if not value:
            return "maven"
        lowered = str(value).strip().lower()
        if lowered in {"mvn", "maven"}:
            return "maven"
        if lowered in {"gradle", "gradle-groovy", "gradle-kotlin"}:
            return "gradle"
        return "maven"

    def _normalize_packaging(self, value: str) -> str:
        lowered = str(value or "").strip().lower()
        return "war" if lowered == "war" else "jar"

    def _normalize_config_format(self, value: str) -> str:
        lowered = str(value or "").strip().lower()
        return "yaml" if lowered in {"yaml", "yml"} else "properties"

    def _generate_java_files(self, java_code: Dict[str, str]) -> Dict[str, str]:
        java_files = {}

        # SBG-16 FIX: Build _ddl_table_map from entity class names BEFORE
        # processing service files so that _derive_entity_name can resolve
        # procedure-named services (e.g. ManageCustomerService -> CustomersEntity)
        # against the real entity set rather than guessing from the class name.
        # SBG-22 FIX: Also populate _ddl_columns from entity source code so that
        # _audit_and_complete_repository has column data when it runs during this
        # same stage — it previously bailed silently because _ddl_columns was only
        # set inside generate_entities() which runs after generate_project().
        if not self._ddl_table_map:
            for filename, code in java_code.items():
                file_type = self._classify_java_file(filename, code)
                if file_type != 'entity':
                    continue
                type_name = self._extract_type_name(code)
                if not type_name:
                    continue
                base = type_name[:-6] if type_name.lower().endswith('entity') else type_name
                key = base.lower()
                self._ddl_table_map[key] = base.upper()
                if key.endswith('s'):
                    self._ddl_table_map[key[:-1]] = base.upper()
                # SBG-22: extract column info from the entity source so
                # _audit_and_complete_repository can rebuild missing operations
                if not self._ddl_columns.get(base.upper()):
                    self._ddl_columns[base.upper()] = \
                        self._extract_columns_from_entity_code(code)

        for filename, code in java_code.items():
            type_name = self._extract_type_name(code)
            if (type_name in {'JpaRepository', 'CrudRepository'}
                    or filename.lower() in {'jparepository.java', 'crudrepository.java'}):
                continue
            target_filename = f"{type_name}.java" if type_name else filename
            file_type = self._classify_java_file(target_filename, code)
            if file_type == 'repository' and type_name in {'JpaRepository', 'CrudRepository'}:
                continue
            target_dir = self._get_target_directory(file_type)
            target_dir.mkdir(parents=True, exist_ok=True)

            file_path = target_dir / target_filename
            payload = code
            if file_type == 'repository':
                payload = self._normalize_repository_code(target_filename, code, self._ddl_table_map)
                repo_interface = self._extract_type_name(payload)
                if repo_interface:
                    self._existing_repositories.add(repo_interface)
            elif file_type == 'entity':
                payload = self._normalize_entity_code(target_filename, code)
            elif file_type == 'controller':
                payload = self._normalize_controller_code(target_filename, code)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(payload)

            java_files[target_filename] = str(file_path)

        self._generate_additional_java_files()

        # SBG-17 FIX: controllers were never generated from generate_project()
        # because generate_controllers() is a separate public method that was
        # never called from within the main pipeline. Fix: after all service
        # files are written, derive and write a controller for each service.
        self._generate_controllers_from_services(java_files)

        logger.info(f"Generated {len(java_files)} Java source files")
        return java_files

    def _generate_controllers_from_services(self, java_files: Dict[str, str]) -> None:
        """
        SBG-17 FIX: Generate one controller per service and write it to the
        controller package directory.  This is called at the end of
        _generate_java_files() so that controllers are always produced as part
        of the main generate_project() pipeline without requiring a separate
        generate_controllers() call.

        For procedure-style services (manageCustomer / processOrder / handlePayment)
        the service methods are action-switch based and don't expose getAll/create
        etc., so the guard in _generate_controller() would return "" and skip them.
        For those we generate a thin action-dispatch controller instead.
        """
        controller_dir = self.package_path / 'controller'
        controller_dir.mkdir(parents=True, exist_ok=True)

        for filename, filepath in list(java_files.items()):
            if not filename.lower().endswith('service.java'):
                continue

            service_name = filename.replace('.java', '')

            # Read back the already-written service code so we can inspect it
            try:
                with open(filepath, encoding='utf-8') as fh:
                    service_code = fh.read()
            except OSError:
                continue

            # Try the standard CRUD-method based controller first
            controller_code = self._generate_controller(service_name, service_code)

            # SBG-17: if the service uses an action-switch pattern (INSERT/UPDATE/
            # DELETE/SELECT) rather than getAll/create/etc., _generate_controller
            # returns "" because none of its regexes match.  Generate a proper
            # action-dispatch REST controller for those services instead.
            if not controller_code:
                controller_code = self._generate_action_dispatch_controller(
                    service_name, service_code
                )

            if not controller_code:
                continue

            controller_name = service_name.replace('Service', '') + 'Controller'
            controller_filename = f"{controller_name}.java"
            controller_path = controller_dir / controller_filename

            normalized = self._normalize_controller_code(controller_filename, controller_code)
            with open(controller_path, 'w', encoding='utf-8') as fh:
                fh.write(normalized)

            java_files[controller_filename] = str(controller_path)
            logger.info(f"Generated controller: {controller_filename}")

    def _generate_action_dispatch_controller(self, service_name: str, service_code: str) -> str:
        """
        SBG-17 FIX: Generate a REST controller for procedure-style services that
        use an action-switch (INSERT/UPDATE/DELETE/SELECT) instead of named CRUD
        methods.  Each action is exposed as a POST endpoint so the caller can
        pass the action and parameters as a JSON body.

        Introspects the service method signature to forward the right parameters.
        """
        # Find the primary public method in the service
        method_match = re.search(
            r'public\s+\w+\s+(\w+)\s*\(([^)]*)\)', service_code
        )
        if not method_match:
            return ""

        method_name = method_match.group(1)
        # Skip constructor-like or lifecycle names
        if method_name in ('class', 'interface', 'void'):
            return ""

        entity_base = service_name.replace('Service', '')
        service_var = service_name[0].lower() + service_name[1:]

        # Parse parameter list to build the forwarding call
        raw_params = method_match.group(2).strip()
        param_pairs = [p.strip() for p in raw_params.split(',') if p.strip()]
        # Each pair is "Type name"; collect names for the forwarding call
        param_names = []
        field_declarations = []
        for pair in param_pairs:
            parts = pair.split()
            if len(parts) >= 2:
                ptype, pname = parts[0], parts[-1]
                param_names.append(pname)
                field_declarations.append(f"        private {ptype} {pname};")

        fields_block = '\n'.join(field_declarations)
        call_args = ', '.join(f"request.get{p[0].upper()+p[1:]}()" for p in param_names)

        needs_big_decimal = 'BigDecimal' in raw_params
        needs_list = 'List<' in raw_params

        import_extras = ''
        if needs_big_decimal:
            import_extras += '\nimport java.math.BigDecimal;'
        if needs_list:
            import_extras += '\nimport java.util.List;'

        return f"""package {self.package_name}.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import {self.package_name}.service.{service_name};{import_extras}

@RestController
@RequestMapping("/api/{entity_base.lower()}")
public class {entity_base}Controller {{

    @Autowired
    private {service_name} {service_var};

    /**
     * Action-dispatch endpoint.
     * Pass a JSON body with an "action" field (INSERT / UPDATE / DELETE / SELECT)
     * plus the procedure parameters.
     */
    @PostMapping("/action")
    public ResponseEntity<?> executeAction(@RequestBody {entity_base}ActionRequest request) {{
        {service_var}.{method_name}({call_args});
        return ResponseEntity.ok().build();
    }}

    /**
     * Request DTO for action-dispatch.
     */
    public static class {entity_base}ActionRequest {{
{fields_block}

{self._generate_request_accessors(param_pairs)}    }}
}}
"""

    def _generate_request_accessors(self, param_pairs: list) -> str:
        """Generate getters and setters for the inner ActionRequest DTO."""
        lines = []
        for pair in param_pairs:
            parts = pair.split()
            if len(parts) < 2:
                continue
            ptype, pname = parts[0], parts[-1]
            cap = pname[0].upper() + pname[1:]
            lines.append(f"        public {ptype} get{cap}() {{ return {pname}; }}")
            lines.append(f"        public void set{cap}({ptype} {pname}) {{ this.{pname} = {pname}; }}")
        return '\n'.join(lines) + '\n' if lines else ''

    def _classify_java_file(self, filename: str, code: str) -> str:
        """
        SBG-10 FIX: repository/JPA check runs BEFORE entity annotation check.
        SBG-27 FIX: Strip LLM trailing garbage before classification so that
        @Entity / JpaRepository appearing AFTER the class closing brace (LLM
        placeholder comments) don't misclassify service files as entity/repo.
        Priority order: @Service/@Controller structural annotations first.
        """
        # Strip garbage appended after the class closing brace
        clean = _strip_llm_trailing_garbage(code)
        filename_lower = filename.lower()

        # PRIORITY 1: Structural annotations in clean code take precedence over everything
        if '@Service' in clean:
            return 'service'
        if '@RestController' in clean or '@Controller' in clean:
            return 'controller'

        # PRIORITY 2: Repository (SBG-10: check before @Entity/@Id)
        if ('extends JpaRepository' in clean or 'extends CrudRepository' in clean
                or '@Repository' in clean):
            return 'repository'
        if 'JpaRepository' in clean or 'CrudRepository' in clean:
            return 'repository'
        if 'repository' in filename_lower or 'dao' in filename_lower:
            return 'repository'

        # PRIORITY 3: Entity — only from clean code (ignores stray @Entity in garbage)
        if any(token in clean for token in ('@Entity', '@Table')):
            return 'entity'
        if '@Id' in clean and '@Column' in clean:
            return 'entity'
        if 'entity' in filename_lower or 'model' in filename_lower:
            return 'entity'

        # PRIORITY 4: Filename heuristics
        if 'controller' in filename_lower or 'rest' in filename_lower:
            return 'controller'
        if 'service' in filename_lower:
            return 'service'
        if 'dto' in filename_lower or 'request' in filename_lower or 'response' in filename_lower:
            return 'dto'
        if 'exception' in filename_lower:
            return 'exception'
        if 'config' in filename_lower:
            return 'config'

        if '@Configuration' in clean:
            return 'config'

        return 'service'

    def _get_target_directory(self, file_type: str) -> Path:
        mapping = {
            'controller': 'controller',
            'service': 'service',
            'repository': 'repository',
            'entity': 'entity',
            'dto': 'dto',
            'exception': 'exception',
            'config': 'config',
        }
        return self.package_path / mapping.get(file_type, 'service')

    def _generate_additional_java_files(self):
        main_class = self._generate_main_application_class()
        main_path = self.package_path / f"{self._to_camel_case(self.project_name)}Application.java"
        with open(main_path, 'w', encoding='utf-8') as f:
            f.write(main_class)

        for class_name, content in self._generate_base_exceptions().items():
            exception_path = self.package_path / 'exception' / f"{class_name}.java"
            with open(exception_path, 'w', encoding='utf-8') as f:
                f.write(content)

        dto_path = self.package_path / 'dto' / 'BaseDTO.java'
        with open(dto_path, 'w', encoding='utf-8') as f:
            f.write(self._generate_base_dto())

        for class_name, content in self._generate_config_classes().items():
            config_path = self.package_path / 'config' / f"{class_name}.java"
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(content)

        # SBG-6: generate at least a context-load test per service
        self._generate_test_files()

    # ── SBG-6: test file generation ──────────────────────────────────────────
    def _generate_test_files(self):
        """Generate a Spring Boot context load test for each generated service."""
        service_dir = self.package_path / 'service'
        test_service_dir = self.test_base_path / self.package_name.replace('.', '/') / 'service'
        test_service_dir.mkdir(parents=True, exist_ok=True)

        generated = 0
        if service_dir.exists():
            for service_file in service_dir.glob('*.java'):
                service_class = service_file.stem
                test_path = test_service_dir / f"{service_class}Test.java"
                if test_path.exists():
                    continue
                content = self._generate_service_test(service_class)
                with open(test_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                generated += 1

        # Always write at least one context load test
        if generated == 0:
            app_test_dir = self.test_base_path / self.package_name.replace('.', '/')
            app_test_dir.mkdir(parents=True, exist_ok=True)
            app_class = self._to_camel_case(self.project_name)
            test_path = app_test_dir / f"{app_class}ApplicationTests.java"
            with open(test_path, 'w', encoding='utf-8') as f:
                f.write(self._generate_context_load_test(app_class))
            generated += 1

        logger.info(f"Generated {generated} test files")

    def _generate_service_test(self, service_class: str) -> str:
        # SBG-24 FIX: @SpringBootTest with only @MockBean DataSource still lets
        # Hibernate attempt schema validation (DdlTransactionIsolatorNonJtaImpl)
        # against the mocked DataSource, causing NullPointerException.
        # Fix: use @SpringBootTest(properties = {...}) to disable ddl-auto and
        # redirect datasource to an in-memory H2 instance so the context loads
        # cleanly without any real Oracle connection or DDL execution.
        return f"""package {self.package_name}.service;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import {self.package_name}.repository.*;
import javax.sql.DataSource;

@SpringBootTest(properties = {{
    "spring.datasource.url=jdbc:h2:mem:testdb;DB_CLOSE_DELAY=-1",
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.username=sa",
    "spring.datasource.password=",
    "spring.jpa.hibernate.ddl-auto=none",
    "spring.jpa.database-platform=org.hibernate.dialect.H2Dialect"
}})
class {service_class}Test {{

    @MockBean
    DataSource dataSource;

    @Autowired(required = false)
    private {service_class} service;

    @Test
    void contextLoads() {{
        // Verifies that the Spring context starts without errors.
    }}
}}
"""

    def _generate_context_load_test(self, app_class: str) -> str:
        return f"""package {self.package_name};

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import javax.sql.DataSource;

@SpringBootTest(properties = {{
    "spring.datasource.url=jdbc:h2:mem:testdb;DB_CLOSE_DELAY=-1",
    "spring.datasource.driver-class-name=org.h2.Driver",
    "spring.datasource.username=sa",
    "spring.datasource.password=",
    "spring.jpa.hibernate.ddl-auto=none",
    "spring.jpa.database-platform=org.hibernate.dialect.H2Dialect"
}})
class {app_class}ApplicationTests {{

    @MockBean
    DataSource dataSource;

    @Test
    void contextLoads() {{
        // Verifies that the Spring context starts without errors.
    }}
}}
"""

    def _generate_main_application_class(self) -> str:
        return f"""package {self.package_name};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.transaction.annotation.EnableTransactionManagement;

/**
 * Main application class for {self.project_name}
 */
@SpringBootApplication
@EnableJpaRepositories(basePackages = "{self.package_name}.repository")
@EnableTransactionManagement
public class {self._to_camel_case(self.project_name)}Application {{

    public static void main(String[] args) {{
        SpringApplication.run({self._to_camel_case(self.project_name)}Application.class, args);
    }}
}}
"""

    def _generate_base_exceptions(self) -> Dict[str, str]:
        def exc(name: str, status: str) -> str:
            return f"""package {self.package_name}.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.{status})
public class {name} extends RuntimeException {{
    public {name}(String message) {{ super(message); }}
    public {name}(String message, Throwable cause) {{ super(message, cause); }}
}}
"""
        return {
            "BusinessException": exc("BusinessException", "BAD_REQUEST"),
            "ResourceNotFoundException": exc("ResourceNotFoundException", "NOT_FOUND"),
            "ValidationException": exc("ValidationException", "BAD_REQUEST"),
        }

    def _generate_base_dto(self) -> str:
        return f"""package {self.package_name}.dto;

import java.io.Serializable;

public abstract class BaseDTO implements Serializable {{

    private static final long serialVersionUID = 1L;

    public abstract Object toEntity();

    public static <T extends BaseDTO> T fromEntity(Object entity) {{
        throw new UnsupportedOperationException("Implement in concrete DTO classes");
    }}
}}
"""

    def _generate_config_classes(self) -> Dict[str, str]:
        return {
            'DatabaseConfig': f"""package {self.package_name}.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;
import org.springframework.transaction.annotation.EnableTransactionManagement;

@Configuration
@EnableJpaAuditing
@EnableTransactionManagement
public class DatabaseConfig {{}}
""",
            'WebConfig': f"""package {self.package_name}.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig implements WebMvcConfigurer {{

    @Override
    public void addCorsMappings(CorsRegistry registry) {{
        registry.addMapping("/**")
                .allowedOrigins("*")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(false);
    }}
}}
""",
            'SwaggerConfig': f"""package {self.package_name}.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {{

    @Bean
    public OpenAPI customOpenAPI() {{
        return new OpenAPI()
                .info(new Info()
                        .title("{self.project_name}")
                        .version("1.0.0")
                        .description("API documentation for the PL/SQL modernization project"));
    }}
}}
""",
            'GlobalExceptionHandler': f"""package {self.package_name}.config;

import {self.package_name}.exception.BusinessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * Global exception handler — converts exceptions to clean JSON responses.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {{

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<Map<String, Object>> handleBusiness(BusinessException ex) {{
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of(
                "error", ex.getMessage(),
                "timestamp", LocalDateTime.now().toString()
        ));
    }}

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> handleIllegalArg(IllegalArgumentException ex) {{
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of(
                "error", ex.getMessage(),
                "timestamp", LocalDateTime.now().toString()
        ));
    }}

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleGeneral(Exception ex) {{
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(Map.of(
                "error", "Internal server error: " + ex.getMessage(),
                "timestamp", LocalDateTime.now().toString()
        ));
    }}
}}
""",
        }

    def _generate_additional_configs(self):
        dockerfile = self._generate_dockerfile()
        with open(self.target_directory / 'Dockerfile', 'w', encoding='utf-8') as f:
            f.write(dockerfile)

        gitignore = self._generate_gitignore()
        with open(self.target_directory / '.gitignore', 'w', encoding='utf-8') as f:
            f.write(gitignore)

        # SBG-19 FIX: generate Gradle wrapper for Gradle projects so the build
        # always uses a pinned, compatible Gradle version regardless of what is
        # installed on the developer's machine.
        if self.build_tool == 'gradle':
            self._generate_gradle_wrapper()

        # SBG-15: _generate_additional_configs no longer writes README
        # README is written exclusively by _generate_readme() called from generate_project()
        logger.info("Additional configuration files generated")

    def _generate_gradle_wrapper(self):
        """
        SBG-19 FIX: Write gradle/wrapper/gradle-wrapper.properties pinned to
        Gradle 8.7, which is the latest release fully compatible with
        io.spring.dependency-management 1.1.4 and Spring Boot 3.2.x.
        This prevents the getDirMode() API breakage introduced in Gradle 8.8.
        """
        wrapper_dir = self.target_directory / 'gradle' / 'wrapper'
        wrapper_dir.mkdir(parents=True, exist_ok=True)
        props = (
            "distributionBase=GRADLE_USER_HOME\n"
            "distributionPath=wrapper/dists\n"
            "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.7-bin.zip\n"
            "networkTimeout=10000\n"
            "validateDistributionUrl=true\n"
            "zipStoreBase=GRADLE_USER_HOME\n"
            "zipStorePath=wrapper/dists\n"
        )
        with open(wrapper_dir / 'gradle-wrapper.properties', 'w', encoding='utf-8') as f:
            f.write(props)
        logger.info("Gradle wrapper properties generated (Gradle 8.7)")

    def _generate_dockerfile(self) -> str:
        return f"""FROM openjdk:{self.java_version}-jdk-slim
WORKDIR /app
COPY target/{self.project_name}-1.0.0.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
"""

    def _generate_gitignore(self) -> str:
        return """*.class
*.log
target/
build/
.gradle
.idea/
*.iml
.vscode/
.DS_Store
Thumbs.db
application-local.yml
application-dev.yml
application-prod.yml
"""

    def _generate_readme(self):
        """SBG-15: single README generation method."""
        readme_content = f"""# {self.project_name}

Auto-generated Spring Boot application from PL/SQL modernization.

## Project Info

- **Package**: {self.package_name}
- **Java**: {self.java_version}
- **Spring Boot**: {self.spring_boot_version}
- **Generated**: {self._get_current_time()}

## Quick Start

1. Edit `src/main/resources/application.properties` with your DB credentials
2. Run the SQL DDL against your Oracle schema
3. `mvn clean package && java -jar target/{self.project_name}-1.0.0.jar`

## API Docs

Swagger UI: `http://localhost:8080/swagger-ui/index.html`
"""
        with open(self.target_directory / 'README.md', 'w', encoding='utf-8') as f:
            f.write(readme_content)

    def _generate_project_summary(self, java_files: Dict[str, str]) -> Dict[str, Any]:
        summary = {
            'project_name': self.project_name,
            'package_name': self.package_name,
            'java_version': self.java_version,
            'spring_boot_version': self.spring_boot_version,
            'total_files': len(java_files),
            'file_types': {},
            'directories': [],
            # SBG-13: include build.gradle when build_tool is gradle
            'configuration_files': ['pom.xml', 'application.properties', 'Dockerfile', '.gitignore'],
        }
        if self.build_tool == 'gradle':  # SBG-13 fix
            summary['configuration_files'].insert(0, 'build.gradle')
            summary['configuration_files'].remove('pom.xml')

        for filename in java_files.keys():
            file_type = self._classify_java_file(filename, "")
            summary['file_types'][file_type] = summary['file_types'].get(file_type, 0) + 1

        for item in self.base_path.iterdir():
            if item.is_dir():
                summary['directories'].append(str(item.name))

        return summary

    def _to_camel_case(self, text: str) -> str:
        return ''.join(word.capitalize() for word in text.replace('-', '_').split('_'))

    def _normalize_entity_type_name(self, raw_name: str) -> str:
        if not raw_name:
            return raw_name
        stripped = raw_name.strip()
        if stripped in {"JpaRepository", "CrudRepository"}:
            return stripped
        lower = stripped.lower()
        base = stripped
        if lower.endswith("entity"):
            base = stripped[:-6]
        if "_" in base or base[:1].islower():
            base = self._to_camel_case(base)
        if lower.endswith("entity"):
            return f"{base}Entity"
        return base

    def _get_current_time(self) -> str:
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _extract_class_name(self, code: str) -> Optional[str]:
        for line in code.splitlines():
            stripped = line.strip()
            if stripped.startswith('public class '):
                return stripped.split()[2].split('{')[0].strip()
        return None

    def _extract_type_name(self, code: str) -> Optional[str]:
        for line in code.splitlines():
            stripped = line.strip()
            if stripped.startswith('public class '):
                return stripped.split()[2].split('{')[0].strip()
            if stripped.startswith('public interface '):
                return stripped.split()[2].split('{')[0].strip()
        return None

    def _normalize_entity_name(self, entity_name: str) -> str:
        if entity_name in self.RESERVED_ENTITY_NAMES:
            return f"{entity_name}Entity"
        return entity_name

    def _to_snake_case(self, value: str) -> str:
        if not value:
            return value
        return re.sub(r'(?<!^)(?=[A-Z])', '_', value).lower()

    def _lower_first(self, value: str) -> str:
        if not value:
            return value
        return value[0].lower() + value[1:]

    def _capitalize_first(self, value: str) -> str:
        if not value:
            return value
        return value[0].upper() + value[1:]

    def _to_lower_camel_case(self, value: str) -> str:
        if not value:
            return value
        pascal = self._to_camel_case(value)
        return self._lower_first(pascal)

    def _is_numeric_type(self, sql_type: str) -> bool:
        normalized = (sql_type or "").upper()
        return normalized.startswith(("NUMBER", "INT", "INTEGER", "SMALLINT", "BIGINT",
                                       "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "REAL"))

    def _map_sql_type_to_java(self, sql_type: str) -> str:
        normalized = sql_type.upper()
        if normalized.startswith(("VARCHAR", "CHAR", "CLOB", "NCLOB", "NVARCHAR")):
            return "String"
        if normalized.startswith("NUMBER"):
            if "," in normalized:
                return "BigDecimal"
            return "Long"
        if normalized.startswith(("INT", "INTEGER", "SMALLINT", "BIGINT")):
            return "Long"
        if normalized.startswith(("DATE", "TIMESTAMP")):
            return "LocalDateTime"
        if normalized.startswith(("FLOAT", "DOUBLE", "REAL")):
            return "Double"
        if normalized.startswith(("DECIMAL", "NUMERIC")):
            return "BigDecimal"
        return "String"

    def _generate_entity_from_ddl(self, entity_name: str, table_name: str, columns: List[Dict[str, str]], fk_list: Optional[List[Dict[str, str]]] = None) -> str:
        """
        SBG-20 FIX (Issue 6): accepts fk_list (list of dicts with keys
        'column', 'ref_table', 'ref_column') and emits @ManyToOne + @JoinColumn
        for every FK column instead of a plain Long field.
        """
        import_lines = ['import jakarta.persistence.*;']
        field_lines = []
        accessor_lines = []
        fk_list = fk_list or []

        # Build a quick lookup: fk_column_name (upper) -> ref_table_name
        fk_lookup: Dict[str, str] = {
            fk['column'].upper(): fk['ref_table']
            for fk in fk_list
            if 'column' in fk and 'ref_table' in fk
        }

        id_column = None
        for col in columns:
            if col["name"].upper() == "ID":
                id_column = col["name"]
                break
        if not id_column:
            for col in columns:
                if col["name"].upper().endswith("_ID") and col["name"].upper() not in fk_lookup:
                    id_column = col["name"]
                    break
        if not id_column:
            for col in columns:
                if col["name"].upper().endswith("_ID"):
                    id_column = col["name"]
                    break
        if not id_column and columns:
            id_column = columns[0]["name"]

        for col in columns:
            col_name = col["name"].upper()
            java_type = self._map_sql_type_to_java(col.get("type", ""))
            if java_type == "LocalDateTime":
                import_lines.append("import java.time.LocalDateTime;")
            if java_type == "BigDecimal":
                import_lines.append("import java.math.BigDecimal;")

            field_name = self._to_lower_camel_case(col_name)
            annotations = []

            # ── PK column ───────────────────────────────────────────────────
            if col_name == id_column.upper():
                annotations.append("@Id")
                if self._is_numeric_type(col.get("type", "")):
                    seq_name = f"{table_name.lower()}_seq"
                    annotations.append(
                        f'@SequenceGenerator(name = "seq_{field_name}", sequenceName = "{seq_name}", allocationSize = 1)'
                    )
                    annotations.append(
                        f'@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "seq_{field_name}")'
                    )
                annotations.append(f'@Column(name = "{col_name}")')
                field_lines.append("\n".join(f"    {a}" for a in annotations))
                field_lines.append(f"    private {java_type} {field_name};\n")

            # ── FK column → @ManyToOne / @JoinColumn ────────────────────────
            elif col_name in fk_lookup:
                ref_table = fk_lookup[col_name]
                ref_entity = f"{self._to_camel_case(ref_table.lower())}Entity"
                ref_entity = self._normalize_entity_name(ref_entity)
                # SBG-21 FIX: use lower_first() not _to_lower_camel_case() here.
                # _to_lower_camel_case() calls _to_camel_case() which lowercases
                # every character except the first of each underscore-split word,
                # so 'CustomersEntity' (no underscores) becomes 'customersentity'.
                # lower_first() preserves the interior PascalCase: 'customersEntity'.
                ref_field = self._lower_first(ref_entity)
                annotations.append("@ManyToOne(fetch = FetchType.LAZY)")
                annotations.append(f'@JoinColumn(name = "{col_name}")')
                field_lines.append("\n".join(f"    {a}" for a in annotations))
                field_lines.append(f"    private {ref_entity} {ref_field};\n")
                # Getter/setter use the entity type, not Long
                accessor_lines.append(
                    f"""    public {ref_entity} get{self._capitalize_first(ref_field)}() {{
        return {ref_field};
    }}

    public void set{self._capitalize_first(ref_field)}({ref_entity} {ref_field}) {{
        this.{ref_field} = {ref_field};
    }}
"""
                )
                continue  # accessor already appended

            # ── Regular column ───────────────────────────────────────────────
            else:
                annotations.append(f'@Column(name = "{col_name}")')
                field_lines.append("\n".join(f"    {a}" for a in annotations))
                field_lines.append(f"    private {java_type} {field_name};\n")

            accessor_lines.append(
                f"""    public {java_type} get{self._capitalize_first(field_name)}() {{
        return {field_name};
    }}

    public void set{self._capitalize_first(field_name)}({java_type} {field_name}) {{
        this.{field_name} = {field_name};
    }}
"""
            )

        imports = "\n".join(dict.fromkeys(import_lines))
        fields_block = "\n".join(field_lines).rstrip()
        accessors_block = "\n".join(accessor_lines).rstrip()

        return f"""package {self.package_name}.entity;

{imports}

@Entity
@Table(name = "{table_name}")
public class {entity_name} {{

{fields_block}

{accessors_block}
}}
"""

    def _generate_fallback_entity(self, entity_name: str, fields: Optional[List[Dict[str, str]]] = None) -> str:
        fields = fields or []
        import_lines = ['import jakarta.persistence.*;']
        normalized_entity_name = self._normalize_entity_name(entity_name)
        if any(field['type'] == 'LocalDateTime' for field in fields):
            import_lines.append('import java.time.LocalDateTime;')
        if entity_name in self.RESERVED_ENTITY_NAMES:
            entity_name += '_entity'
        field_blocks = []
        accessor_blocks = []
        for field in fields:
            field_name = field['name']
            field_type = field['type']
            field_blocks.append(
                f"""    @Column(name = "{self._to_snake_case(field_name)}")
    private {field_type} {field_name};"""
            )
            accessor_blocks.append(
                f"""    public {field_type} get{field_name[0].upper() + field_name[1:]}() {{
        return {field_name};
    }}

    public void set{field_name[0].upper() + field_name[1:]}({field_type} {field_name}) {{
        this.{field_name} = {field_name};
    }}"""
            )

        fields_section = ('\n\n' + '\n\n'.join(field_blocks)) if field_blocks else ''
        accessors_section = ('\n\n' + '\n\n'.join(accessor_blocks)) if accessor_blocks else ''

        # SBG-14: SEQUENCE strategy to match Oracle named-sequence DDL
        return f"""package {self.package_name}.entity;

{chr(10).join(import_lines)}

@Entity
@Table(name = "{entity_name.lower()}")
public class {normalized_entity_name} {{

    @Id
    @SequenceGenerator(name = "seq_id", sequenceName = "{entity_name.lower()}_seq", allocationSize = 1)
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "seq_id")
    private Long id;{fields_section}

    public Long getId() {{
        return id;
    }}

    public void setId(Long id) {{
        this.id = id;
    }}{accessors_section}
}}
"""

    def generate_repositories(self, entities: Dict[str, str]) -> Dict[str, str]:
        # SBG-18 FIX: when called standalone (Stage 7 in the pipeline, after
        # generate_project/generate_entities), _latest_java_code and
        # _ddl_table_map may be empty because they are only set inside
        # generate_project().  Rebuild both from the already-written entity
        # files on disk and from the entities dict passed in.
        #
        # (a) Rebuild _ddl_table_map from entity filenames so that repository
        #     generation can resolve entity names correctly.
        if not self._ddl_table_map:
            entity_dir = self.package_path / 'entity'
            if entity_dir.exists():
                for ef in entity_dir.glob('*.java'):
                    ename = ef.stem
                    base = ename[:-6] if ename.lower().endswith('entity') else ename
                    key = base.lower()
                    self._ddl_table_map[key] = base.upper()
                    if key.endswith('s'):
                        self._ddl_table_map[key[:-1]] = base.upper()
                    # SBG-22: extract columns so _audit_and_complete_repository works
                    if not self._ddl_columns.get(base.upper()):
                        try:
                            code = ef.read_text(encoding='utf-8')
                            self._ddl_columns[base.upper()] = \
                                self._extract_columns_from_entity_code(code)
                        except OSError:
                            pass
            # Also index from the entities dict itself
            for fname in entities:
                ename = fname.replace('.java', '')
                base = ename[:-6] if ename.lower().endswith('entity') else ename
                key = base.lower()
                self._ddl_table_map.setdefault(key, base.upper())
                if key.endswith('s'):
                    self._ddl_table_map.setdefault(key[:-1], base.upper())

        # (b) Rebuild _latest_java_code by reading every already-written Java
        #     file from the service directory so referenced-repository scanning works.
        if not getattr(self, '_latest_java_code', None):
            self._latest_java_code = {}
            for sub in ('service', 'repository', 'controller'):
                sub_dir = self.package_path / sub
                if sub_dir.exists():
                    for jf in sub_dir.glob('*.java'):
                        try:
                            self._latest_java_code[jf.name] = jf.read_text(encoding='utf-8')
                        except OSError:
                            pass

        repositories = {}

        repo_dir = self.package_path / 'repository'
        existing_repo_names: Set[str] = set()
        if repo_dir.exists():
            for repo_file in repo_dir.glob('*.java'):
                existing_repo_names.add(repo_file.stem)
        existing_repo_names.update(self._existing_repositories)

        # SBG-23 FIX: Re-audit repositories that were already written to disk
        # during Stage 5 (generate_project). At that point _ddl_columns was empty
        # so _audit_and_complete_repository bailed silently leaving repos incomplete
        # (missing INSERT/DELETE, incomplete UPDATE columns, missing @Param).
        # Now that Stage 6 (generate_entities) has populated _ddl_columns and
        # _ddl_table_map, re-read every existing repo, run the full audit/complete
        # pipeline on it, and overwrite the file if anything changed.
        if repo_dir.exists() and self._ddl_columns:
            for repo_file in sorted(repo_dir.glob('*.java')):
                try:
                    original = repo_file.read_text(encoding='utf-8')
                except OSError:
                    continue

                # Strip package+imports then run normalize (which calls audit)
                audited = self._normalize_repository_code(
                    repo_file.name, original, self._ddl_table_map
                )
                # Also ensure every @Query method has @Param on all its parameters
                audited = self._ensure_repo_params(audited)

                if audited != original:
                    repo_file.write_text(audited, encoding='utf-8')
                    repositories[repo_file.name] = audited
                    logger.info(f"Re-audited repository: {repo_file.name}")

        referenced_repo_names: Set[str] = set()
        for code in (getattr(self, "_latest_java_code", {}) or {}).values():
            for match in re.finditer(r'\b([A-Z]\w*)Repository\b', code):
                name = match.group(0)
                if name in {"JpaRepository", "CrudRepository"}:
                    continue
                referenced_repo_names.add(name)

        # SBG-12: deduplicate by entity base name (strip "Entity" suffix)
        seen_entity_bases: Set[str] = set()

        for filename, code in entities.items():
            entity_name = filename.replace('.java', '')
            if entity_name in {"Jpa", "JpaRepository", "CrudRepository"}:
                continue
            base_entity = entity_name[:-6] if entity_name.endswith("Entity") else entity_name
            # SBG-12: skip if we've already generated a repo for this base
            if base_entity in seen_entity_bases:
                continue
            repo_name = f"{entity_name}Repository.java"
            if repo_name.replace('.java', '') in existing_repo_names:
                continue
            if f"{base_entity}Repository" in existing_repo_names:
                continue
            seen_entity_bases.add(base_entity)
            repo_content = self._generate_repository_interface(entity_name)
            repositories[repo_name] = repo_content

        for repo_name in sorted(referenced_repo_names):
            if repo_name in {"JpaRepository", "CrudRepository"}:
                continue
            if repo_name in existing_repo_names or (repo_dir / f"{repo_name}.java").exists():
                continue
            base_entity = repo_name[:-10] if repo_name.endswith("Repository") else repo_name
            if base_entity in {"Jpa", "Crud", "Repository"}:
                continue
            if self._ddl_table_map:
                resolved_entity, _ = self._resolve_entity_from_ddl(base_entity, self._ddl_table_map)
            else:
                resolved_entity = base_entity
            resolved_entity = self._normalize_entity_name(resolved_entity)
            repositories[f"{repo_name}.java"] = self._generate_repository_interface(
                resolved_entity, repo_name=repo_name
            )

        for filename, code in repositories.items():
            file_path = repo_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

        logger.info(f"Generated {len(repositories)} repository interfaces")
        return repositories

    def _generate_repository_interface(self, entity_name: str, repo_name: Optional[str] = None) -> str:
        interface_name = repo_name or f"{entity_name}Repository"
        return f"""package {self.package_name}.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import {self.package_name}.entity.{entity_name};

/**
 * JPA repository for {entity_name}
 */
@Repository
public interface {interface_name} extends JpaRepository<{entity_name}, Long> {{
    // Custom query methods can be added here
}}
"""

    def generate_services(self, java_code: Dict[str, str]) -> Dict[str, str]:
        # SBG-16 FIX: ensure _ddl_table_map is populated from entity sources
        # before normalising any service, so that _derive_entity_name can map
        # procedure-named services to the correct entity class.
        if not self._ddl_table_map:
            for filename, code in java_code.items():
                file_type = self._classify_java_file(filename, code)
                if file_type != 'entity':
                    continue
                type_name = self._extract_type_name(code)
                if not type_name:
                    continue
                base = type_name[:-6] if type_name.lower().endswith('entity') else type_name
                key = base.lower()
                self._ddl_table_map[key] = base.upper()
                if key.endswith('s'):
                    self._ddl_table_map[key[:-1]] = base.upper()

        services = {}
        service_dir = self.package_path / 'service'

        # SBG-23 FIX: Re-normalise service files that were already written during
        # Stage 5 (generate_project). At that point _ddl_table_map was empty so
        # _derive_entity_name fell back to raw class names, entity imports were wrong,
        # and _inject_crud_repository_calls had no repository names to inject.
        # Now that Stage 6 has populated _ddl_table_map, re-read each service,
        # run the full normalisation pipeline, and overwrite if anything changed.
        if service_dir.exists() and self._ddl_table_map:
            for svc_file in sorted(service_dir.glob('*.java')):
                if svc_file.stem.endswith('Test'):
                    continue
                try:
                    original = svc_file.read_text(encoding='utf-8')
                except OSError:
                    continue
                normalised = self._normalize_service_code(svc_file.name, original)
                if normalised != original:
                    svc_file.write_text(normalised, encoding='utf-8')
                    services[svc_file.name] = normalised
                    logger.info(f"Re-normalised service: {svc_file.name}")

        for filename, code in java_code.items():
            class_name = None
            for line in code.splitlines():
                stripped = line.strip()
                if stripped.startswith('public class '):
                    class_name = stripped.split()[2]
                    break

            looks_like_service = (
                '@Service' in code
                or filename.lower().endswith('service.java')
                or (class_name is not None and class_name.lower().endswith('service'))
            )
            if looks_like_service:
                target_filename = f"{class_name}.java" if class_name else filename
                normalised = self._normalize_service_code(target_filename, code)
                services[target_filename] = normalised
                file_path = service_dir / target_filename
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(normalised)

        logger.info(f"Generated {len(services)} service classes")
        return services

    def _normalize_service_code(self, filename: str, code: str) -> str:
        """
        SBG-7 FIX: All regex word-boundary patterns are built as variables
        BEFORE being used in re.sub(), never inside f-strings.
        SBG-11 FIX: Inject repository calls for INSERT/UPDATE/DELETE/SELECT actions
        when the service body contains only TODO stubs.
        """
        service_name = filename.replace('.java', '')
        class_name = self._extract_class_name(code) or service_name
        entity_names = self._derive_entity_names(filename, class_name, code)
        repository_names: List[str] = []
        repository_base_map: Dict[str, str] = {}

        for match in re.finditer(r'\b([A-Z]\w*)Repository\b', code):
            raw_base = match.group(1)
            resolved_entity, _ = self._resolve_entity_from_ddl(raw_base, self._ddl_table_map)
            resolved_entity = self._normalize_entity_name(resolved_entity)
            repo_base = resolved_entity[:-6] if resolved_entity.endswith("Entity") else resolved_entity
            repository_name = f"{repo_base}Repository"
            if repository_name not in repository_names:
                repository_names.append(repository_name)
            repository_base_map[raw_base] = repository_name

        import_lines = [
            'import org.springframework.beans.factory.annotation.Autowired;',
            'import org.springframework.stereotype.Service;',
            'import org.springframework.transaction.annotation.Transactional;',
        ]
        if 'LocalDateTime' in code:
            import_lines.append('import java.time.LocalDateTime;')
        if 'List<' in code:
            import_lines.append('import java.util.List;')
        if 'Optional<' in code:
            import_lines.append('import java.util.Optional;')
        # FIX: add all commonly LLM-generated types that were missing
        if 'BigDecimal' in code:
            import_lines.append('import java.math.BigDecimal;')
        if 'DataAccessException' in code:
            import_lines.append('import org.springframework.dao.DataAccessException;')
        if 'EntityManager' in code or '@PersistenceContext' in code:
            import_lines.append('import jakarta.persistence.EntityManager;')
            import_lines.append('import jakarta.persistence.PersistenceContext;')
        if re.search(r'\bQuery\b', code) and 'EntityManager' in code:
            import_lines.append('import jakarta.persistence.Query;')
        if 'PersistenceException' in code:
            import_lines.append('import jakarta.persistence.PersistenceException;')
        if 'LoggerFactory' in code or re.search(r'\bLogger\b', code):
            import_lines.append('import org.slf4j.Logger;')
            import_lines.append('import org.slf4j.LoggerFactory;')

        for entity_name in entity_names:
            normalized_entity, _ = self._resolve_entity_from_ddl(entity_name, self._ddl_table_map)
            normalized_entity = self._normalize_entity_name(normalized_entity)
            import_lines.append(f'import {self.package_name}.entity.{normalized_entity};')
        for repository_name in repository_names:
            import_lines.append(f'import {self.package_name}.repository.{repository_name};')
        import_lines.append(f'import {self.package_name}.exception.BusinessException;')
        imports = '\n'.join(dict.fromkeys(import_lines))

        # SBG-27 FIX: Strip any LLM-appended garbage after the class closing brace
        # BEFORE stripping imports/package — otherwise we'd emit garbage as Java code.
        code = _strip_llm_trailing_garbage(code)

        body_lines = [
            line for line in code.splitlines()
            if not line.strip().startswith('package ')
            and not line.strip().startswith('import ')
        ]
        body = '\n'.join(body_lines).strip()

        # SBG-7 FIX: repository renaming via pre-built pattern variables
        for raw_base, repository_name in repository_base_map.items():
            pat = re.compile(r'\b' + re.escape(raw_base) + r'Repository\b')
            body = pat.sub(repository_name, body)

        if '@Service' not in body:
            body = body.replace(f"public class {service_name}", f"@Service\npublic class {service_name}")

        # FIX: if LLM used EntityManager/createNativeQuery instead of a repository,
        # strip the EntityManager field and force the body through the repository injector.
        if 'createNativeQuery' in body and repository_names:
            # Remove @PersistenceContext + EntityManager field declaration
            body = re.sub(
                r'\s*@PersistenceContext\s*\n\s*private\s+EntityManager\s+\w+\s*;',
                '',
                body,
            )
            # Remove any executeCreate/executeUpdate/executeDelete private helper methods
            body = re.sub(
                r'\s*private\s+void\s+execute\w+\([^)]*\)\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}',
                '',
                body,
                flags=re.DOTALL,
            )
            # Remove nested static exception class if present
            body = re.sub(
                r'\s*public\s+static\s+class\s+\w+Exception\s+extends\s+RuntimeException\s*\{[^}]*\}',
                '',
                body,
            )
            # Force inject correct repository calls now that stubs are cleared
            body = self._inject_crud_repository_calls(body, entity_names, repository_names)

        # FIX: deduplicate consecutive identical case labels produced when
        # the CREATE→INSERT substitution fires on a body that already has INSERT.
        body = re.sub(r'(case "[A-Z]+":\s*)\n(\s*\1)', r'\1', body)

        # SBG-21 FIX: Replace wrong entity class names that the LLM invents.
        # The LLM sometimes uses:
        #   (a) Bare names: "Customer", "Order" instead of "CustomersEntity"
        #   (b) ALLCAPS names: "CUSTOMERSEntity" because entity_names list was
        #       built with a broken _to_pascal_case that didn't lowercase input.
        # Both cause "cannot find symbol" compile errors.
        #
        # Two-pass replacement:
        # Pass A (DDL-map-independent): fix ALLCAPS entity names using regex —
        #   any token matching [A-Z]{2,}[a-z]*Entity is normalised to PascalCase.
        #   e.g. CUSTOMERSEntity -> CustomersEntity, ORDERSEntity -> OrdersEntity
        # Pass B (DDL-map-dependent): fix bare/wrong names using _resolve_entity_from_ddl.

        # Pass A — normalise ALLCAPS entity names without needing _ddl_table_map
        allcaps_entity_pat = re.compile(r'\b([A-Z]{2,}[A-Za-z]*)Entity\b')
        def _normalise_allcaps_entity(m: re.Match) -> str:
            raw = m.group(1)   # e.g. "CUSTOMERS"
            # capitalize() lowercases then uppercases first char
            parts = [p.capitalize() for p in re.split(r'[^A-Za-z0-9]+', raw) if p]
            base = ''.join(parts)
            return f'{base}Entity'
        body = allcaps_entity_pat.sub(_normalise_allcaps_entity, body)

        # Pass B — replace bare/wrong names using DDL map (only when populated)
        if entity_names and self._ddl_table_map:
            for raw_name in entity_names:
                resolved, _ = self._resolve_entity_from_ddl(raw_name, self._ddl_table_map)
                resolved = self._normalize_entity_name(resolved)
                if resolved and resolved != raw_name:
                    # Replace usages like "Customer var" / "new Customer()" but NOT
                    # inside import/package lines (already stripped) or comments.
                    wrong_pat = re.compile(r'\b' + re.escape(raw_name) + r'\b')
                    body = wrong_pat.sub(resolved, body)

        # SBG-28 FIX: Replace entity constructor calls with args with no-arg + setters.
        # The LLM sometimes generates: new CustomersEntity(id, name, email, status)
        # but entity classes only have no-arg constructors, causing compile errors.
        # Detect pattern: new SomeEntity(args) and replace with no-arg constructor.
        if self._ddl_table_map:
            for table_key, table_val in self._ddl_table_map.items():
                entity_pascal = f"{self._to_camel_case(table_val.lower())}Entity"
                entity_pascal = self._normalize_entity_name(entity_pascal)
                # Pattern: new EntityClass(one or more args)
                ctor_pat = re.compile(
                    r'new\s+' + re.escape(entity_pascal) + r'\s*\([^)]+\)'
                )
                if ctor_pat.search(body):
                    body = ctor_pat.sub(f'new {entity_pascal}()', body)
                    logger.debug("SBG-28: replaced parameterised %s constructor with no-arg", entity_pascal)

        # SBG-25 FIX: Replace .setId( with the correct PK setter name.
        # The LLM sometimes calls .setId(pCustomerId) on an entity whose PK field
        # is named customerId (not id), causing "cannot find symbol: method setId()".
        # Derive the real PK setter from _ddl_columns for each entity in scope.
        if self._ddl_columns and entity_names and self._ddl_table_map:
            for raw_name in entity_names:
                _, table = self._resolve_entity_from_ddl(raw_name, self._ddl_table_map)
                if not table:
                    continue
                columns = self._ddl_columns.get(table.upper(), [])
                pk_col = next(
                    (c for c in columns if c['name'].upper().endswith('_ID')),
                    columns[0] if columns else None
                )
                if pk_col and pk_col['name'].upper() != 'ID':
                    pk_setter = 'set' + self._capitalize_first(
                        self._lower_first(self._to_camel_case(pk_col['name'].upper()))
                    )
                    # Replace .setId( -> .setPkSetter( only when .setId is NOT a real method
                    if pk_setter != 'setId':
                        body = re.sub(r'\b\.setId\(', f'.{pk_setter}(', body)

        # SBG-11: inject real repository calls if all switch cases are TODO stubs
        body = self._inject_crud_repository_calls(body, entity_names, repository_names)
        # Deterministically correct insertXxx argument order from repository signatures.
        body = self._rewrite_insert_calls_from_repo_signature(body, repository_names)

        return f"""package {self.package_name}.service;

{imports}

{body}
"""

    def _resolve_repo_method_names(self, repo_name: str) -> dict:
        """
        FIX C1/C2: Scan the actual repository .java file on disk and extract the
        real insertXxx / updateXxx / deleteXxx / findXxx method names so that
        _inject_crud_repository_calls uses the exact declared names rather than
        constructing them from the table name.  Falls back to constructed names
        if the file does not exist yet (e.g. Stage 5 before Stage 7).

        Returns a dict with keys: insert, update, delete, select
        e.g. {'insert': 'insertCustomer', 'update': 'updateCustomer',
              'delete': 'deleteCustomer', 'select': 'findNameByCustomerId'}
        """
        methods = {'insert': None, 'update': None, 'delete': None, 'select': None}
        # Use self.base_path which is target_directory/src/main/java
        repo_path = getattr(self, 'base_path', None)
        if not repo_path:
            return methods
        # Locate the repo file anywhere under the java source root
        repo_file = None
        for candidate in repo_path.rglob(f'{repo_name}.java'):
            repo_file = candidate
            break
        if not repo_file or not repo_file.exists():
            return methods
        try:
            src = repo_file.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return methods

        # Extract method names from signatures: void/int methodName(@Param...)
        method_pat = re.compile(
            r'(?:void|int|\w+)\s+(\w+)\s*\(', re.MULTILINE
        )
        for m in method_pat.finditer(src):
            name = m.group(1)
            nl = name.lower()
            if nl.startswith('insert') and methods['insert'] is None:
                methods['insert'] = name
            elif nl.startswith('update') and methods['update'] is None:
                methods['update'] = name
            elif nl.startswith('delete') and methods['delete'] is None:
                methods['delete'] = name
            elif (nl.startswith('find') or nl.startswith('select') or nl.startswith('get'))                     and methods['select'] is None:
                methods['select'] = name
        return methods

    def _get_insert_params(self, repo_name: str) -> Optional[str]:
        """
        FIX D1/D2: Scan the repo file on disk to get the real parameter list of
        the insertXxx method.  Returns a formatted Java args string using the
        service method's parameter names mapped by position.
        Returns None if the repo file is not found or has no insert method.
        """
        param_names = self._get_insert_param_names(repo_name)
        return ', '.join(param_names) if param_names else None

    def _get_insert_param_names(self, repo_name: str) -> List[str]:
        """Return insert-method @Param names in declared repository order."""
        repo_path = getattr(self, 'base_path', None)
        if not repo_path:
            return []
        repo_file = None
        for candidate in repo_path.rglob(f'{repo_name}.java'):
            repo_file = candidate
            break
        if not repo_file or not repo_file.exists():
            return []
        try:
            src = repo_file.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return []
        # Find insertXxx method signature and extract @Param names.
        # The parameter list may span multiple lines, so match up to the
        # closing ); using DOTALL. [^;]+ stops at the semicolon safely.
        m = re.search(r'(?:void|int)\s+insert\w+\s*\(([^;]+)\)\s*;', src, re.DOTALL)
        if not m:
            return []
        param_block = m.group(1)
        return re.findall(r'@Param\("(\w+)"\)', param_block)

    def _resolve_service_argument_name(self, body: str, repo_param: str) -> Optional[str]:
        """Resolve a repository param to the most likely service variable name."""
        raw = (repo_param or '').strip()
        if not raw:
            return None

        candidates: List[str] = []
        parts = [p for p in re.split(r'[_\W]+', raw) if p]
        pascal = ''.join(p.capitalize() for p in parts) or raw[:1].upper() + raw[1:]
        camel = pascal[:1].lower() + pascal[1:] if pascal else raw

        for candidate in (f'p{pascal}', camel, raw, raw.lower()):
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        if raw.lower().startswith('p_'):
            trimmed = raw[2:]
            trim_parts = [p for p in re.split(r'[_\W]+', trimmed) if p]
            trimmed_pascal = ''.join(p.capitalize() for p in trim_parts)
            trimmed_camel = trimmed_pascal[:1].lower() + trimmed_pascal[1:] if trimmed_pascal else trimmed
            for candidate in (f'p{trimmed_pascal}', trimmed_camel, trimmed):
                if candidate and candidate not in candidates:
                    candidates.append(candidate)

        for candidate in candidates:
            if re.search(r'\b' + re.escape(candidate) + r'\b', body):
                return candidate
        return None

    def _rewrite_insert_calls_from_repo_signature(self, body: str, repository_names: List[str]) -> str:
        """Rewrite repo.insertXxx(...) calls to the exact repository signature order."""
        for repo_name in repository_names:
            repo_var = repo_name[0].lower() + repo_name[1:]
            insert_method = self._resolve_repo_method_names(repo_name).get('insert')
            if not insert_method:
                continue
            param_names = self._get_insert_param_names(repo_name)
            if not param_names:
                continue

            resolved_args: List[str] = []
            for param_name in param_names:
                resolved = self._resolve_service_argument_name(body, param_name)
                if not resolved:
                    resolved_args = []
                    break
                resolved_args.append(resolved)
            if not resolved_args:
                continue

            call_pat = re.compile(
                r'\b' + re.escape(repo_var) + r'\s*\.\s*' + re.escape(insert_method) + r'\s*\([^;]*\)\s*;',
                re.DOTALL,
            )
            body = call_pat.sub(f'{repo_var}.{insert_method}({", ".join(resolved_args)});', body)

        return body

    def _inject_crud_repository_calls(
        self, body: str, entity_names: List[str], repository_names: List[str]
    ) -> str:
        """
        SBG-11 / SBG-20 FIX: Replace stub cases in action-based switch blocks
        with real JPA repository calls, and ensure the repository field is
        @Autowired into the service class.

        Handles two stub patterns the LLM produces:
          (a) // TODO comment stubs  (original SBG-11 case)
          (b) throw new BusinessException("... not implemented") stubs
              (SBG-20: LLM throws instead of using TODO, bypassing the old check)

        Also always injects the @Autowired repository field if it is missing.
        """
        if not repository_names:
            return body

        entity_name = entity_names[0] if entity_names else "Entity"
        normalized_entity, _ = self._resolve_entity_from_ddl(entity_name, self._ddl_table_map)
        normalized_entity = self._normalize_entity_name(normalized_entity)
        repo_name = repository_names[0]
        repo_var = repo_name[0].lower() + repo_name[1:]
        entity_var = normalized_entity[0].lower() + normalized_entity[1:]
        id_type = "Long"

        # FIX C1/C2: Resolve actual method names from the repo file on disk.
        # This prevents the LLM from inventing names like .insert()/.update() that
        # don't exist, and ensures the generated service matches whatever the repo
        # file actually declares (insertCustomer, updateCustomer, etc.).
        real_methods = self._resolve_repo_method_names(repo_name)
        insert_method = real_methods.get('insert') or f'insert{normalized_entity.replace("Entity", "")}'
        update_method = real_methods.get('update') or f'update{normalized_entity.replace("Entity", "")}'
        delete_method = real_methods.get('delete') or 'deleteById'
        select_method = real_methods.get('select') or 'findById'

        # FIX D1/D2: Build INSERT call using actual @Param names from repo method.
        # The PK column is sequence-generated so must NOT be passed to insertXxx.
        insert_params_str = self._get_insert_params(repo_name)

        # SBG-20: inject @Autowired repo field if not already present
        autowired_field = f'    @Autowired\n    private {repo_name} {repo_var};'
        if repo_name not in body:
            # Insert after the opening brace of the class
            body = re.sub(
                r'(public\s+class\s+\w+\s*\{)',
                r'\1\n\n' + autowired_field,
                body,
                count=1
            )

        # SBG-20: stub detection — both TODO comments and throw-not-implemented patterns
        has_todo = '// TODO' in body
        has_throw_stub = bool(re.search(
            r'case\s+"(?:INSERT|UPDATE|DELETE|SELECT|CREATE)"\s*:\s*'
            r'(?://[^\n]*)?\s*throw\s+new\s+\w+Exception\s*\([^)]*not\s+implement',
            body, re.IGNORECASE
        ))

        if not has_todo and not has_throw_stub:
            return body

        # FIX C1/C2/D1/D2: Build switch cases using real repo method names and
        # real @Param names from the repo file on disk.  Fall back to constructed
        # names when the repo file isn't on disk yet (early pipeline stages).
        if insert_params_str:
            insert_call = f'{repo_var}.{insert_method}({insert_params_str});'
        else:
            insert_call = (
                f'{normalized_entity} {entity_var} = new {normalized_entity}();\n'
                f'                    // TODO: set fields from parameters\n'
                f'                    {repo_var}.save({entity_var});'
            )

        replacements = {
            'case "INSERT":': (
                f'case "INSERT":\n'
                f'                    {insert_call}\n'
                f'                    break;'
            ),
            'case "UPDATE":': (
                f'case "UPDATE":\n'
                f'                    {normalized_entity} existing{normalized_entity} = '
                f'{repo_var}.findById(pId != null ? pId : 0L)\n'
                f'                            .orElseThrow(() -> new BusinessException("{normalized_entity} not found"));\n'
                f'                    // TODO: update fields from parameters\n'
                f'                    {repo_var}.save(existing{normalized_entity});\n'
                f'                    break;'
            ),
            'case "DELETE":': (
                f'case "DELETE":\n'
                f'                    {repo_var}.deleteById(pId != null ? pId : 0L);\n'
                f'                    break;'
            ),
            'case "SELECT":': (
                f'case "SELECT":\n'
                f'                    {repo_var}.findById(pId != null ? pId : 0L)\n'
                f'                        .orElseThrow(() -> new BusinessException("{normalized_entity} not found"));\n'
                f'                    break;'
            ),
            'case "CREATE":': (
                f'case "CREATE":\n'
                f'                    {normalized_entity} {entity_var}New = new {normalized_entity}();\n'
                f'                    // TODO: set fields from parameters\n'
                f'                    {repo_var}.save({entity_var}New);\n'
                f'                    break;'
            ),
        }

        for placeholder, replacement in replacements.items():
            # Pattern A: case label followed by any number of comment lines then break.
            # SBG-24 FIX: old regex only matched a SINGLE // TODO line before break.
            # The LLM often writes multiple comment lines (// TODO + // Example: ...)
            # before the break, causing the single-line pattern to never match.
            # New: consume the case label then greedily eat any whitespace/comment
            # lines until the break statement.
            stub_pat_todo = re.compile(
                re.escape(placeholder) + r'(?:\s*//[^\n]*)*\s*break\s*;',
                re.DOTALL
            )
            body = stub_pat_todo.sub(replacement, body)

            # Pattern B: case + any number of comment lines + throw new XxxException(...)
            # SBG-24 FIX: also made greedy for multiple comment lines before throw.
            stub_pat_throw = re.compile(
                re.escape(placeholder) + r'(?:\s*//[^\n]*)*\s*throw\s+new\s+\w+Exception\s*\([^)]*\)\s*;',
                re.DOTALL | re.IGNORECASE
            )
            body = stub_pat_throw.sub(replacement, body)

        return body

    def _normalize_controller_code(self, filename: str, code: str) -> str:
        """
        SBG-8 FIX: Use actual newline '\n' not literal '\\n' as join separator.
        """
        controller_name = self._extract_type_name(code) or filename.replace('.java', '')
        body_lines = [
            line for line in code.splitlines()
            if not line.strip().startswith('package ')
            and not line.strip().startswith('import ')
        ]
        body = '\n'.join(body_lines).strip()

        import_lines = [
            'import org.springframework.web.bind.annotation.*;',
            'import org.springframework.http.ResponseEntity;',
        ]
        if '@Autowired' in body:
            import_lines.append('import org.springframework.beans.factory.annotation.Autowired;')

        service_candidates = set(re.findall(r'\b([A-Z]\w*Service)\b', body))
        if controller_name.endswith('Controller'):
            service_candidates.add(f"{controller_name[:-10]}Service")
        for service_name in sorted(service_candidates):
            import_lines.append(f'import {self.package_name}.service.{service_name};')
        if 'List<' in code:
            import_lines.append('import java.util.List;')
        if 'BigDecimal' in code:
            import_lines.append('import java.math.BigDecimal;')
        if 'LocalDateTime' in code:
            import_lines.append('import java.time.LocalDateTime;')
        if 'Optional<' in code:
            import_lines.append('import java.util.Optional;')

        import_lines = list(dict.fromkeys(import_lines))
        # SBG-8 FIX: actual newline character
        imports = '\n'.join(import_lines)

        return f"""package {self.package_name}.controller;

{imports}

{body}
"""

    def _normalize_repository_code(self, filename: str, code: str, ddl_map: Optional[Dict[str, str]] = None) -> str:
        # SBG-26 / SBG-28 FIX: Unconditionally strip duplicate @Modifying/@Transactional
        # annotations HERE, at the very start of normalisation — before imports are
        # rebuilt and before the audit runs. This catches duplicates that the LLM
        # writes in its initial output regardless of whether _ddl_columns is populated.
        # Previously the dedup only ran inside _audit_and_complete_repository which
        # requires _ddl_columns to be non-empty, so Stage-5 repos were never cleaned.
        code = _dedupe_annotation_block(code)
        code = _collapse_repository_query_annotations(code)

        type_name = self._extract_type_name(code) or filename.replace('.java', '')
        if type_name in {'JpaRepository', 'CrudRepository'}:
            return code

        import_lines = ['import org.springframework.stereotype.Repository;']
        if 'JpaRepository' in code:
            import_lines.append('import org.springframework.data.jpa.repository.JpaRepository;')
        if 'CrudRepository' in code:
            import_lines.append('import org.springframework.data.repository.CrudRepository;')
        if '@Query' in code or 'Query(' in code:
            import_lines.append('import org.springframework.data.jpa.repository.Query;')
        if '@Param' in code:
            import_lines.append('import org.springframework.data.repository.query.Param;')
        if '@Modifying' in code:
            import_lines.append('import org.springframework.data.jpa.repository.Modifying;')
        if '@Transactional' in code:
            import_lines.append('import org.springframework.transaction.annotation.Transactional;')
        if 'List<' in code:
            import_lines.append('import java.util.List;')
        if 'Optional<' in code:
            import_lines.append('import java.util.Optional;')
        if 'LocalDateTime' in code:
            import_lines.append('import java.time.LocalDateTime;')
        if 'BigDecimal' in code:
            import_lines.append('import java.math.BigDecimal;')

        entity_matches = re.findall(
            r'extends\s+(?:JpaRepository|CrudRepository)\s*<\s*([A-Za-z_][\w$#]*)',
            code,
        )
        ddl_map = ddl_map or {}
        for entity_name in entity_matches:
            normalized_entity, _ = self._resolve_entity_from_ddl(entity_name, ddl_map)
            normalized_entity = self._normalize_entity_name(normalized_entity)
            import_lines.append(f'import {self.package_name}.entity.{normalized_entity};')

        imports = '\n'.join(dict.fromkeys(import_lines))

        body_lines = [
            line for line in code.splitlines()
            if not line.strip().startswith('package ')
            and not line.strip().startswith('import ')
        ]
        body = '\n'.join(body_lines).strip()
        body = _collapse_repository_query_annotations(body)

        if '@Repository' not in body:
            body = re.sub(r'public\s+interface', '@Repository\npublic interface', body, count=1)

        # SBG-21 FIX: correct lowercase entity class names the LLM produces in
        # JPQL queries and JpaRepository<> generics.
        # e.g. "JpaRepository<paymentsEntity, Long>" -> "JpaRepository<PaymentsEntity, Long>"
        # e.g. "FROM paymentsEntity p" -> "FROM PaymentsEntity p"
        # Scan every known entity name and fix any occurrence with wrong capitalisation.
        if self._ddl_table_map:
            for table_key, table_val in self._ddl_table_map.items():
                entity_pascal = f"{self._to_camel_case(table_val.lower())}Entity"
                entity_pascal = self._normalize_entity_name(entity_pascal)
                # Build a pattern that matches the same word with any first-char case
                wrong_lower = entity_pascal[0].lower() + entity_pascal[1:]
                if wrong_lower != entity_pascal and wrong_lower in body:
                    body = body.replace(wrong_lower, entity_pascal)

        # SBG-20 FIX: ensure all 4 CRUD operations exist and UPDATE covers all columns
        body, extra_imports = self._audit_and_complete_repository(body, filename)
        body = _collapse_repository_query_annotations(body)
        for imp in extra_imports:
            if imp not in import_lines:
                import_lines.append(imp)
        imports = '\n'.join(dict.fromkeys(import_lines))

        return f"""package {self.package_name}.repository;

{imports}

{body}
"""

    def _extract_columns_from_entity_code(self, code: str) -> List[Dict[str, str]]:
        """
        SBG-22 FIX: Reverse-engineer column name+type info from an already-generated
        entity Java file so that _audit_and_complete_repository can use it even when
        generate_entities() hasn't run yet (i.e. during Stage 5 generate_project).

        Handles both the multi-line format the generator produces:
            @Column(name = "CUSTOMER_ID")
            private Long customerId;
        and the single-line format the LLM sometimes produces:
            @Column(name = "CUSTOMER_ID") private Long customerId;
        """
        columns: List[Dict[str, str]] = []
        lines = code.splitlines()
        pending_col_name: Optional[str] = None

        java_to_sql = {
            'BigDecimal': 'NUMBER(10,2)',
            'Long':       'NUMBER',
            'Integer':    'NUMBER',
            'String':     'VARCHAR2',
            'LocalDateTime': 'DATE',
            'Date':       'DATE',
        }

        for line in lines:
            stripped = line.strip()
            # Detect @Column(name = "COL_NAME") — may be followed by private on same line
            col_match = re.search(r'@Column\s*\([^)]*name\s*=\s*"([^"]+)"', stripped)
            if col_match:
                pending_col_name = col_match.group(1).upper()
                # Same-line: @Column(name = "X") private Long x;
                field_match = re.search(r'private\s+(\S+)\s+\w+\s*;', stripped)
                if field_match:
                    java_type = field_match.group(1).split('.')[-1]  # strip java.time. prefix
                    sql_type = java_to_sql.get(java_type, 'VARCHAR2')
                    columns.append({'name': pending_col_name, 'type': sql_type})
                    pending_col_name = None
                continue

            # Multi-line: @Column on previous line, private field on this line
            if pending_col_name:
                field_match = re.match(r'private\s+(\S+)\s+\w+\s*;', stripped)
                if field_match:
                    java_type = field_match.group(1).split('.')[-1]
                    sql_type = java_to_sql.get(java_type, 'VARCHAR2')
                    columns.append({'name': pending_col_name, 'type': sql_type})
                    pending_col_name = None
                elif stripped and not stripped.startswith('//') \
                        and not stripped.startswith('*') \
                        and not stripped.startswith('@'):
                    # A non-annotation, non-comment line that isn't a field resets pending
                    pending_col_name = None

        return columns

    def _ensure_repo_params(self, code: str) -> str:
        """
        SBG-23 FIX: Ensure every @Query method parameter has a @Param annotation.
        SBG-24 FIX: Previous implementation placed @Param BETWEEN the Java type and
        the parameter name (e.g. "Long @Param("x") x") which is illegal Java syntax.
        Java requires parameter annotations BEFORE the type: "@Param("x") Long x".

        This rewrite uses a single, correct substitution: find "Type paramName" where
        the param name appears in the query as :paramName, and prefix the whole pair
        with @Param("paramName") only when the annotation is not already present.
        """
        # Build a mapping from query :paramName -> (type, paramName) from method sigs
        # Strategy: for each @Query block, extract :params, then fix the method sig
        # by replacing "SomeType paramName" with "@Param("paramName") SomeType paramName"

        def fix_signature(sig: str, named_params: set) -> str:
            for pname in sorted(named_params):
                # Skip if already annotated correctly
                if f'@Param("{pname}")' in sig or f"@Param('{pname}')" in sig:
                    continue
                # Match "TypeName paramName" or "Type<Generic> paramName" followed
                # by comma or closing paren, and prefix with @Param("paramName").
                # Pattern: word-boundary + one or more type tokens + whitespace + pname
                # We look for the pattern where pname is a standalone word at a param
                # position (after type, before , or )).
                # Correct placement: @Param("x") TypeName x
                sig = re.sub(
                    r'(\b(?:[A-Z][\w.<>\[\]]*|[a-z][\w.<>\[\]]*)\s+)' +
                    r'(\b' + re.escape(pname) + r'\b)(\s*[,)])',
                    lambda m: f'@Param("{pname}") ' + m.group(1) + m.group(2) + m.group(3),
                    sig
                )
            return sig

        # Process the code: find each @Query block and fix the following method sig
        result = []
        lines = code.splitlines(keepends=True)
        i = 0
        while i < len(lines):
            line = lines[i]
            if not re.search(r'@Query\s*\(', line):
                result.append(line)
                i += 1
                continue

            # Collect full @Query annotation (may span multiple lines)
            query_block = line
            j = i + 1
            open_parens = query_block.count('(') - query_block.count(')')
            while open_parens > 0 and j < len(lines):
                query_block += lines[j]
                open_parens += lines[j].count('(') - lines[j].count(')')
                j += 1

            # Extract :paramName placeholders from the query string
            named_params = set(re.findall(r':([a-zA-Z]\w*)', query_block))

            # Emit the @Query block lines unchanged
            for k in range(i, j):
                result.append(lines[k])
            i = j

            # Skip any intervening annotations (@Modifying, @Transactional, etc.)
            while i < len(lines) and re.match(r'\s*@', lines[i].strip()):
                result.append(lines[i])
                i += 1

            # Collect the method signature (may span multiple lines)
            if i < len(lines):
                sig = lines[i]
                open_p = sig.count('(') - sig.count(')')
                i += 1
                while open_p > 0 and i < len(lines):
                    sig += lines[i]
                    open_p += lines[i].count('(') - lines[i].count(')')
                    i += 1
                result.append(fix_signature(sig, named_params))

        return ''.join(result)

    def _audit_and_complete_repository(self, body: str, filename: str) -> tuple:
        """
        SBG-20 FIX: Issues 4 & 5 — ensure every repository generated from a
        procedure-style service has all 4 CRUD operations and that UPDATE
        queries include every non-PK column from the DDL table.

        Returns (updated_body, extra_import_lines).
        """
        extra_imports: List[str] = []

        # SBG-25 FIX: Strip ANY duplicate consecutive @Modifying / @Transactional
        # annotations unconditionally. These appear when:
        #  (a) The LLM writes them twice in its own output, OR
        #  (b) The re-audit (SBG-23) re-runs _normalize_repository_code on a file
        #      that already has the annotations, and the UPDATE rebuild injects them
        #      again without removing the originals first.
        # Strategy: wherever we see @Modifying or @Transactional appearing more than
        # once consecutively (with only whitespace between repetitions), collapse to one.
        # SBG-25 FIX: Collapse any consecutive duplicate @Modifying / @Transactional
        # annotations down to one of each. Uses a simple line-by-line dedup so no
        # newline-in-regex issues arise.
        body = _dedupe_annotation_block(body)

        # Derive table name from the interface name (e.g. CustomersRepository -> CUSTOMERS)
        iface_match = re.search(r'public\s+interface\s+(\w+)', body)
        if not iface_match:
            return body, extra_imports
        iface_name = iface_match.group(1)  # e.g. "CustomersRepository"

        # Derive entity class from JpaRepository<EntityClass, ...>
        entity_match = re.search(
            r'extends\s+JpaRepository\s*<\s*(\w+)\s*,', body
        )
        entity_class = entity_match.group(1) if entity_match else None

        # Get table name and columns from _ddl_table_map + stored column info
        table_name = None
        columns: List[Dict[str, str]] = []
        if self._ddl_table_map:
            base = iface_name.replace('Repository', '')
            key = base.replace('_', '').lower()
            table_name = self._ddl_table_map.get(key) or self._ddl_table_map.get(
                key[:-1] if key.endswith('s') else key + 's'
            )
        if table_name and hasattr(self, '_ddl_columns'):
            columns = self._ddl_columns.get(table_name.upper(), [])

        if not table_name or not columns:
            return body, extra_imports

        table_lower = table_name.lower()

        # Identify the PK column (first _ID column or first column)
        pk_col = next(
            (c for c in columns if c['name'].upper().endswith('_ID')),
            columns[0] if columns else None
        )
        if not pk_col:
            return body, extra_imports

        pk_name = pk_col['name'].upper()
        pk_java = self._to_lower_camel_case(pk_name)
        non_pk_cols = [c for c in columns if c['name'].upper() != pk_name
                       and c['name'].upper() != 'CREATED_AT']

        def needs_big_decimal():
            return any(self._map_sql_type_to_java(c.get('type', '')) == 'BigDecimal'
                       for c in non_pk_cols)

        # ── Issue 5: detect missing INSERT ────────────────────────────────────
        has_insert = bool(re.search(r'(?i)\bINSERT\s+INTO\b', body))
        if not has_insert:
            # Build column list and value placeholders
            insert_cols = [c['name'].upper() for c in columns]
            # Use sequence for PK, SYSDATE for created_at, params for rest
            value_parts = []
            param_parts = []
            for c in columns:
                cn = c['name'].upper()
                if cn == pk_name:
                    value_parts.append(f'{table_lower}_seq.NEXTVAL')
                elif cn == 'CREATED_AT':
                    value_parts.append('SYSDATE')
                else:
                    pname = self._to_lower_camel_case(cn)
                    value_parts.append(f':{pname}')
                    jtype = self._map_sql_type_to_java(c.get('type', ''))
                    param_parts.append((pname, jtype))
            cols_str = ', '.join(insert_cols)
            vals_str = ', '.join(value_parts)
            params_decl = '\n'.join(
                f'                      @Param("{p}") {t} {p},'
                for p, t in param_parts
            ).rstrip(',')
            insert_method = (
                f'\n    @Modifying\n'
                f'    @Transactional\n'
                f'    @Query(value = "INSERT INTO {table_lower} ({cols_str}) '
                f'VALUES ({vals_str})", nativeQuery = true)\n'
                f'    void insert{self._to_camel_case(table_lower)}(\n'
                f'{params_decl});\n'
            )
            # Inject before the closing brace of the interface
            body = re.sub(r'\}\s*$', insert_method + '\n}', body)
            extra_imports += [
                'import org.springframework.data.jpa.repository.Modifying;',
                'import org.springframework.transaction.annotation.Transactional;',
                'import org.springframework.data.jpa.repository.Query;',
                'import org.springframework.data.repository.query.Param;',
            ]
            if needs_big_decimal():
                extra_imports.append('import java.math.BigDecimal;')

        # ── Issue 5: detect missing DELETE ────────────────────────────────────
        has_delete = bool(re.search(r'(?i)\bDELETE\s+FROM\b', body))
        if not has_delete:
            delete_method = (
                f'\n    @Modifying\n'
                f'    @Transactional\n'
                # SBG-24 FIX: was missing '=' in WHERE clause -> "WHERE order_id :orderId"
                f'    @Query(value = "DELETE FROM {table_lower} WHERE {pk_name.lower()} = :{pk_java}",'
                f' nativeQuery = true)\n'
                f'    int delete{self._to_camel_case(table_lower)}By{self._to_camel_case(pk_name)}'
                f'(@Param("{pk_java}") Long {pk_java});\n'
            )
            body = re.sub(r'\}\s*$', delete_method + '\n}', body)
            extra_imports += [
                'import org.springframework.data.jpa.repository.Modifying;',
                'import org.springframework.transaction.annotation.Transactional;',
                'import org.springframework.data.jpa.repository.Query;',
                'import org.springframework.data.repository.query.Param;',
            ]

        # ── Issue 4: ensure UPDATE covers all non-PK, non-CREATED_AT columns ─
        # SBG-24 FIX: Previous JPQL rebuild used entity field names like 'o.customerId'
        # but when the column is a FK the entity has an object field ('customersEntity')
        # not a primitive Long — JPQL on such tables throws a QuerySyntaxException.
        # Fix: always rebuild incomplete UPDATE queries as native SQL, which uses
        # column names directly and is immune to FK object mapping issues.
        # Also fix: after replacing the @Query annotation, update the method's
        # @Param declarations to match the new parameter set, and replace the
        # method signature if it is missing params.
        entity_pascal = f"{self._to_camel_case(table_lower)}Entity"
        entity_pascal = self._normalize_entity_name(entity_pascal)
        update_match = re.search(
            r'(@Query\s*\([^)]*?(?:UPDATE\s+' + re.escape(table_lower) +
            r'|UPDATE\s+' + re.escape(entity_pascal) +
            r')[\s\S]*?\))',
            body, re.IGNORECASE
        )
        if update_match and non_pk_cols:
            existing_update = update_match.group(1)
            # Check whether all non-PK columns are represented in the SET clause
            missing_cols = [
                c for c in non_pk_cols
                if self._lower_first(self._to_camel_case(c['name'])) not in existing_update
                and c['name'].lower() not in existing_update.lower()
            ]
            if missing_cols:
                # Always rebuild as native SQL — safe for both plain columns and FK columns
                set_parts = ', '.join(
                    f'{c["name"].lower()} = :{self._lower_first(self._to_camel_case(c["name"]))}'
                    for c in non_pk_cols
                )
                # Build new @Query annotation
                new_query_ann = (
                    f'@Query(value = "UPDATE {table_lower} SET {set_parts} '
                    f'WHERE {pk_name.lower()} = :{pk_java}", nativeQuery = true)'
                )
                # Build correct method signature with all @Param declarations
                all_params = [(pk_java, 'Long')] + [
                    (self._lower_first(self._to_camel_case(c['name'])),
                     self._map_sql_type_to_java(c.get('type', '')))
                    for c in non_pk_cols
                ]
                params_sig = ', \n                     '.join(
                    f'@Param("{pname}") {ptype} {pname}'
                    for pname, ptype in all_params
                )
                method_name = f'update{self._to_camel_case(table_lower)}'
                new_method = (
                    f'    @Modifying\n'
                    f'    @Transactional\n'
                    f'    {new_query_ann}\n'
                    f'    int {method_name}({params_sig});'
                )
                # RC3 FIX: strip any duplicate @Modifying/@Transactional annotations
                # that the LLM wrote immediately before the matched @Query block,
                # so the rebuilt new_method doesn't produce duplicates.
                dup_prefix_pat = re.compile(
                    r'((?:\s*@Modifying\s*\n|\s*@Transactional\s*\n)+)' +
                    re.escape(existing_update),
                    re.DOTALL
                )
                body = dup_prefix_pat.sub(existing_update, body)

                # Replace the existing @Query block AND the entire method signature that follows it
                # Match from the @Query annotation up to and including the method declaration line
                update_method_pat = re.compile(
                    re.escape(existing_update) +
                    r'[\s\S]*?;(?=\s*\n)',
                    re.DOTALL
                )
                if update_method_pat.search(body):
                    body = update_method_pat.sub(new_method, body, count=1)
                else:
                    body = body.replace(existing_update, new_query_ann)
                extra_imports += [
                    'import org.springframework.data.jpa.repository.Modifying;',
                    'import org.springframework.transaction.annotation.Transactional;',
                    'import org.springframework.data.jpa.repository.Query;',
                    'import org.springframework.data.repository.query.Param;',
                ]
                if needs_big_decimal():
                    extra_imports.append('import java.math.BigDecimal;')

        return body, list(dict.fromkeys(extra_imports))

    def _normalize_entity_code(self, filename: str, code: str) -> str:
        type_name = self._extract_type_name(code) or filename.replace('.java', '')
        import_lines = ['import jakarta.persistence.*;']
        if 'LocalDateTime' in code:
            import_lines.append('import java.time.LocalDateTime;')
        if 'BigDecimal' in code:
            import_lines.append('import java.math.BigDecimal;')

        imports = '\n'.join(dict.fromkeys(import_lines))
        body_lines = [
            line for line in code.splitlines()
            if not line.strip().startswith('package ')
            and not line.strip().startswith('import ')
        ]
        body = '\n'.join(body_lines).strip()
        if '@Entity' not in body and any(token in body for token in ('@Id', '@Column', '@Table')):
            body = re.sub(r'public\s+class', '@Entity\npublic class', body, count=1)

        return f"""package {self.package_name}.entity;

{imports}

{body}
"""

    # ── Stubs for methods referenced elsewhere (kept for compatibility) ───────

    def _resolve_entity_from_ddl(self, raw_entity: str, ddl_map: Dict[str, str]) -> Tuple[str, Optional[str]]:
        if not raw_entity:
            return raw_entity, None
        raw = raw_entity.strip()
        lowered = raw.lower()
        base = raw[:-6] if lowered.endswith("entity") else raw
        base_key = base.replace("_", "").lower()
        table_name = ddl_map.get(base_key)
        if not table_name:
            if base_key.endswith("s"):
                table_name = ddl_map.get(base_key[:-1])
            else:
                table_name = ddl_map.get(f"{base_key}s")
        if table_name:
            entity_name = f"{self._to_camel_case(table_name.lower())}Entity"
            return entity_name, table_name
        entity_index = getattr(self, "_entity_name_index", None)
        if entity_index:
            candidate = entity_index.get(base_key)
            if candidate:
                return candidate, None
        return self._normalize_entity_type_name(raw), None

    def _derive_entity_names(self, filename: str, class_name: Optional[str], code: str) -> List[str]:
        entity_names: List[str] = []
        for match in re.finditer(r'\b([A-Z]\w*)Repository\b', code):
            candidate = match.group(1)
            if self._is_entity_candidate_name(candidate):
                entity_names.append(candidate)
        fallback = self._derive_entity_name(filename, class_name)
        if fallback and not entity_names:
            entity_names.append(fallback)
        ordered: List[str] = []
        seen = set()
        for name in entity_names:
            if name and name not in seen:
                ordered.append(name)
                seen.add(name)
        return ordered

    def _derive_entity_name(self, filename: str, class_name: Optional[str]) -> Optional[str]:
        """
        SBG-16 FIX: Resolve the derived base name against _ddl_table_map using
        both a direct lookup AND a camel-case suffix search before falling back
        to the raw stripped name.

        Problem: procedure-named service classes such as ManageCustomerService
        or OrderProcessingService strip to "ManageCustomer" / "OrderProcessing"
        after removing the "Service" suffix.  These multi-word bases don't match
        any DDL table key directly, so the old code silently used the raw value
        and generated "import ...entity.ManageCustomer" which does not exist.

        Resolution order:
          1. Strip the 'Service' suffix to get a raw base (e.g. "ManageCustomer").
          2. Direct lookup via _resolve_entity_from_ddl (works when base == table,
             e.g. "Payment" -> "payments").
          3. Camel-case segment suffix search: split the base into PascalCase
             words and try progressively shorter right-hand suffixes against the
             DDL map, longest match wins.
             e.g. "ManageCustomer" -> try "ManageCustomer", then "Customer"
                  "OrderProcessing" -> try "OrderProcessing", then "Processing"
             "Customer" matches "customer" -> "CUSTOMERS" -> "CustomersEntity".
          4. Fall back to the raw base only when the DDL map has no match at all
             (no DDL provided, or this is genuinely a new entity).
        """
        if class_name and class_name.lower().endswith('service'):
            base = class_name[:-7]
        elif filename.lower().endswith('service.java'):
            base = self._to_camel_case(filename[:-12])
        else:
            base = self._to_camel_case(filename.replace('.java', ''))

        if not base:
            return None

        if self._ddl_table_map:
            # Step 2: direct resolution (handles "PaymentService" -> "Payment" -> payments)
            resolved, table = self._resolve_entity_from_ddl(base, self._ddl_table_map)
            if table is not None:
                return resolved

            # Step 3: split PascalCase into words and try each right-hand suffix
            # AND each individual word, longest/leftmost match first.
            # e.g. "ManageCustomer"  -> ["Manage","Customer"]
            #      try: "Customer"                          -> matches customers
            # e.g. "OrderProcessing" -> ["Order","Processing"]
            #      try: "OrderProcessing", "Processing",    <- right suffixes
            #           "Order"                             <- individual words
            words = re.findall(r'[A-Z][a-z0-9]*', base)
            # Collect candidates: right-anchored suffixes then individual words
            # (deduplicated, preserving order)
            candidates = []
            seen_cands: set = set()
            # Right-anchored suffixes from length 2 down to 1 (full base tried above)
            for start in range(1, len(words)):
                suffix = ''.join(words[start:])
                if suffix not in seen_cands:
                    candidates.append(suffix)
                    seen_cands.add(suffix)
            # Individual words (catches "Order" in "OrderProcessing")
            for w in words:
                if w not in seen_cands:
                    candidates.append(w)
                    seen_cands.add(w)

            for candidate in candidates:
                resolved, table = self._resolve_entity_from_ddl(candidate, self._ddl_table_map)
                if table is not None:
                    return resolved

        return base

    def _is_entity_candidate_name(self, candidate: str) -> bool:
        # SBG-27 FIX: also block JPA/Spring framework class names that the LLM
        # sometimes uses as repository base names (JpaRepository, CrudRepository,
        # Customer, etc.) causing bogus imports like com.example.demo.entity.Jpa.
        blocked_suffixes = ('Exception', 'Result', 'Response', 'Request', 'DTO', 'Config', 'Controller', 'Service')
        blocked_names = {
            'BusinessException', 'IllegalArgumentException', 'ProcessOrderResult', 'TABLE',
            # JPA / Spring framework names that are never user-defined entities:
            'Jpa', 'JpaRepository', 'CrudRepository', 'Repository', 'Entity',
            'Optional', 'List', 'Map', 'Set', 'Collection', 'Object',
        }
        return (bool(candidate)
                and candidate not in blocked_names
                and not candidate.endswith(blocked_suffixes)
                and not candidate.startswith('javax.')
                and not candidate.startswith('jakarta.'))

    def _entity_has_meaningful_fields(self, code: str) -> bool:
        field_lines = [l for l in code.splitlines() if l.strip().startswith("private ")]
        if not field_lines:
            return False
        return any(" id;" not in l.lower() for l in field_lines)

    def _generate_controller(self, service_name: str, service_code: str) -> str:
        entity_name = service_name.replace('Service', '')
        service_var = service_name[0].lower() + service_name[1:]

        has_get_all = bool(re.search(r'\bgetAll\s*\(', service_code))
        has_get_by_id = bool(re.search(r'\bgetById\s*\(', service_code))
        has_create = bool(re.search(r'\bcreate\s*\(', service_code))
        has_update = bool(re.search(r'\bupdate\s*\(', service_code))
        has_delete = bool(re.search(r'\bdelete\s*\(', service_code))

        if not any([has_get_all, has_get_by_id, has_create, has_update, has_delete]):
            return ""

        import_lines = [
            'import org.springframework.beans.factory.annotation.Autowired;',
            'import org.springframework.http.ResponseEntity;',
            'import org.springframework.web.bind.annotation.*;',
            f'import {self.package_name}.service.{service_name};',
        ]
        if has_get_all:
            import_lines.append('import java.util.List;')
        # SBG-8 FIX: actual newline
        imports = '\n'.join(import_lines)

        methods = []
        if has_get_all:
            methods.append(
                f"    @GetMapping\n"
                f"    public ResponseEntity<List<?>> getAll{entity_name}s() {{\n"
                f"        return ResponseEntity.ok({service_var}.getAll());\n"
                f"    }}"
            )
        if has_create:
            methods.append(
                f"    @PostMapping\n"
                f"    public ResponseEntity<?> create{entity_name}(@RequestBody Object request) {{\n"
                f"        return ResponseEntity.ok({service_var}.create(request));\n"
                f"    }}"
            )
        if has_update:
            methods.append(
                f"    @PutMapping(\"/{{id}}\")\n"
                f"    public ResponseEntity<?> update{entity_name}(@PathVariable Long id, @RequestBody Object request) {{\n"
                f"        return ResponseEntity.ok({service_var}.update(id, request));\n"
                f"    }}"
            )
        if has_delete:
            methods.append(
                f"    @DeleteMapping(\"/{{id}}\")\n"
                f"    public ResponseEntity<Void> delete{entity_name}(@PathVariable Long id) {{\n"
                f"        {service_var}.delete(id);\n"
                f"        return ResponseEntity.noContent().build();\n"
                f"    }}"
            )

        # SBG-9 FIX: use actual newline characters
        methods_block = '\n\n'.join(methods)

        return f"""package {self.package_name}.controller;

{imports}

@RestController
@RequestMapping("/api/{entity_name.lower()}")
public class {entity_name}Controller {{

    @Autowired
    private {service_name} {service_var};

{methods_block}
}}
"""

    def generate_controllers(self, services: Dict[str, str]) -> Dict[str, str]:
        # SBG-18 FIX: the pipeline calls this method (Stage 9) with a dict of
        # filename -> Java source code produced by generate_services().
        # The old implementation only delegated to _generate_controller() which
        # returns "" for procedure-style action-switch services (no getAll/create
        # etc.), producing 0 controllers.
        # Fix: mirror the same two-path logic as _generate_controllers_from_services():
        #   1. Try the standard CRUD-method controller.
        #   2. Fall back to the action-dispatch controller for procedure services.
        controllers = {}
        controller_dir = self.package_path / 'controller'
        controller_dir.mkdir(parents=True, exist_ok=True)

        for filename, code in services.items():
            service_name = filename.replace('.java', '')

            # Try standard CRUD controller first
            controller_code = self._generate_controller(service_name, code)

            # Fall back to action-dispatch for procedure-style services
            if not controller_code:
                controller_code = self._generate_action_dispatch_controller(service_name, code)

            if not controller_code:
                continue

            if service_name.endswith('Service'):
                controller_filename = service_name[:-7] + 'Controller.java'
            else:
                controller_filename = service_name + 'Controller.java'

            normalized = self._normalize_controller_code(controller_filename, controller_code)
            controllers[controller_filename] = normalized

            file_path = controller_dir / controller_filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(normalized)

        logger.info(f"Generated {len(controllers)} controller classes")
        return controllers

    def generate_entities(self, java_code: Dict[str, str], ddl_columns: Optional[Dict[str, List[Dict[str, str]]]] = None, fk_map: Optional[Dict[str, List[Dict[str, str]]]] = None) -> Dict[str, str]:
        entities = {}
        ddl_columns = ddl_columns or {}
        ddl_map = {table.replace("_", "").lower(): table for table in ddl_columns.keys()}
        self._ddl_table_map = ddl_map
        # SBG-20: persist for use by _audit_and_complete_repository and FK injection
        self._ddl_columns = ddl_columns
        self._fk_map = fk_map or {}

        for filename, code in java_code.items():
            if '@Entity' in code or 'extends BaseEntity' in code:
                class_name = self._extract_class_name(code) or filename.replace('.java', '')
                if class_name in {"Jpa", "JpaRepository", "CrudRepository"}:
                    continue
                normalized_name = self._normalize_entity_name(class_name)
                target_filename = f"{normalized_name}.java"
                entities[target_filename] = code

        for table_name, columns in ddl_columns.items():
            ddl_entity_name = f"{self._to_camel_case(table_name.lower())}Entity"
            normalized_entity_name = self._normalize_entity_name(ddl_entity_name)
            target_filename = f"{normalized_entity_name}.java"
            if target_filename in entities:
                continue
            # SBG-20: pass FK relationships for this table
            table_fks = self._fk_map.get(table_name.upper(), [])
            entities[target_filename] = self._generate_entity_from_ddl(
                normalized_entity_name, table_name, columns, table_fks
            )

        if not entities:
            for filename, code in java_code.items():
                class_name = self._extract_class_name(code)
                for entity_name in self._derive_entity_names(filename, class_name, code):
                    normalized_entity_name = self._normalize_entity_name(entity_name)
                    fallback_name = f"{normalized_entity_name}.java"
                    if fallback_name not in entities:
                        entities[fallback_name] = self._generate_fallback_entity(entity_name, [])

        entity_dir = self.package_path / 'entity'
        for filename, code in entities.items():
            file_path = entity_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

        logger.info(f"Generated {len(entities)} entity classes")
        return entities

    def _looks_like_service_source(self, filename: str, code: str) -> bool:
        class_name = self._extract_class_name(code) or ''
        filename_lower = filename.lower()
        return (
            '@Service' in code
            or filename_lower.endswith('service.java')
            or class_name.lower().endswith('service')
        )

    def _is_entity_reference_type(self, field_type: str) -> bool:
        scalar_types = {
            'String', 'Long', 'Integer', 'Boolean', 'Double', 'Float',
            'BigDecimal', 'LocalDate', 'LocalDateTime', 'Instant', 'UUID',
        }
        return bool(field_type) and field_type not in scalar_types and field_type[:1].isupper()

    @staticmethod
    def parse_fk_constraints(sql_text: str) -> Dict[str, List[Dict[str, str]]]:
        """
        SBG-20 FIX (Issue 6): Parse ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY
        statements and return a map of table_name (upper) -> list of FK dicts.

        Each FK dict has keys:
          'column'     - the FK column on the source table (upper)
          'ref_table'  - the referenced table name (upper)
          'ref_column' - the referenced column name (upper)

        Example SQL handled:
          ALTER TABLE orders
          ADD CONSTRAINT fk_orders_customer
          FOREIGN KEY (customer_id)
          REFERENCES customers(customer_id);

        Returns: {'ORDERS': [{'column': 'CUSTOMER_ID',
                               'ref_table': 'CUSTOMERS',
                               'ref_column': 'CUSTOMER_ID'}], ...}
        """
        fk_map: Dict[str, List[Dict[str, str]]] = {}
        if not sql_text:
            return fk_map

        # Remove comments
        cleaned = re.sub(r'--[^\r\n]*', ' ', sql_text)
        cleaned = re.sub(r'/\*.*?\*/', ' ', cleaned, flags=re.DOTALL)

        pattern = re.compile(
            r'ALTER\s+TABLE\s+(?:"?[\w$#]+"?\s*\.\s*)?(?P<table>"?[\w$#]+"?)'
            r'.*?'
            r'FOREIGN\s+KEY\s*\(\s*(?P<fk_col>"?[\w$#]+"?)\s*\)'
            r'\s*REFERENCES\s+(?:"?[\w$#]+"?\s*\.\s*)?(?P<ref_table>"?[\w$#]+"?)'
            r'\s*\(\s*(?P<ref_col>"?[\w$#]+"?)\s*\)',
            re.IGNORECASE | re.DOTALL,
        )

        for m in pattern.finditer(cleaned):
            table = m.group('table').strip('"').upper()
            fk_col = m.group('fk_col').strip('"').upper()
            ref_table = m.group('ref_table').strip('"').upper()
            ref_col = m.group('ref_col').strip('"').upper()
            fk_map.setdefault(table, []).append({
                'column': fk_col,
                'ref_table': ref_table,
                'ref_column': ref_col,
            })

        return fk_map


def create_spring_boot_generator(config: Dict[str, Any]) -> SpringBootGenerator:
    return SpringBootGenerator(config)
