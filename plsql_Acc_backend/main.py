#!/usr/bin/env python3
"""
PL/SQL → Java Modernization Platform
Main entry point for the conversion pipeline
"""

import os
import sys
import logging
import argparse
import asyncio
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

# Import platform components
from src.utils.logger import setup_logging
from src.utils.config import load_config
from src.parser.plsql_parser import PLSQLParser
from src.analyzer.dependency_graph import DependencyAnalyzer
from src.converter.llm_engine import LLMConversionEngine
from src.generator.spring_boot_generator import SpringBootGenerator
from src.validator.test_generator import TestGenerator
from src.validator.semantic_validator import SemanticValidator, SemanticValidationReport
from src.utils.file_utils import FileExtractor
from src.parser.sql_table_discovery import extract_create_table_columns
from src.parser.discovery_analyzer import build_conversion_units, build_discovery_model
from src.advanced.optimization_engine import create_optimization_engine
from src.advanced.advanced_features import create_advanced_features

# Configure logging
logger = logging.getLogger(__name__)


class ConversionError(RuntimeError):
    """Raised when deterministic semantic validation cannot be satisfied."""

    def __init__(self, errors: List[str]):
        self.errors = list(errors or [])
        detail = "; ".join(self.errors[:12]) if self.errors else "unknown conversion error"
        super().__init__(f"Conversion failed: {detail}")


