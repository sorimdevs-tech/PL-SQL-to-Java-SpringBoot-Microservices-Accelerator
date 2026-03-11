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
from pathlib import Path
from typing import Optional, Dict, Any

# Import platform components
from src.utils.logger import setup_logging
from src.utils.config import load_config
from src.parser.plsql_parser import PLSQLParser
from src.analyzer.dependency_graph import DependencyAnalyzer
from src.converter.llm_engine import LLMConversionEngine
from src.generator.spring_boot_generator import SpringBootGenerator
from src.validator.test_generator import TestGenerator
from src.utils.file_utils import FileExtractor
from src.advanced.optimization_engine import create_optimization_engine
from src.advanced.advanced_features import create_advanced_features

# Configure logging
logger = logging.getLogger(__name__)


class PLSQLModernizationPipeline:
    """Main pipeline for PL/SQL to Java conversion"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the modernization pipeline
        
        Args:
            config_path (str): Path to configuration file
        """
        loaded_config = load_config(config_path)
        # Normalize to dict for downstream components that use mapping-style access.
        self.config = (
            loaded_config.model_dump()
            if hasattr(loaded_config, "model_dump")
            else loaded_config.dict()
        )
        self.parser = PLSQLParser()
        self.dependency_analyzer = DependencyAnalyzer()
        llm_config = dict(self.config.get('llm', {}))
        llm_config['output'] = self.config.get('output', {})
        self.llm_engine = LLMConversionEngine(llm_config)
        self.generator = SpringBootGenerator(self.config.get('output', {}))
        self.test_generator = TestGenerator()
        self.file_extractor = FileExtractor()
        
        # Setup output directories
        self.setup_output_directories()
    
    def setup_output_directories(self):
        """Create necessary output directories"""
        output_dir = Path(self.config.get('output', {}).get('target_directory', 'C:/Users/THIS PC/Documents/output'))
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        # (output_dir / 'java').mkdir(parents=True, exist_ok=True)
        # (output_dir / 'resources').mkdir(parents=True, exist_ok=True)
        (output_dir / 'reports').mkdir(parents=True, exist_ok=True)
        # (output_dir / 'tests').mkdir(parents=True, exist_ok=True)
    
    async def run_pipeline(self, source_path: str, source_type: str = "file"):
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
            entities = await self.generate_entities(java_code)
            
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
            
            # Generate migration report
            logger.info("Generating migration report...")
            await self.generate_migration_report(
                plsql_files, ast_results, dependency_graph, 
                project_structure, entities, repositories, services, controllers, test_results
            )
            
            logger.info("Pipeline completed successfully!")
            
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
    
    async def generate_entities(self, java_code: Dict[str, str]) -> Dict[str, str]:
        """
        Generate JPA entity classes
        
        Args:
            java_code (Dict[str, str]): Generated Java code
            
        Returns:
            Dict[str, str]: Generated entity files
        """
        return self.generator.generate_entities(java_code)
    
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
    
    async def generate_migration_report(self, plsql_files: Dict[str, str],
                                      ast_results: Dict[str, Any],
                                      dependency_graph: Dict[str, Any],
                                      project_structure: Dict[str, Any],
                                      entities: Dict[str, str],
                                      repositories: Dict[str, str],
                                      services: Dict[str, str],
                                      controllers: Dict[str, str],
                                      test_results: Dict[str, Any]):
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
            "validation_passed": test_results.get('validation_passed', False)
        }
        
        # Save report to file
        output_dir = Path(self.config.get('output', {}).get('target_directory', './output'))
        report_file = output_dir / 'reports' / 'migration_report.json'
        
        import json
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Migration report saved to: {report_file}")
        logger.info(f"Migration Summary: {report}")


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
