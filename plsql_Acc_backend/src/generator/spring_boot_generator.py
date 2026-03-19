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
        return f"""plugins {{
    id 'org.springframework.boot' version '{self.spring_boot_version}'
    id 'io.spring.dependency-management' version '1.1.3'
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
        logger.info(f"Generated {len(java_files)} Java source files")
        return java_files

    def _classify_java_file(self, filename: str, code: str) -> str:
        """
        SBG-10 FIX: repository/JPA check runs BEFORE entity annotation check.
        A repository interface importing entities will not be misclassified.
        """
        filename_lower = filename.lower()

        # Repository check FIRST (fixes SBG-10)
        if 'JpaRepository' in code or 'CrudRepository' in code or '@Repository' in code:
            return 'repository'
        if 'repository' in filename_lower or 'dao' in filename_lower:
            return 'repository'

        # Then entity
        if any(token in code for token in ('@Entity', '@Table', '@Id', '@Column')):
            return 'entity'
        if 'entity' in filename_lower or 'model' in filename_lower:
            return 'entity'

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

        if '@RestController' in code or '@Controller' in code:
            return 'controller'
        if '@Service' in code:
            return 'service'
        if '@Entity' in code:
            return 'entity'
        if '@Configuration' in code:
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
        return f"""package {self.package_name}.service;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import javax.sql.DataSource;

@SpringBootTest
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