class PLSQLModernizationPipeline:
    """Main pipeline for PL/SQL to Java conversion"""
    
    def __init__(
        self,
        config_path: str = "config.json",
        output_directory: Optional[str] = None,
        config_overrides: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the modernization pipeline
        
        Args:
            config_path (str): Path to configuration file
            output_directory (Optional[str]): Override target output directory
        """
        loaded_config = load_config(config_path)
        # Normalize to dict for downstream components that use mapping-style access.
        self.config = (
            loaded_config.model_dump()
            if hasattr(loaded_config, "model_dump")
            else loaded_config.dict()
        )
        if config_overrides:
            self._merge_config(self.config, config_overrides)
        self.config_path = config_path
        if output_directory:
            self.config.setdefault('output', {})
            self.config['output']['target_directory'] = str(Path(output_directory))
        self.output_directory = Path(
            self.config.get('output', {}).get('target_directory', 'C:/Users/THIS PC/Documents/output')
        )
        self.parser = PLSQLParser()
        self.dependency_analyzer = DependencyAnalyzer()
        llm_config = dict(self.config.get('llm', {}))
        llm_config['output'] = self.config.get('output', {})
        self.llm_engine = LLMConversionEngine(llm_config)
        self.generator = SpringBootGenerator(self.config.get('output', {}))
        self.test_generator = TestGenerator()
        self.semantic_validator = SemanticValidator(
            self.config.get('output', {}).get('package_name', 'com.company.project')
        )
        self.file_extractor = FileExtractor()
        self.repair_config = self.config.get('backup_llm', {}) or {}
        self._last_repair_result: Dict[str, Any] = {}
        
        # Setup output directories
        self.setup_output_directories()

    def _merge_config(self, base: Dict[str, Any], overrides: Dict[str, Any]) -> None:
        """Recursively merge override values into the loaded config dict."""
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def setup_output_directories(self):
        """Create necessary output directories"""
        self.output_directory.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        # (output_dir / 'java').mkdir(parents=True, exist_ok=True)
        # (output_dir / 'resources').mkdir(parents=True, exist_ok=True)
        (self.output_directory / 'reports').mkdir(parents=True, exist_ok=True)
        # (output_dir / 'tests').mkdir(parents=True, exist_ok=True)
    
    async def run_pipeline(self, source_path: str, source_type: str = "file") -> Dict[str, Any]:
        """
        Execute the complete modernization pipeline
        
        Args:
            source_path (str): Path to source file/directory/repository
            source_type (str): Type of source (file, git, database)
        """
        logger.info(f"Starting PL/SQL modernization pipeline for {source_type}: {source_path}")
        
        try:
            # Stage 1: Extract PL/SQL code
            logger.info("Stage 1: Extracting PL/SQL code...")
            plsql_files = await self.extract_plsql_code(source_path, source_type)
            
            # Stage 2: Extract raw PL/SQL semantics and full object bodies
            logger.info("Stage 2: Extracting SQL semantics from raw PL/SQL...")
            semantic_model = await self.extract_conversion_semantics(plsql_files)

            # Diagnostic parse only. AST is no longer the LLM source of truth.
            logger.info("Stage 2a: Parsing PL/SQL for diagnostics...")
            ast_results = await self.parse_plsql_code(plsql_files)
            dependency_graph = self.build_dependency_summary(semantic_model)

            # Stage 3: Generate entities from extracted columns
            logger.info("Stage 3: Generating JPA entities...")
            entities = await self.generate_entities({}, plsql_files, semantic_model)

            # Stage 4-6: Deterministic generation with strict 3-pass validation loop.
            repositories: Dict[str, str] = {}
            services: Dict[str, str] = {}
            semantic_validation = SemanticValidationReport(passed=False, issues=[])
            repository_feedback: Dict[str, List[str]] = {}
            service_feedback: Dict[str, List[str]] = {}
            for attempt in range(3):
                logger.info("Stage 4: Generating deterministic repositories (attempt %s/3)...", attempt + 1)
                repositories = await self.generate_repositories(
                    semantic_model,
                    entities,
                    repository_feedback,
                )

                logger.info("Stage 5: Generating constrained services (attempt %s/3)...", attempt + 1)
                services = await self.generate_services(
                    semantic_model,
                    entities,
                    repositories,
                    service_feedback,
                )

                logger.info("Stage 6: Running semantic validation (attempt %s/3)...", attempt + 1)
                semantic_validation = await self.validate_semantics(
                    semantic_model,
                    entities,
                    repositories,
                    services,
                )
                if semantic_validation.passed:
                    break
                repository_feedback = semantic_validation.feedback_by_component("repository")
                service_feedback = semantic_validation.feedback_by_component("service")
                logger.warning(
                    "Semantic validation failed on attempt %s/3: %s",
                    attempt + 1,
                    "; ".join(issue.message for issue in semantic_validation.issues[:5]),
                )
            if not semantic_validation.passed:
                raise ConversionError([issue.message for issue in semantic_validation.issues])

            controllers = await self.generate_controllers(services, write_files=False)
            final_java_code = {}
            final_java_code.update(entities)
            final_java_code.update(repositories)
            final_java_code.update(services)
            final_java_code.update(controllers)

            # Stage 7: Write validated files to the Spring Boot project
            logger.info("Stage 7: Writing validated Spring Boot project...")
            project_structure = await self.generate_spring_boot_project(
                final_java_code,
                auto_generate_controllers=False,
            )
            
            # Stage 8: Generate tests and validate
            logger.info("Stage 8: Generating tests and validation...")
            test_results = await self.generate_tests_and_validate(
                entities, repositories, services, controllers
            )
            test_results["semantic_validation"] = semantic_validation.to_dict()
            test_results["validation_passed"] = bool(
                test_results.get("validation_passed", False) and semantic_validation.passed
            )

            # Stage 9: Build validation and backup-LLM repair
            logger.info("Stage 9: Validating generated project build...")
            repair_results = await self.repair_generated_project_if_needed(project_structure)
            
            # Generate migration report
            logger.info("Generating migration report...")
            await self.generate_migration_report(
                plsql_files, ast_results, dependency_graph, 
                project_structure, entities, repositories, services, controllers, test_results, repair_results
            )
            
            logger.info("Pipeline completed successfully!")
            return self._build_pipeline_result(
                source_path=source_path,
                source_type=source_type,
                plsql_files=plsql_files,
                ast_results=ast_results,
                dependency_graph=dependency_graph,
                project_structure=project_structure,
                entities=entities,
                repositories=repositories,
                services=services,
                controllers=controllers,
                test_results=test_results,
                repair_results=repair_results,
            )
            
        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
            raise
    
    async def extract_plsql_code(self, source_path: str, source_type: str) -> Dict[str, str]:
        """
        Extract PL/SQL code from various sources
        
        Args:
            source_path (str): Path to source
            source_type (str): Type of source (file, git, database)
            
        Returns:
            Dict[str, str]: Dictionary of file names and content
        """
        if source_type == "file":
            return self.file_extractor.extract_from_file(source_path)
        elif source_type == "git":
            return await self.file_extractor.extract_from_git(source_path)
        elif source_type == "database":
            return await self.file_extractor.extract_from_database(source_path)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")
    
    async def parse_plsql_code(self, plsql_files: Dict[str, str]) -> Dict[str, Any]:
        """
        Parse PL/SQL files and generate AST
        
        Args:
            plsql_files (Dict[str, str]): Dictionary of file names and content
            
        Returns:
            Dict[str, Any]: Parsed AST results
        """
        ast_results = {}
        
        for filename, content in plsql_files.items():
            logger.debug(f"Parsing file: {filename}")
            try:
                ast = self.parser.parse(content)
                ast_results[filename] = ast
            except Exception as e:
                logger.warning(f"Failed to parse {filename}: {str(e)}")
                continue
        
        return ast_results

    async def extract_conversion_semantics(self, plsql_files: Dict[str, str]) -> Dict[str, Any]:
        """Build raw-object conversion units and merged schema semantics."""
        units: List[Dict[str, Any]] = []
        merged_schema = {
            "tables": [],
            "relationships": [],
            "sequences": [],
            "sequence_mapping": [],
        }
        table_index: Dict[str, Dict[str, Any]] = {}
        relationship_keys: set[tuple[str, str, str, str]] = set()
        sequence_names: set[str] = set()
        sequence_mapping_keys: set[tuple[str, str]] = set()

        for filename, content in (plsql_files or {}).items():
            model = build_discovery_model(content)
            file_units = build_conversion_units(content)
            for unit in file_units:
                unit["source_file"] = filename
            units.extend(file_units)

            for table in model.get("schema", {}).get("tables", []):
                table_name = str(table.get("name", "")).upper()
                if not table_name:
                    continue
                existing = table_index.get(table_name)
                if not existing:
                    table_index[table_name] = {
                        "name": table_name,
                        "columns": list(table.get("columns", [])),
                        "primary_keys": list(table.get("primary_keys", [])),
                        "foreign_keys": list(table.get("foreign_keys", [])),
                        "source": table.get("source", "ddl"),
                    }
                    continue

                existing_columns = {
                    str(column.get("name", "")).upper(): column
                    for column in existing.get("columns", [])
                    if column.get("name")
                }
                for column in table.get("columns", []):
                    column_name = str(column.get("name", "")).upper()
                    if column_name and column_name not in existing_columns:
                        existing["columns"].append(column)
                existing["primary_keys"] = sorted(
                    {*(existing.get("primary_keys", []) or []), *(table.get("primary_keys", []) or [])}
                )
                existing["foreign_keys"] = list({
                    (
                        fk.get("source_column", ""),
                        fk.get("target_table", ""),
                        fk.get("target_column", ""),
                    ): fk
                    for fk in [*(existing.get("foreign_keys", []) or []), *(table.get("foreign_keys", []) or [])]
                }.values())

            for relationship in model.get("schema", {}).get("relationships", []):
                key = (
                    str(relationship.get("source_table", "")).upper(),
                    str(relationship.get("source_column", "")).upper(),
                    str(relationship.get("target_table", "")).upper(),
                    str(relationship.get("target_column", "")).upper(),
                )
                if key in relationship_keys:
                    continue
                relationship_keys.add(key)
                merged_schema["relationships"].append(relationship)

            for sequence in model.get("schema", {}).get("sequences", []):
                sequence_name = str(sequence.get("name", "")).upper()
                if not sequence_name or sequence_name in sequence_names:
                    continue
                sequence_names.add(sequence_name)
                merged_schema["sequences"].append(sequence)

            for mapping in model.get("schema", {}).get("sequence_mapping", []):
                key = (
                    str(mapping.get("sequence_name", "")).upper(),
                    str(mapping.get("mapped_table", "")).upper(),
                )
                if key in sequence_mapping_keys:
                    continue
                sequence_mapping_keys.add(key)
                merged_schema["sequence_mapping"].append(mapping)

        merged_schema["tables"] = sorted(table_index.values(), key=lambda item: item.get("name", ""))
        sequence_map: Dict[str, str] = {}
        for mapping in merged_schema.get("sequence_mapping", []):
            sequence_name = str(mapping.get("sequence_name", "")).upper()
            mapped_table = str(mapping.get("mapped_table", "")).upper()
            if sequence_name and mapped_table and mapped_table not in sequence_map:
                sequence_map[mapped_table] = sequence_name

        known_tables = {
            str(table.get("name", "")).upper()
            for table in merged_schema.get("tables", [])
            if table.get("name")
        }
        target_tables = {
            str(table_name).upper()
            for unit in units
            for table_name in (unit.get("target_tables") or [])
            if table_name
        }
        mapped_sequences = set(sequence_map.values())
        for sequence in merged_schema.get("sequences", []):
            sequence_name = str(sequence.get("name", "")).upper()
            if not sequence_name or sequence_name in mapped_sequences:
                continue
            base = re.sub(r"_SEQ$", "", sequence_name, flags=re.IGNORECASE)
            if not base:
                continue
            candidates = [
                table_name
                for table_name in known_tables
                if table_name == base
                or table_name.endswith(f"_{base}")
                or base in table_name
            ]
            if len(candidates) > 1:
                preferred = [table for table in candidates if table in target_tables]
                if len(preferred) == 1:
                    candidates = preferred
            if len(candidates) == 1:
                table_name = candidates[0]
                if table_name not in sequence_map:
                    sequence_map[table_name] = sequence_name

        return {
            "source_units": units,
            "schema": merged_schema,
            "sequences": sequence_map,
        }

    def build_dependency_summary(self, semantic_model: Dict[str, Any]) -> Dict[str, Any]:
        tables = sorted(
            {
                str(table.get("name", "")).upper()
                for table in semantic_model.get("schema", {}).get("tables", [])
                if table.get("name")
            }
        )
        operations_by_table: Dict[str, List[str]] = {}
        lookup_keys_by_table: Dict[str, List[str]] = {}
        for unit in semantic_model.get("source_units", []):
            for table_name, operations in (unit.get("operations_by_table") or {}).items():
                operations_by_table.setdefault(table_name, [])
                operations_by_table[table_name] = sorted(
                    {*(operations_by_table[table_name]), *(operations or [])}
                )
            for table_name, columns in (unit.get("lookup_keys") or {}).items():
                lookup_keys_by_table.setdefault(table_name, [])
                lookup_keys_by_table[table_name] = sorted(
                    {*(lookup_keys_by_table[table_name]), *(columns or [])}
                )
        return {
            "tables": tables,
            "operations_by_table": operations_by_table,
            "lookup_keys_by_table": lookup_keys_by_table,
        }

    async def validate_semantics(
        self,
        semantic_model: Dict[str, Any],
        entities: Dict[str, str],
        repositories: Dict[str, str],
        services: Dict[str, str],
    ) -> SemanticValidationReport:
        return self.semantic_validator.validate(
            semantic_model.get("source_units", []),
            entities,
            repositories,
            services,
        )
    
    async def analyze_dependencies(self, ast_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze dependencies between PL/SQL components
        
        Args:
            ast_results (Dict[str, Any]): Parsed AST results
            
        Returns:
            Dict[str, Any]: Dependency graph and analysis
        """
        return self.dependency_analyzer.analyze(ast_results)
    
    async def convert_to_java(self, ast_results: Dict[str, Any], 
                            dependency_graph: Dict[str, Any]) -> Dict[str, str]:
        """
        Convert PL/SQL AST to Java code using LLM
        
        Args:
            ast_results (Dict[str, Any]): Parsed AST results
            dependency_graph (Dict[str, Any]): Dependency analysis
            
        Returns:
            Dict[str, str]: Generated Java code files
        """
        merged_ast = self._merge_ast_results(ast_results)

        # LCE-FIX: If the dependency graph produced no tables (which happens when
        # the PL/SQL parser doesn't fully resolve SQL statement table references),
        # enrich the dependency_graph with DDL-extracted table names so that
        # llm_engine._prepare_conversion_context() can build correct entity_names
        # and repository_names for the LLM prompt.
        if not dependency_graph.get('tables'):
            # Re-extract table names from the raw PL/SQL source stored in plsql_files
            # (available via self._last_plsql_files set in run_pipeline)
            ddl_tables = getattr(self, '_last_ddl_tables', [])
            if ddl_tables:
                dependency_graph = dict(dependency_graph)
                dependency_graph['tables'] = ddl_tables
                logger.info(f"LCE-FIX: enriched dependency_graph with {len(ddl_tables)} DDL tables: {ddl_tables}")

        return await self.llm_engine.convert(merged_ast, dependency_graph)

    def _merge_ast_results(self, ast_results: Dict[str, Any]) -> Dict[str, Any]:
        """Merge file-level AST results into a single AST for conversion."""
        merged = {
            'type': 'plsql_file',
            'procedures': [],
            'functions': [],
            'triggers': [],
            'packages': [],
            'declarations': [],
            'executables': [],
            'exceptions': []
        }
        
        for ast in ast_results.values():
            if not isinstance(ast, dict):
                continue
            merged['procedures'].extend(ast.get('procedures', []))
            merged['functions'].extend(ast.get('functions', []))
            merged['triggers'].extend(ast.get('triggers', []))
            merged['packages'].extend(ast.get('packages', []))
            merged['declarations'].extend(ast.get('declarations', []))
            merged['executables'].extend(ast.get('executables', []))
            merged['exceptions'].extend(ast.get('exceptions', []))
        
        return merged
    
    async def generate_spring_boot_project(
        self,
        java_code: Dict[str, str],
        auto_generate_controllers: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate complete Spring Boot project structure
        
        Args:
            java_code (Dict[str, str]): Generated Java code
            
        Returns:
            Dict[str, Any]: Project structure information
        """
        return await self.generator.generate_project(
            java_code,
            auto_generate_controllers=auto_generate_controllers,
        )
    
    async def generate_entities(
        self,
        java_code: Dict[str, str],
        plsql_files: Dict[str, str],
        semantic_model: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Generate JPA entity classes
        
        Args:
            java_code (Dict[str, str]): Generated Java code
            plsql_files (Dict[str, str]): Original PL/SQL source files
            
        Returns:
            Dict[str, str]: Generated entity files
        """
        ddl_columns: Dict[str, List[Dict[str, str]]] = {}
        fk_map: Dict[str, List[Dict[str, str]]] = {}

        if semantic_model:
            for table in semantic_model.get("schema", {}).get("tables", []):
                table_name = table.get("name")
                if not table_name:
                    continue
                ddl_columns[str(table_name).upper()] = list(table.get("columns", []))
                for fk in table.get("foreign_keys", []) or []:
                    fk_map.setdefault(str(table_name).upper(), []).append(
                        {
                            "column": fk.get("source_column", ""),
                            "ref_table": fk.get("target_table", ""),
                            "ref_column": fk.get("target_column", ""),
                        }
                    )
        else:
            for content in (plsql_files or {}).values():
                try:
                    ddl_columns.update(extract_create_table_columns(content))
                except Exception:
                    continue
            for content in (plsql_files or {}).values():
                try:
                    fk_map.update(SpringBootGenerator.parse_fk_constraints(content))
                except Exception:
                    continue

        return self.generator.generate_entities(
            java_code,
            ddl_columns,
            fk_map,
            sequence_map=(semantic_model or {}).get("sequences", {}),
            write_files=False,
        )
    
    async def generate_repositories(
        self,
        semantic_model: Dict[str, Any],
        entities: Dict[str, str],
        validation_feedback: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, str]:
        """
        Generate JPA repository interfaces
        
        Args:
            entities (Dict[str, str]): Generated entity files
            
        Returns:
            Dict[str, str]: Generated repository files
        """
        return await self.llm_engine.generate_repositories_from_semantics(
            semantic_model.get("source_units", []),
            entities,
            validation_feedback=validation_feedback,
        )
    
    async def generate_services(
        self,
        semantic_model: Dict[str, Any],
        entities: Dict[str, str],
        repositories: Dict[str, str],
        validation_feedback: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, str]:
        """
        Generate service layer classes
        
        Args:
            java_code (Dict[str, str]): Generated Java code
            
        Returns:
            Dict[str, str]: Generated service files
        """
        return await self.llm_engine.generate_services_from_semantics(
            semantic_model.get("source_units", []),
            entities,
            repositories,
            validation_feedback=validation_feedback,
        )
    
    async def generate_controllers(self, services: Dict[str, str], write_files: bool = True) -> Dict[str, str]:
        """
        Generate REST controller classes
        
        Args:
            services (Dict[str, str]): Generated service files
            
        Returns:
            Dict[str, str]: Generated controller files
        """
        return self.generator.generate_controllers(services, write_files=write_files)
    
    async def generate_tests_and_validate(self, entities: Dict[str, str], 
                                        repositories: Dict[str, str],
                                        services: Dict[str, str],
                                        controllers: Dict[str, str]) -> Dict[str, Any]:
        """
        Generate unit tests and perform validation
        
        Args:
            entities (Dict[str, str]): Generated entity files
            repositories (Dict[str, str]): Generated repository files
            services (Dict[str, str]): Generated service files
            controllers (Dict[str, str]): Generated controller files
            
        Returns:
            Dict[str, Any]: Test results and validation information
        """
        # return await self.test_generator.generate_and_validate(
        #     entities, repositories, services, controllers
        # )
         # Temporarily disabled per product decision:
        # do not generate/write test sources as part of conversion output.
        logger.info("Test generation is disabled; skipping Stage 8 test file creation.")
        return {
            'total_tests': 0,
            'unit_tests': [],
            'integration_tests': [],
            'validation_results': [],
            'sql_validation_results': [],
            'test_report': '# Test generation disabled\n',
            'validation_passed': True,
        }

    async def repair_generated_project_if_needed(self, project_structure: Dict[str, Any]) -> Dict[str, Any]:
        project_root = self.output_directory
        initial_build = await self._run_generated_project_build(project_root)
        if initial_build.get('success'):
            self._last_repair_result = {
                'enabled': bool(self.repair_config.get('enabled')),
                'attempted': False,
                'build_passed': True,
                'iterations': [],
                'final_build': initial_build,
            }
            return self._last_repair_result

        if not self.repair_config.get('enabled'):
            self._last_repair_result = {
                'enabled': False,
                'attempted': False,
                'build_passed': False,
                'iterations': [],
                'final_build': initial_build,
                'reason': 'backup_llm_disabled',
            }
            return self._last_repair_result

        max_loops = max(1, int(self.repair_config.get('max_repair_loops', 2)))
        max_files = max(1, int(self.repair_config.get('max_files_per_attempt', 8)))
        iterations: List[Dict[str, Any]] = []
        current_build = initial_build

        for attempt in range(1, max_loops + 1):
            context = self._build_repair_context(
                project_root=project_root,
                project_structure=project_structure,
                build_result=current_build,
                max_files=max_files,
            )
            repair_payload = await self.llm_engine.repair_generated_project(context)
            changed_files = self._apply_repair_files(project_root, repair_payload.get('files', []))
            build_after = await self._run_generated_project_build(project_root)
            iteration = {
                'attempt': attempt,
                'summary': repair_payload.get('summary', ''),
                'files_changed': changed_files,
                'build_passed': build_after.get('success', False),
                'build_command': build_after.get('command'),
            }
            iterations.append(iteration)
            current_build = build_after
            if build_after.get('success'):
                break
            if not changed_files:
                break

        self._last_repair_result = {
            'enabled': True,
            'attempted': True,
            'build_passed': current_build.get('success', False),
            'iterations': iterations,
            'final_build': current_build,
        }
        self._write_repair_report(self._last_repair_result)
        return self._last_repair_result

    async def _run_generated_project_build(self, project_root: Path) -> Dict[str, Any]:
        command = self._resolve_build_command(project_root)
        if not command:
            return {
                'success': False,
                'command': None,
                'stdout': '',
                'stderr': 'No supported build command found for generated project',
                'combined_output': 'No supported build command found for generated project',
                'error_files': [],
            }

        pre_stdout = ""
        pre_stderr = ""
        if command[0] == "./gradlew":
            chmod_result = subprocess.run(
                ["chmod", "+x", "gradlew"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
            )
            pre_stdout = chmod_result.stdout or ""
            pre_stderr = chmod_result.stderr or ""

        result = subprocess.run(
            command,
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )
        stdout = f"{pre_stdout}{result.stdout or ''}"
        stderr = f"{pre_stderr}{result.stderr or ''}"
        combined_output = (stdout + "\n" + stderr).strip()
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'command': " ".join(command),
            'stdout': stdout,
            'stderr': stderr,
            'combined_output': combined_output[-20000:],
            'error_files': self._extract_build_error_files(combined_output, project_root),
        }

    def _resolve_build_command(self, project_root: Path) -> List[str]:
        gradlew_unix = project_root / 'gradlew'
        gradlew = project_root / 'gradlew.bat'
        gradle = project_root / 'build.gradle'
        mvnw = project_root / 'mvnw.cmd'
        pom = project_root / 'pom.xml'

        if gradlew_unix.exists():
            return ['./gradlew', 'compileJava']
        if gradlew.exists():
            return [str(gradlew), 'compileJava']
        if gradle.exists():
            gradle_cmd = shutil.which('gradle')
            if gradle_cmd:
                return [gradle_cmd, 'compileJava']
        if mvnw.exists():
            return [str(mvnw), '-DskipTests', 'compile']
        if pom.exists():
            mvn_cmd = shutil.which('mvn')
            if mvn_cmd:
                return [mvn_cmd, '-DskipTests', 'compile']
        return []

    def _extract_build_error_files(self, output: str, project_root: Path) -> List[str]:
        if not output:
            return []
        matches = set()
        normalized_root = str(project_root).replace('\\', '/')
        patterns = [
            r'([A-Za-z]:[\\/][^\r\n:]*?\.java)',
            r'((?:src[\\/][^\r\n:]+?\.java))',
            r'((?:src[\\/][^\r\n:]+?\.xml))',
            r'((?:src[\\/][^\r\n:]+?\.properties))',
            r'((?:src[\\/][^\r\n:]+?\.yml))',
        ]
        for pattern in patterns:
            for match in re.findall(pattern, output):
                path = str(match).replace('\\', '/')
                if re.match(r'^[A-Za-z]:/', path):
                    try:
                        path = str(Path(path).resolve()).replace('\\', '/')
                        if path.startswith(normalized_root):
                            path = path[len(normalized_root):].lstrip('/')
                    except Exception:
                        continue
                matches.add(path)
        return sorted(matches)

    def _build_repair_context(
        self,
        project_root: Path,
        project_structure: Dict[str, Any],
        build_result: Dict[str, Any],
        max_files: int,
    ) -> Dict[str, Any]:
        file_paths = build_result.get('error_files') or []
        if not file_paths:
            file_paths = self._collect_project_source_files(project_root)[:max_files]
        else:
            file_paths = file_paths[:max_files]

        files = []
        for rel_path in file_paths:
            abs_path = project_root / rel_path
            if abs_path.exists() and abs_path.is_file():
                try:
                    files.append({
                        'path': rel_path.replace('\\', '/'),
                        'content': abs_path.read_text(encoding='utf-8', errors='replace')
                    })
                except Exception:
                    continue

        config_files = []
        for rel_path in ('pom.xml', 'build.gradle', 'settings.gradle', 'src/main/resources/application.properties', 'src/main/resources/application.yml'):
            abs_path = project_root / rel_path
            if abs_path.exists() and abs_path.is_file():
                config_files.append({
                    'path': rel_path,
                    'content': abs_path.read_text(encoding='utf-8', errors='replace')
                })

        return {
            'project_name': self.config.get('output', {}).get('project_name', 'converted-app'),
            'package_name': self.config.get('output', {}).get('package_name', 'com.company.project'),
            'build_command': build_result.get('command'),
            'build_output': build_result.get('combined_output', ''),
            'project_summary': project_structure.get('project_structure', {}),
            'failing_files': files,
            'config_files': config_files,
        }

    def _collect_project_source_files(self, project_root: Path) -> List[str]:
        candidates = []
        for path in sorted((project_root / 'src').rglob('*')):
            if path.is_file() and path.suffix.lower() in {'.java', '.xml', '.properties', '.yml'}:
                candidates.append(str(path.relative_to(project_root)).replace('\\', '/'))
        return candidates

    def _enforce_repair_java_imports(self, rel_path: str, content: str) -> str:
        """Apply compile-focused import guardrails to repaired Java files."""
        if not isinstance(rel_path, str) or not rel_path.lower().endswith('.java'):
            return content

        normalized_path = rel_path.replace('\\', '/').lower()
        filename = normalized_path.rsplit('/', 1)[-1]
        looks_like_service = '/service/' in normalized_path or filename.endswith('service.java')
        if not looks_like_service:
            return content

        required_imports: List[str] = []

        # Only add imports when the simple type name is actually used.
        uses_bare_optional = bool(re.search(r'(?<![\w.])Optional\s*(?:<|\.|\()', content))
        has_optional_import = bool(re.search(r'(?m)^\s*import\s+java\.util\.Optional\s*;\s*$', content))
        if uses_bare_optional and not has_optional_import:
            required_imports.append('import java.util.Optional;')

        uses_transaction_template = bool(re.search(r'(?<![\w.])TransactionTemplate\b', content))
        has_transaction_template_import = bool(
            re.search(
                r'(?m)^\s*import\s+org\.springframework\.transaction\.support\.TransactionTemplate\s*;\s*$',
                content,
            )
        )
        if uses_transaction_template and not has_transaction_template_import:
            required_imports.append('import org.springframework.transaction.support.TransactionTemplate;')

        uses_platform_transaction_manager = bool(
            re.search(r'(?<![\w.])PlatformTransactionManager\b', content)
        )
        has_platform_transaction_manager_import = bool(
            re.search(
                r'(?m)^\s*import\s+org\.springframework\.transaction\.PlatformTransactionManager\s*;\s*$',
                content,
            )
        )
        if uses_platform_transaction_manager and not has_platform_transaction_manager_import:
            required_imports.append('import org.springframework.transaction.PlatformTransactionManager;')

        if not required_imports:
            return content

        lines = content.splitlines()
        package_idx = next((i for i, line in enumerate(lines) if line.strip().startswith('package ')), None)
        import_indices = [i for i, line in enumerate(lines) if line.strip().startswith('import ')]

        if import_indices:
            insert_idx = import_indices[-1] + 1
            for import_line in required_imports:
                lines.insert(insert_idx, import_line)
                insert_idx += 1
        elif package_idx is not None:
            insert_idx = package_idx + 1
            lines.insert(insert_idx, '')
            for offset, import_line in enumerate(required_imports, start=1):
                lines.insert(insert_idx + offset, import_line)
            after_imports_idx = insert_idx + len(required_imports) + 1
            if after_imports_idx >= len(lines) or lines[after_imports_idx].strip():
                lines.insert(after_imports_idx, '')
        else:
            for offset, import_line in enumerate(required_imports):
                lines.insert(offset, import_line)
            lines.insert(len(required_imports), '')

        normalized = '\n'.join(lines)
        if content.endswith('\n'):
            normalized += '\n'
        return normalized

    def _apply_repair_files(self, project_root: Path, files: List[Dict[str, str]]) -> List[str]:
        changed = []
        for item in files or []:
            rel_path = item.get('path')
            content = item.get('content')
            if not isinstance(rel_path, str) or not isinstance(content, str):
                continue
            target_path = (project_root / rel_path).resolve()
            try:
                target_path.relative_to(project_root.resolve())
            except ValueError:
                logger.warning("Skipping repair write outside project root: %s", rel_path)
                continue
            content = self._enforce_repair_java_imports(rel_path, content)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding='utf-8')
            changed.append(str(target_path.relative_to(project_root)).replace('\\', '/'))
        return changed

    def _write_repair_report(self, repair_results: Dict[str, Any]) -> None:
        try:
            report_file = self.output_directory / 'reports' / 'repair_report.json'
            report_file.parent.mkdir(parents=True, exist_ok=True)
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(repair_results, f, indent=2)
        except Exception as exc:
            logger.warning("Failed to write repair report: %s", exc)
    
    async def generate_migration_report(self, plsql_files: Dict[str, str],
                                      ast_results: Dict[str, Any],
                                      dependency_graph: Dict[str, Any],
                                      project_structure: Dict[str, Any],
                                      entities: Dict[str, str],
                                      repositories: Dict[str, str],
                                      services: Dict[str, str],
                                      controllers: Dict[str, str],
                                      test_results: Dict[str, Any],
                                      repair_results: Optional[Dict[str, Any]] = None):
        """
        Generate comprehensive migration report
        
        Args:
            plsql_files (Dict[str, str]): Original PL/SQL files
            ast_results (Dict[str, Any]): Parsed AST results
            dependency_graph (Dict[str, Any]): Dependency analysis
            project_structure (Dict[str, Any]): Generated project structure
            entities (Dict[str, str]): Generated entity files
            repositories (Dict[str, str]): Generated repository files
            services (Dict[str, str]): Generated service files
            controllers (Dict[str, str]): Generated controller files
            test_results (Dict[str, Any]): Test and validation results
        """
        unit_tests = test_results.get('unit_tests', []) if isinstance(test_results, dict) else []
        integration_tests = test_results.get('integration_tests', []) if isinstance(test_results, dict) else []
        report = {
            "total_procedures": sum(len(f.get('procedures', [])) for f in ast_results.values()),
            "total_functions": sum(len(f.get('functions', [])) for f in ast_results.values()),
            "total_triggers": sum(len(f.get('triggers', [])) for f in ast_results.values()),
            "total_packages": sum(len(f.get('packages', [])) for f in ast_results.values()),
            "tables_detected": len(dependency_graph.get('tables', [])),
            "java_files_generated": len(project_structure.get('java_files', [])),
            "entities_generated": len(entities),
            "repositories_generated": len(repositories),
            "services_generated": len(services),
            "controllers_generated": len(controllers),
            "unit_tests_generated": len(unit_tests),
            "integration_tests_generated": len(integration_tests),
            "total_tests_generated": test_results.get('total_tests', 0),
            "validation_passed": test_results.get('validation_passed', False),
            "semantic_validation_passed": bool((test_results.get("semantic_validation") or {}).get("passed")),
            "backup_llm_repair_enabled": bool((repair_results or {}).get('enabled')),
            "backup_llm_repair_attempted": bool((repair_results or {}).get('attempted')),
            "build_validation_passed": bool((repair_results or {}).get('final_build', {}).get('success')),
            "repair_iterations": len((repair_results or {}).get('iterations', [])),
        }
        
        # Save report to file
        output_dir = Path(self.config.get('output', {}).get('target_directory', './output'))
        report_file = output_dir / 'reports' / 'migration_report.json'
        
        import json
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Migration report saved to: {report_file}")
        logger.info(f"Migration Summary: {report}")

    def _build_pipeline_result(
        self,
        source_path: str,
        source_type: str,
        plsql_files: Dict[str, str],
        ast_results: Dict[str, Any],
        dependency_graph: Dict[str, Any],
        project_structure: Dict[str, Any],
        entities: Dict[str, str],
        repositories: Dict[str, str],
        services: Dict[str, str],
        controllers: Dict[str, str],
        test_results: Dict[str, Any],
        repair_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a structured result for CLI callers and API consumers."""
        unit_tests = test_results.get('unit_tests', []) if isinstance(test_results, dict) else []
        integration_tests = test_results.get('integration_tests', []) if isinstance(test_results, dict) else []
        validation_results = test_results.get('validation_results', []) if isinstance(test_results, dict) else []
        output_files = self._collect_output_files()
        report_path = self.output_directory / 'reports' / 'migration_report.json'
        return {
            'status': 'completed',
            'source_type': source_type,
            'source_path': source_path,
            'output_directory': str(self.output_directory),
            'project_name': self.config.get('output', {}).get('project_name', 'converted-app'),
            'package_name': self.config.get('output', {}).get('package_name', 'com.company.project'),
            'input_files': sorted(plsql_files.keys()),
            'generated_files': output_files,
            'report_path': str(report_path) if report_path.exists() else None,
            'repair_report_path': str(self.output_directory / 'reports' / 'repair_report.json') if (self.output_directory / 'reports' / 'repair_report.json').exists() else None,
            'summary': {
                'plsql_files': len(plsql_files),
                'procedures': sum(len(f.get('procedures', [])) for f in ast_results.values()),
                'functions': sum(len(f.get('functions', [])) for f in ast_results.values()),
                'triggers': sum(len(f.get('triggers', [])) for f in ast_results.values()),
                'packages': sum(len(f.get('packages', [])) for f in ast_results.values()),
                'tables_detected': len(dependency_graph.get('tables', [])),
                'java_files_generated': len(project_structure.get('java_files', [])),
                'entities_generated': len(entities),
                'repositories_generated': len(repositories),
                'services_generated': len(services),
                'controllers_generated': len(controllers),
                'unit_tests_generated': len(unit_tests),
                'integration_tests_generated': len(integration_tests),
                'validation_results': len(validation_results),
                'validation_passed': test_results.get('validation_passed', False),
                'semantic_validation_passed': bool((test_results.get("semantic_validation") or {}).get("passed")),
                'build_validation_passed': bool((repair_results or {}).get('final_build', {}).get('success')),
                'repair_iterations': len((repair_results or {}).get('iterations', [])),
            },
            'artifacts': {
                'entities': sorted(entities.keys()),
                'repositories': sorted(repositories.keys()),
                'services': sorted(services.keys()),
                'controllers': sorted(controllers.keys()),
                'unit_tests': [test.test_name for test in unit_tests],
                'integration_tests': [test.test_name for test in integration_tests],
            },
            'repair': repair_results or {},
        }

    def _collect_output_files(self) -> list[Dict[str, Any]]:
        """Return generated files relative to the output directory."""
        if not self.output_directory.exists():
            return []
        files = []
        for path in sorted(self.output_directory.rglob('*')):
            if path.is_file():
                files.append(
                    {
                        'path': str(path.relative_to(self.output_directory)).replace('\\', '/'),
                        'size': path.stat().st_size,
                    }
                )
        return files


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="PL/SQL → Java Modernization Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py input.sql
  python main.py --source-type git --repo-url https://github.com/example/plsql-repo
  python main.py --source-type database --connection-string "oracle://user:pass@host:port/service"
        """
    )
    
    parser.add_argument("source", nargs="?", help="Source file or path")
    parser.add_argument("--source-type", choices=["file", "git", "database"], 
                       default="file", help="Type of source (default: file)")
    parser.add_argument("--repo-url", help="Git repository URL")
    parser.add_argument("--connection-string", help="Database connection string")
    parser.add_argument("--config", default="config.json", help="Configuration file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    
    # Validate arguments
    if args.source_type == "git" and not args.repo_url:
        parser.error("--repo-url is required when --source-type is 'git'")
    elif args.source_type == "database" and not args.connection_string:
        parser.error("--connection-string is required when --source-type is 'database'")
    elif args.source_type == "file" and not args.source:
        parser.error("Source file is required when --source-type is 'file'")
    
    try:
        # Initialize pipeline
        pipeline = PLSQLModernizationPipeline(args.config)
        
        # Determine source path
        if args.source_type == "git":
            source_path = args.repo_url
        elif args.source_type == "database":
            source_path = args.connection_string
        else:
            source_path = args.source
        
        # Run pipeline
        asyncio.run(pipeline.run_pipeline(source_path, args.source_type))
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
