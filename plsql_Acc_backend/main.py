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
from src.utils.file_utils import FileExtractor
from src.parser.sql_table_discovery import extract_create_table_columns
from src.advanced.optimization_engine import create_optimization_engine
from src.advanced.advanced_features import create_advanced_features

# Configure logging
logger = logging.getLogger(__name__)


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
            
            # Stage 2: Parse PL/SQL and generate AST
            logger.info("Stage 2: Parsing PL/SQL code...")
            ast_results = await self.parse_plsql_code(plsql_files)
            
            # Stage 3: Analyze dependencies
            logger.info("Stage 3: Analyzing dependencies...")
            dependency_graph = await self.analyze_dependencies(ast_results)
            
            # Stage 4: Convert to Java using LLM
            logger.info("Stage 4: Converting to Java using LLM...")

            # LCE-FIX: Extract DDL table names NOW (before Stage 4) so convert_to_java
            # can inject them into the LLM context. The dependency graph may not have
            # found any tables if the SQL statement parser couldn't resolve table
            # references in procedure bodies.
            try:
                from src.parser.sql_table_discovery import extract_create_table_columns
                self._last_ddl_tables = []
                for _content in (plsql_files or {}).values():
                    for _tbl in extract_create_table_columns(_content).keys():
                        if _tbl.upper() not in [t.upper() for t in self._last_ddl_tables]:
                            self._last_ddl_tables.append(_tbl.upper())
                if self._last_ddl_tables:
                    logger.info(f"LCE-FIX: found {len(self._last_ddl_tables)} DDL tables for LLM context: {self._last_ddl_tables}")
            except Exception as _e:
                logger.warning(f"LCE-FIX: DDL table extraction failed: {_e}")
                self._last_ddl_tables = []

            java_code = await self.convert_to_java(ast_results, dependency_graph)
            if not java_code:
                raise RuntimeError(
                    "Stage 4 produced zero Java files after retries. "
                    "Check LLM provider connectivity/model access or configure llm.fallback."
                )
            
            # Stage 5: Generate Spring Boot project
            logger.info("Stage 5: Generating Spring Boot project...")
            project_structure = await self.generate_spring_boot_project(java_code)
            
            # Stage 6: Generate entities
            logger.info("Stage 6: Generating JPA entities...")
            entities = await self.generate_entities(java_code, plsql_files)
            
            # Stage 7: Generate repositories
            logger.info("Stage 7: Generating JPA repositories...")
            repositories = await self.generate_repositories(entities)
            
            # Stage 8: Generate services
            logger.info("Stage 8: Generating service layer...")
            services = await self.generate_services(java_code)
            
            # Stage 9: Generate controllers
            logger.info("Stage 9: Generating REST controllers...")
            controllers = await self.generate_controllers(services)
            
            # Stage 10: Generate tests and validate
            logger.info("Stage 10: Generating tests and validation...")
            test_results = await self.generate_tests_and_validate(
                entities, repositories, services, controllers
            )

            # Stage 11: Build validation and backup-LLM repair
            logger.info("Stage 11: Validating generated project build...")
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
    
    async def generate_spring_boot_project(self, java_code: Dict[str, str]) -> Dict[str, Any]:
        """
        Generate complete Spring Boot project structure
        
        Args:
            java_code (Dict[str, str]): Generated Java code
            
        Returns:
            Dict[str, Any]: Project structure information
        """
        return await self.generator.generate_project(java_code)
    
    async def generate_entities(self, java_code: Dict[str, str], plsql_files: Dict[str, str]) -> Dict[str, str]:
        """
        Generate JPA entity classes
        
        Args:
            java_code (Dict[str, str]): Generated Java code
            plsql_files (Dict[str, str]): Original PL/SQL source files
            
        Returns:
            Dict[str, str]: Generated entity files
        """
        ddl_columns: Dict[str, List[Dict[str, str]]] = {}
        for content in (plsql_files or {}).values():
            try:
                ddl_columns.update(extract_create_table_columns(content))
            except Exception:
                continue

        # SBG-20 FIX (Issue 6): parse ALTER TABLE ... FOREIGN KEY constraints
        # so that _generate_entity_from_ddl can emit @ManyToOne/@JoinColumn
        fk_map: Dict[str, List[Dict[str, str]]] = {}
        for content in (plsql_files or {}).values():
            try:
                fk_map.update(SpringBootGenerator.parse_fk_constraints(content))
            except Exception:
                continue

        return self.generator.generate_entities(java_code, ddl_columns, fk_map)
    
    async def generate_repositories(self, entities: Dict[str, str]) -> Dict[str, str]:
        """
        Generate JPA repository interfaces
        
        Args:
            entities (Dict[str, str]): Generated entity files
            
        Returns:
            Dict[str, str]: Generated repository files
        """
        return self.generator.generate_repositories(entities)
    
    async def generate_services(self, java_code: Dict[str, str]) -> Dict[str, str]:
        """
        Generate service layer classes
        
        Args:
            java_code (Dict[str, str]): Generated Java code
            
        Returns:
            Dict[str, str]: Generated service files
        """
        return self.generator.generate_services(java_code)
    
    async def generate_controllers(self, services: Dict[str, str]) -> Dict[str, str]:
        """
        Generate REST controller classes
        
        Args:
            services (Dict[str, str]): Generated service files
            
        Returns:
            Dict[str, str]: Generated controller files
        """
        return self.generator.generate_controllers(services)
    
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
        return await self.test_generator.generate_and_validate(
            entities, repositories, services, controllers
        )

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

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(project_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        stdout = stdout_bytes.decode('utf-8', errors='replace')
        stderr = stderr_bytes.decode('utf-8', errors='replace')
        combined_output = (stdout + "\n" + stderr).strip()
        return {
            'success': process.returncode == 0,
            'returncode': process.returncode,
            'command': " ".join(command),
            'stdout': stdout,
            'stderr': stderr,
            'combined_output': combined_output[-20000:],
            'error_files': self._extract_build_error_files(combined_output, project_root),
        }

    def _resolve_build_command(self, project_root: Path) -> List[str]:
        gradlew = project_root / 'gradlew.bat'
        gradle = project_root / 'build.gradle'
        mvnw = project_root / 'mvnw.cmd'
        pom = project_root / 'pom.xml'

        if gradlew.exists():
            return [str(gradlew), 'build', '-x', 'test']
        if gradle.exists():
            gradle_cmd = shutil.which('gradle')
            if gradle_cmd:
                return [gradle_cmd, 'build', '-x', 'test']
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