@SpringBootTest
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
        }

    def _generate_additional_configs(self):
        dockerfile = self._generate_dockerfile()
        with open(self.target_directory / 'Dockerfile', 'w', encoding='utf-8') as f:
            f.write(dockerfile)

        gitignore = self._generate_gitignore()
        with open(self.target_directory / '.gitignore', 'w', encoding='utf-8') as f:
            f.write(gitignore)

        # SBG-15: _generate_additional_configs no longer writes README
        # README is written exclusively by _generate_readme() called from generate_project()
        logger.info("Additional configuration files generated")

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

    def _generate_entity_from_ddl(self, entity_name: str, table_name: str, columns: List[Dict[str, str]]) -> str:
        import_lines = ['import jakarta.persistence.*;']
        field_lines = []
        accessor_lines = []

        id_column = None
        for col in columns:
            if col["name"].upper() == "ID":
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
            if col_name == id_column:
                annotations.append("@Id")
                if self._is_numeric_type(col.get("type", "")):
                    # SBG-14: use SEQUENCE strategy for Oracle compatibility
                    seq_name = f"{table_name.lower()}_seq"
                    annotations.append(
                        f'@SequenceGenerator(name = "seq_{field_name}", sequenceName = "{seq_name}", allocationSize = 1)'
                    )
                    annotations.append('@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "seq_' + field_name + '")')
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
        repositories = {}

        repo_dir = self.package_path / 'repository'
        existing_repo_names: Set[str] = set()
        if repo_dir.exists():
            for repo_file in repo_dir.glob('*.java'):
                existing_repo_names.add(repo_file.stem)
        existing_repo_names.update(self._existing_repositories)

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
        services = {}

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
                services[target_filename] = self._normalize_service_code(target_filename, code)

        service_dir = self.package_path / 'service'
        for filename, code in services.items():
            file_path = service_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

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

        for entity_name in entity_names:
            normalized_entity, _ = self._resolve_entity_from_ddl(entity_name, self._ddl_table_map)
            normalized_entity = self._normalize_entity_name(normalized_entity)
            import_lines.append(f'import {self.package_name}.entity.{normalized_entity};')
        for repository_name in repository_names:
            import_lines.append(f'import {self.package_name}.repository.{repository_name};')
        import_lines.append(f'import {self.package_name}.exception.BusinessException;')
        imports = '\n'.join(dict.fromkeys(import_lines))

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

        # SBG-11: inject real repository calls if all switch cases are TODO stubs
        body = self._inject_crud_repository_calls(body, entity_names, repository_names)

        return f"""package {self.package_name}.service;

{imports}

{body}
"""

    def _inject_crud_repository_calls(
        self, body: str, entity_names: List[str], repository_names: List[str]
    ) -> str:
        """
        SBG-11 FIX: Replace // TODO stubs in action-based switch/if-else blocks
        with actual JPA repository calls.
        """
        if not repository_names or '// TODO' not in body:
            return body

        entity_name = entity_names[0] if entity_names else "Entity"
        normalized_entity, _ = self._resolve_entity_from_ddl(entity_name, self._ddl_table_map)
        normalized_entity = self._normalize_entity_name(normalized_entity)
        repo_name = repository_names[0]
        repo_var = repo_name[0].lower() + repo_name[1:]
        entity_var = normalized_entity[0].lower() + normalized_entity[1:]
        id_type = "Long"

        replacements = {
            'case "INSERT":': (
                f'case "INSERT":\n'
                f'                    {normalized_entity} {entity_var} = new {normalized_entity}();\n'
                f'                    // TODO: set fields from parameters\n'
                f'                    {repo_var}.save({entity_var});\n'
                f'                    break;'
            ),
            'case "UPDATE":': (
                f'case "UPDATE":\n'
                f'                    {repo_var}.findById(({id_type}) customerId).ifPresent(e -> {{\n'
                f'                        // TODO: update fields from parameters\n'
                f'                        {repo_var}.save(e);\n'
                f'                    }});\n'
                f'                    break;'
            ),
            'case "DELETE":': (
                f'case "DELETE":\n'
                f'                    {repo_var}.deleteById(({id_type}) customerId);\n'
                f'                    break;'
            ),
            'case "SELECT":': (
                f'case "SELECT":\n'
                f'                    return {repo_var}.findById(({id_type}) customerId)\n'
                f'                        .orElseThrow(() -> new BusinessException("Not found: " + customerId));\n'
            ),
            'case "CREATE":': (
                f'case "CREATE":\n'
                f'                    {normalized_entity} {entity_var}Create = new {normalized_entity}();\n'
                f'                    // TODO: set fields from parameters\n'
                f'                    {repo_var}.save({entity_var}Create);\n'
                f'                    break;'
            ),
        }

        for placeholder, replacement in replacements.items():
            # Only replace the stub pattern (case + TODO + break or just case + TODO)
            stub_pat = re.compile(
                re.escape(placeholder) + r'\s*// TODO[^\n]*\n\s*break;',
                re.DOTALL
            )
            body = stub_pat.sub(replacement, body)

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

        import_lines = list(dict.fromkeys(import_lines))
        # SBG-8 FIX: actual newline character
        imports = '\n'.join(import_lines)

        return f"""package {self.package_name}.controller;

{imports}

{body}
"""

    def _normalize_repository_code(self, filename: str, code: str, ddl_map: Optional[Dict[str, str]] = None) -> str:
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

        if '@Repository' not in body:
            body = re.sub(r'public\s+interface', '@Repository\npublic interface', body, count=1)

        return f"""package {self.package_name}.repository;

{imports}

{body}
"""

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
        if class_name and class_name.lower().endswith('service'):
            base = class_name[:-7]
            return base if base else None
        if filename.lower().endswith('service.java'):
            base = filename[:-12]
            return self._to_camel_case(base) if base else None
        stem = filename.replace('.java', '')
        return self._to_camel_case(stem) if stem else None

    def _is_entity_candidate_name(self, candidate: str) -> bool:
        blocked_suffixes = ('Exception', 'Result', 'Response', 'Request', 'DTO', 'Config', 'Controller', 'Service')
        blocked_names = {'BusinessException', 'IllegalArgumentException', 'ProcessOrderResult', 'TABLE'}
        return bool(candidate) and candidate not in blocked_names and not candidate.endswith(blocked_suffixes)

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
        controllers = {}
        for filename, code in services.items():
            service_name = filename.replace('.java', '')
            if service_name.endswith('Service'):
                controller_name = service_name[:-7] + 'Controller.java'
            else:
                controller_name = service_name + 'Controller.java'
            controller_content = self._generate_controller(service_name, code)
            if not controller_content:
                continue
            controllers[controller_name] = self._normalize_controller_code(controller_name, controller_content)

        controller_dir = self.package_path / 'controller'
        for filename, code in controllers.items():
            file_path = controller_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

        logger.info(f"Generated {len(controllers)} controller classes")
        return controllers

    def generate_entities(self, java_code: Dict[str, str], ddl_columns: Optional[Dict[str, List[Dict[str, str]]]] = None) -> Dict[str, str]:
        entities = {}
        ddl_columns = ddl_columns or {}
        ddl_map = {table.replace("_", "").lower(): table for table in ddl_columns.keys()}
        self._ddl_table_map = ddl_map

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
            entities[target_filename] = self._generate_entity_from_ddl(normalized_entity_name, table_name, columns)

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


def create_spring_boot_generator(config: Dict[str, Any]) -> SpringBootGenerator:
    return SpringBootGenerator(config)