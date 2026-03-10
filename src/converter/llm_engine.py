"""
LLM Conversion Engine for PL/SQL Modernization Platform
Converts PL/SQL AST to Java code using Large Language Models
"""

import os
import json
import asyncio
import time
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
import logging

# Import platform utilities
from ..utils.logger import get_logger
from ..utils.config import get_config_value

logger = get_logger(__name__)


@dataclass
class ConversionRequest:
    """Represents a conversion request"""
    plsql_ast: Dict[str, Any]
    dependency_graph: Dict[str, Any]
    target_language: str = "Java"
    target_framework: str = "Spring Boot"
    package_name: str = "com.company.project"


@dataclass
class ConversionResult:
    """Represents a conversion result"""
    success: bool
    java_code: Optional[str]
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def generate_code(self, prompt: str, max_tokens: int = 4000, 
                          temperature: float = 0.1) -> str:
        """Generate code using the LLM"""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the LLM model"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider"""
    
    def __init__(self, api_key: str, model: str = "gpt-4", base_url: Optional[str] = None, timeout: int = 60):
        """
        Initialize OpenAI provider
        
        Args:
            api_key (str): OpenAI API key
            model (str): Model name
        """
        try:
            import openai
            self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
            self.model = model
            self.base_url = base_url
            self.timeout = timeout
        except ImportError:
            raise ImportError("OpenAI library required. Install with: pip install openai")
    
    async def generate_code(self, prompt: str, max_tokens: int = 4000, 
                          temperature: float = 0.1) -> str:
        """
        Generate code using OpenAI GPT
        
        Args:
            prompt (str): Prompt for code generation
            max_tokens (int): Maximum tokens to generate
            temperature (float): Temperature for randomness
            
        Returns:
            str: Generated code
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert Java developer specializing in converting PL/SQL to Spring Boot applications."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=60
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get OpenAI model information"""
        return {
            'provider': 'OpenAI',
            'model': self.model,
            'base_url': self.base_url or 'https://api.openai.com/v1',
            'max_tokens': 8000,
            'supports_streaming': True
        }


class HuggingFaceProvider(LLMProvider):
    """Hugging Face provider via OpenAI-compatible chat completions API."""
    
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-20b", base_url: str = "https://router.huggingface.co/v1", timeout: int = 60):
        try:
            import openai
            self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
            self.model = model
            self.base_url = base_url
            self.timeout = timeout
        except ImportError:
            raise ImportError("OpenAI library required. Install with: pip install openai")
    
    async def generate_code(self, prompt: str, max_tokens: int = 4000,
                          temperature: float = 0.1) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert Java developer specializing in converting PL/SQL to Spring Boot applications."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=self.timeout
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Hugging Face API error: {str(e)}")
            raise
    
    def get_model_info(self) -> Dict[str, Any]:
        return {
            'provider': 'HuggingFace',
            'model': self.model,
            'base_url': self.base_url,
            'max_tokens': 8000,
            'supports_streaming': True
        }


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider"""
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229", timeout: int = 60):
        """
        Initialize Anthropic provider
        
        Args:
            api_key (str): Anthropic API key
            model (str): Model name
        """
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(api_key=api_key)
            self.model = model
            self.timeout = timeout
        except ImportError:
            raise ImportError("Anthropic library required. Install with: pip install anthropic")
    
    async def generate_code(self, prompt: str, max_tokens: int = 4000, 
                          temperature: float = 0.1) -> str:
        """
        Generate code using Anthropic Claude
        
        Args:
            prompt (str): Prompt for code generation
            max_tokens (int): Maximum tokens to generate
            temperature (float): Temperature for randomness
            
        Returns:
            str: Generated code
        """
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Anthropic model information"""
        return {
            'provider': 'Anthropic',
            'model': self.model,
            'max_tokens': 100000,
            'supports_streaming': False
        }


class PromptTemplate:
    """Manages prompt templates for different conversion types"""
    
    def __init__(self):
        """Initialize prompt templates"""
        self.templates = {
            'procedure_to_service': self._get_procedure_template(),
            'function_to_service': self._get_function_template(),
            'trigger_to_event': self._get_trigger_template(),
            'package_to_class': self._get_package_template(),
            'sql_to_repository': self._get_sql_template(),
            'entity_generation': self._get_entity_template()
        }
    
    def get_prompt(self, conversion_type: str, plsql_ast: Dict[str, Any], 
                  context: Dict[str, Any]) -> str:
        """
        Get prompt for specific conversion type
        
        Args:
            conversion_type (str): Type of conversion
            plsql_ast (Dict[str, Any]): PL/SQL AST
            context (Dict[str, Any]): Additional context
            
        Returns:
            str: Generated prompt
        """
        if conversion_type not in self.templates:
            raise ValueError(f"Unknown conversion type: {conversion_type}")
        
        template = self.templates[conversion_type]
        format_context = dict(context)
        format_context.setdefault('package_name', 'com.company.project')
        format_context.setdefault('dependencies', [])
        format_context.setdefault('tables', [])
        format_context['plsql_code'] = self._format_plsql_ast(plsql_ast)
        return template.format(**format_context)
    
    def _get_procedure_template(self) -> str:
        """Get procedure to service conversion template"""
        return """
Convert the following PL/SQL procedure to a Java Spring Boot service method.

PL/SQL Procedure:
{plsql_code}

Requirements:
1. Create a Spring Boot service class with proper annotations
2. Use JPA repositories for database operations
3. Implement proper exception handling
4. Use dependency injection
5. Follow Java naming conventions
6. Add appropriate JavaDoc comments
7. Use the package name: {package_name}

Context:
- Dependencies: {dependencies}
- Tables involved: {tables}

Generate the complete Java service class with all necessary imports and annotations.
"""
    
    def _get_function_template(self) -> str:
        """Get function to service conversion template"""
        return """
Convert the following PL/SQL function to a Java Spring Boot service method.

PL/SQL Function:
{plsql_code}

Requirements:
1. Create a Spring Boot service class with proper annotations
2. Return appropriate Java types (avoid using Object)
3. Use JPA repositories for database operations
4. Implement proper exception handling
5. Use dependency injection
6. Follow Java naming conventions
7. Add appropriate JavaDoc comments
8. Use the package name: {package_name}

Context:
- Dependencies: {dependencies}
- Tables involved: {tables}

Generate the complete Java service class with all necessary imports and annotations.
"""
    
    def _get_trigger_template(self) -> str:
        """Get trigger to event conversion template"""
        return """
Convert the following PL/SQL trigger to a Java Spring Boot event listener or service method.

PL/SQL Trigger:
{plsql_code}

Requirements:
1. Create a Spring Boot service or event listener
2. Use @EventListener or appropriate annotations
3. Implement the trigger logic in Java
4. Use JPA repositories for database operations
5. Implement proper exception handling
6. Use dependency injection
7. Follow Java naming conventions
8. Add appropriate JavaDoc comments
9. Use the package name: {package_name}

Context:
- Trigger timing: {trigger_timing}
- Trigger event: {trigger_event}
- Table: {table}

Generate the complete Java class with all necessary imports and annotations.
"""
    
    def _get_package_template(self) -> str:
        """Get package to class conversion template"""
        return """
Convert the following PL/SQL package to Java classes.

PL/SQL Package:
{plsql_code}

Requirements:
1. Create appropriate Java classes (services, utilities, etc.)
2. Use proper package structure
3. Implement all procedures and functions as methods
4. Use dependency injection where appropriate
5. Implement proper exception handling
6. Follow Java naming conventions
7. Add appropriate JavaDoc comments
8. Use the package name: {package_name}

Context:
- Package procedures: {procedures}
- Package functions: {functions}
- Dependencies: {dependencies}

Generate the complete Java classes with all necessary imports and annotations.
"""
    
    def _get_sql_template(self) -> str:
        """Get SQL to JPA repository conversion template"""
        return """
Convert the following SQL queries to JPA repository methods.

SQL Queries:
{plsql_code}

Requirements:
1. Create a Spring Data JPA repository interface
2. Use appropriate JPA annotations
3. Implement custom queries using @Query if needed
4. Use method naming conventions for simple queries
5. Add appropriate JavaDoc comments
6. Use the package name: {package_name}

Context:
- Entity: {entity}
- Table: {table}
- Columns: {columns}

Generate the complete JPA repository interface with all necessary imports and annotations.
"""
    
    def _get_entity_template(self) -> str:
        """Get entity generation template"""
        return """
Generate a JPA entity class based on the following database table structure.

Table Information:
{plsql_code}

Requirements:
1. Create a JPA entity class with proper annotations
2. Map all columns to Java fields
3. Use appropriate data types
4. Add proper relationships if specified
5. Implement equals(), hashCode(), and toString() methods
6. Add appropriate JavaDoc comments
7. Use the package name: {package_name}

Context:
- Table name: {table_name}
- Primary key: {primary_key}
- Relationships: {relationships}

Generate the complete JPA entity class with all necessary imports and annotations.
"""
    
    def _format_plsql_ast(self, ast: Dict[str, Any]) -> str:
        """Format PL/SQL AST for prompt"""
        if not ast:
            return "No PL/SQL code provided"
        
        # Normalize single object AST into list-based structure expected below.
        if isinstance(ast, dict) and ast.get('type') in {'procedure', 'function', 'trigger', 'package'}:
            obj_type = ast.get('type')
            normalized = {'procedures': [], 'functions': [], 'triggers': [], 'packages': [], 'sql_statements': []}
            if obj_type == 'procedure':
                normalized['procedures'].append(ast)
            elif obj_type == 'function':
                normalized['functions'].append(ast)
            elif obj_type == 'trigger':
                normalized['triggers'].append(ast)
            elif obj_type == 'package':
                normalized['packages'].append(ast)
            ast = normalized
        
        formatted = []
        
        # Format procedures
        for proc in ast.get('procedures', []):
            formatted.append(f"PROCEDURE {proc.get('name', 'unknown')}")
            formatted.append(f"  Parameters: {proc.get('parameters', [])}")
            formatted.append(f"  Statements: {len(proc.get('statements', []))}")
            formatted.append("")
        
        # Format functions
        for func in ast.get('functions', []):
            formatted.append(f"FUNCTION {func.get('name', 'unknown')}")
            formatted.append(f"  Parameters: {func.get('parameters', [])}")
            formatted.append(f"  Return Type: {func.get('return_type', 'unknown')}")
            formatted.append("")
        
        # Format triggers
        for trigger in ast.get('triggers', []):
            formatted.append(f"TRIGGER {trigger.get('name', 'unknown')}")
            formatted.append(f"  Timing: {trigger.get('timing', 'unknown')}")
            formatted.append(f"  Event: {trigger.get('event', 'unknown')}")
            formatted.append(f"  Table: {trigger.get('table', 'unknown')}")
            formatted.append("")
        
        # Format SQL statements
        for sql_stmt in ast.get('sql_statements', []):
            formatted.append(f"SQL: {sql_stmt.get('text', 'unknown')}")
            formatted.append("")
        
        if formatted:
            return "\n".join(formatted)
        
        # Fallback to raw structure so the model still gets concrete context.
        return json.dumps(ast, ensure_ascii=True, default=str, indent=2)


class LLMConversionEngine:
    """Main LLM conversion engine"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LLM conversion engine
        
        Args:
            config (Dict[str, Any]): LLM configuration
        """
        self.config = config
        self.request_timeout = int(config.get('timeout', 60))
        self.retry_attempts = max(1, int(config.get('retry_attempts', 3)))
        self.retry_base_delay = float(config.get('retry_base_delay_seconds', 0.5))
        self.provider = self._create_provider()
        self.fallback_provider = self._create_fallback_provider()
        self.prompt_template = PromptTemplate()
        self.conversion_cache = {}
        
        # Performance settings
        self.max_concurrent_requests = config.get('batch_size', 5)
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
        logger.info(f"LLM Conversion Engine initialized with {self.provider.get_model_info()}")
    
    def _create_provider(self) -> LLMProvider:
        """Create LLM provider based on configuration"""
        provider_name = self.config.get('provider', 'openai')
        
        if provider_name.lower() == 'openai':
            return OpenAIProvider(
                api_key=self.config.get('api_key'),
                model=self.config.get('model', 'gpt-4'),
                base_url=self.config.get('base_url'),
                timeout=self.config.get('timeout', 60)
            )
        elif provider_name.lower() == 'anthropic':
            return AnthropicProvider(
                api_key=self.config.get('api_key'),
                model=self.config.get('model', 'claude-3-sonnet-20240229'),
                timeout=self.config.get('timeout', 60)
            )
        elif provider_name.lower() == 'huggingface':
            return HuggingFaceProvider(
                api_key=self.config.get('api_key'),
                model=self.config.get('model', 'openai/gpt-oss-20b'),
                base_url=self.config.get('base_url') or 'https://router.huggingface.co/v1',
                timeout=self.config.get('timeout', 60)
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_name}")

    def _create_fallback_provider(self) -> Optional[LLMProvider]:
        """Create optional fallback provider for transient upstream failures."""
        fallback_cfg = self.config.get('fallback')
        if not fallback_cfg or not isinstance(fallback_cfg, dict):
            return None
        provider_name = (fallback_cfg.get('provider') or '').lower()
        if not provider_name:
            return None
        try:
            if provider_name == 'openai':
                fallback_api_key = (
                    fallback_cfg.get('api_key')
                    or os.getenv('OPENAI_API_KEY')
                    or self.config.get('api_key')
                )
                return OpenAIProvider(
                    api_key=fallback_api_key,
                    model=fallback_cfg.get('model', 'gpt-4o-mini'),
                    base_url=fallback_cfg.get('base_url'),
                    timeout=fallback_cfg.get('timeout', self.request_timeout),
                )
            if provider_name == 'anthropic':
                fallback_api_key = (
                    fallback_cfg.get('api_key')
                    or os.getenv('ANTHROPIC_API_KEY')
                    or self.config.get('api_key')
                )
                return AnthropicProvider(
                    api_key=fallback_api_key,
                    model=fallback_cfg.get('model', 'claude-3-5-sonnet-latest'),
                    timeout=fallback_cfg.get('timeout', self.request_timeout),
                )
            if provider_name == 'huggingface':
                fallback_api_key = (
                    fallback_cfg.get('api_key')
                    or os.getenv('HUGGINGFACE_API_KEY')
                    or os.getenv('HF_TOKEN')
                    or self.config.get('api_key')
                )
                return HuggingFaceProvider(
                    api_key=fallback_api_key,
                    model=fallback_cfg.get('model', 'openai/gpt-oss-20b'),
                    base_url=fallback_cfg.get('base_url') or 'https://router.huggingface.co/v1',
                    timeout=fallback_cfg.get('timeout', self.request_timeout),
                )
            logger.warning(f"Ignoring unsupported fallback provider: {provider_name}")
            return None
        except Exception as e:
            logger.warning(f"Failed to initialize fallback provider: {e}")
            return None

    async def _generate_with_retries(self, prompt: str) -> str:
        """Generate text with retries and optional fallback provider."""
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                return await self.provider.generate_code(
                    prompt,
                    max_tokens=self.config.get('max_tokens', 4000),
                    temperature=self.config.get('temperature', 0.1),
                )
            except Exception as e:
                last_error = e
                if attempt < self.retry_attempts:
                    delay = self.retry_base_delay * attempt
                    logger.warning(
                        f"Primary provider attempt {attempt}/{self.retry_attempts} failed: {e}. Retrying in {delay:.1f}s."
                    )
                    await asyncio.sleep(delay)
        
        if self.fallback_provider:
            logger.warning("Primary provider exhausted retries. Switching to fallback provider.")
            for attempt in range(1, self.retry_attempts + 1):
                try:
                    return await self.fallback_provider.generate_code(
                        prompt,
                        max_tokens=self.config.get('max_tokens', 4000),
                        temperature=self.config.get('temperature', 0.1),
                    )
                except Exception as e:
                    last_error = e
                    if attempt < self.retry_attempts:
                        delay = self.retry_base_delay * attempt
                        logger.warning(
                            f"Fallback provider attempt {attempt}/{self.retry_attempts} failed: {e}. Retrying in {delay:.1f}s."
                        )
                        await asyncio.sleep(delay)
        
        raise last_error if last_error else RuntimeError("Code generation failed with unknown error")
    
    async def convert(self, ast_results: Dict[str, Any], 
                     dependency_graph: Dict[str, Any]) -> Dict[str, str]:
        """
        Convert PL/SQL AST to Java code
        
        Args:
            ast_results (Dict[str, Any]): Parsed AST results
            dependency_graph (Dict[str, Any]): Dependency analysis
            
        Returns:
            Dict[str, str]: Generated Java code files
        """
        logger.info("Starting LLM conversion process...")
        
        # Prepare conversion context
        context = self._prepare_conversion_context(ast_results, dependency_graph)
        
        # Convert different types of PL/SQL objects
        java_files = {}
        
        # Convert procedures
        procedures = ast_results.get('procedures', [])
        if procedures:
            logger.info(f"Converting {len(procedures)} procedures...")
            procedure_files = await self._convert_procedures(procedures, context)
            java_files.update(procedure_files)
        
        # Convert functions
        functions = ast_results.get('functions', [])
        if functions:
            logger.info(f"Converting {len(functions)} functions...")
            function_files = await self._convert_functions(functions, context)
            java_files.update(function_files)
        
        # Convert triggers
        triggers = ast_results.get('triggers', [])
        if triggers:
            logger.info(f"Converting {len(triggers)} triggers...")
            trigger_files = await self._convert_triggers(triggers, context)
            java_files.update(trigger_files)
        
        # Convert packages
        packages = ast_results.get('packages', [])
        if packages:
            logger.info(f"Converting {len(packages)} packages...")
            package_files = await self._convert_packages(packages, context)
            java_files.update(package_files)
        
        # Convert SQL queries to repositories
        sql_queries = self._extract_sql_queries(ast_results)
        if sql_queries:
            logger.info(f"Converting {len(sql_queries)} SQL queries to repositories...")
            repository_files = await self._convert_sql_to_repositories(sql_queries, context)
            java_files.update(repository_files)
        
        logger.info(f"LLM conversion completed. Generated {len(java_files)} Java files.")
        return java_files
    
    def _prepare_conversion_context(self, ast_results: Dict[str, Any], 
                                  dependency_graph: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare conversion context with all necessary information"""
        context = {
            'package_name': self.config.get('output', {}).get('package_name', 'com.company.project'),
            'dependencies': dependency_graph.get('dependencies', []),
            'tables': dependency_graph.get('tables', []),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'model_info': self.provider.get_model_info()
        }
        
        # Extract additional context from AST
        context['procedures'] = [p.get('name') for p in ast_results.get('procedures', [])]
        context['functions'] = [f.get('name') for f in ast_results.get('functions', [])]
        context['triggers'] = [t.get('name') for t in ast_results.get('triggers', [])]
        context['packages'] = [p.get('name') for p in ast_results.get('packages', [])]
        
        return context
    
    async def _convert_procedures(self, procedures: List[Dict[str, Any]], 
                                context: Dict[str, Any]) -> Dict[str, str]:
        """Convert PL/SQL procedures to Java services"""
        java_files = {}
        
        async def convert_single_procedure(procedure: Dict[str, Any]) -> Tuple[str, str]:
            async with self.semaphore:
                try:
                    # Create conversion request
                    conversion_request = ConversionRequest(
                        plsql_ast=procedure,
                        dependency_graph=context,
                        target_language="Java",
                        target_framework="Spring Boot"
                    )
                    
                    # Generate prompt
                    prompt = self.prompt_template.get_prompt(
                        'procedure_to_service',
                        conversion_request.plsql_ast,
                        context
                    )
                    
                    # Generate Java code
                    java_code = await self._generate_with_retries(prompt)
                    
                    # Clean up the generated code
                    cleaned_code = self._clean_java_code(java_code)
                    
                    # Generate filename
                    filename = f"{procedure.get('name', 'Procedure')}.java"
                    
                    return filename, cleaned_code
                    
                except Exception as e:
                    logger.error(f"Failed to convert procedure {procedure.get('name')}: {str(e)}")
                    return None, None
        
        # Convert procedures concurrently
        tasks = [convert_single_procedure(proc) for proc in procedures]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for filename, java_code in results:
            if filename and java_code and java_code.strip():
                java_files[filename] = java_code
        
        return java_files
    
    async def _convert_functions(self, functions: List[Dict[str, Any]], 
                               context: Dict[str, Any]) -> Dict[str, str]:
        """Convert PL/SQL functions to Java services"""
        java_files = {}
        
        async def convert_single_function(function: Dict[str, Any]) -> Tuple[str, str]:
            async with self.semaphore:
                try:
                    # Generate prompt
                    prompt = self.prompt_template.get_prompt(
                        'function_to_service',
                        function,
                        context
                    )
                    
                    # Generate Java code
                    java_code = await self._generate_with_retries(prompt)
                    
                    # Clean up the generated code
                    cleaned_code = self._clean_java_code(java_code)
                    
                    # Generate filename
                    filename = f"{function.get('name', 'Function')}.java"
                    
                    return filename, cleaned_code
                    
                except Exception as e:
                    logger.error(f"Failed to convert function {function.get('name')}: {str(e)}")
                    return None, None
        
        # Convert functions concurrently
        tasks = [convert_single_function(func) for func in functions]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for filename, java_code in results:
            if filename and java_code and java_code.strip():
                java_files[filename] = java_code
        
        return java_files
    
    async def _convert_triggers(self, triggers: List[Dict[str, Any]], 
                              context: Dict[str, Any]) -> Dict[str, str]:
        """Convert PL/SQL triggers to Java event listeners"""
        java_files = {}
        
        async def convert_single_trigger(trigger: Dict[str, Any]) -> Tuple[str, str]:
            async with self.semaphore:
                try:
                    # Prepare trigger-specific context
                    trigger_context = context.copy()
                    trigger_context.update({
                        'trigger_timing': trigger.get('timing', 'unknown'),
                        'trigger_event': trigger.get('event', 'unknown'),
                        'table': trigger.get('table', 'unknown')
                    })
                    
                    # Generate prompt
                    prompt = self.prompt_template.get_prompt(
                        'trigger_to_event',
                        trigger,
                        trigger_context
                    )
                    
                    # Generate Java code
                    java_code = await self._generate_with_retries(prompt)
                    
                    # Clean up the generated code
                    cleaned_code = self._clean_java_code(java_code)
                    
                    # Generate filename
                    filename = f"{trigger.get('name', 'Trigger')}Handler.java"
                    
                    return filename, cleaned_code
                    
                except Exception as e:
                    logger.error(f"Failed to convert trigger {trigger.get('name')}: {str(e)}")
                    return None, None
        
        # Convert triggers concurrently
        tasks = [convert_single_trigger(trigger) for trigger in triggers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for filename, java_code in results:
            if filename and java_code and java_code.strip():
                java_files[filename] = java_code
        
        return java_files
    
    async def _convert_packages(self, packages: List[Dict[str, Any]], 
                              context: Dict[str, Any]) -> Dict[str, str]:
        """Convert PL/SQL packages to Java classes"""
        java_files = {}
        
        async def convert_single_package(package: Dict[str, Any]) -> Tuple[str, str]:
            async with self.semaphore:
                try:
                    # Prepare package-specific context
                    package_context = context.copy()
                    package_context.update({
                        'procedures': [p.get('name') for p in package.get('procedures', [])],
                        'functions': [f.get('name') for f in package.get('functions', [])]
                    })
                    
                    # Generate prompt
                    prompt = self.prompt_template.get_prompt(
                        'package_to_class',
                        package,
                        package_context
                    )
                    
                    # Generate Java code
                    java_code = await self._generate_with_retries(prompt)
                    
                    # Clean up the generated code
                    cleaned_code = self._clean_java_code(java_code)
                    
                    # Generate filename
                    filename = f"{package.get('name', 'Package')}.java"
                    
                    return filename, cleaned_code
                    
                except Exception as e:
                    logger.error(f"Failed to convert package {package.get('name')}: {str(e)}")
                    return None, None
        
        # Convert packages concurrently
        tasks = [convert_single_package(pkg) for pkg in packages]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for filename, java_code in results:
            if filename and java_code and java_code.strip():
                java_files[filename] = java_code
        
        return java_files
    
    async def _convert_sql_to_repositories(self, sql_queries: List[Dict[str, Any]], 
                                         context: Dict[str, Any]) -> Dict[str, str]:
        """Convert SQL queries to JPA repositories"""
        java_files = {}
        
        # Group queries by table
        table_queries = {}
        for query in sql_queries:
            tables = query.get('tables', [])
            for table in tables:
                if table not in table_queries:
                    table_queries[table] = []
                table_queries[table].append(query)
        
        async def convert_table_queries(table_name: str, queries: List[Dict[str, Any]]) -> Tuple[str, str]:
            async with self.semaphore:
                try:
                    # Prepare table-specific context
                    table_context = context.copy()
                    table_context.update({
                        'entity': f"{table_name}Entity",
                        'table': table_name,
                        'columns': self._extract_columns_from_queries(queries)
                    })
                    
                    # Create combined SQL for the table
                    combined_sql = "\n\n".join([q.get('query', '') for q in queries])
                    
                    # Generate prompt
                    prompt = self.prompt_template.get_prompt(
                        'sql_to_repository',
                        {'sql_statements': [{'text': combined_sql}]},
                        table_context
                    )
                    
                    # Generate Java code
                    java_code = await self._generate_with_retries(prompt)
                    
                    # Clean up the generated code
                    cleaned_code = self._clean_java_code(java_code)
                    
                    # Generate filename
                    filename = f"{table_name}Repository.java"
                    
                    return filename, cleaned_code
                    
                except Exception as e:
                    logger.error(f"Failed to convert SQL queries for table {table_name}: {str(e)}")
                    return None, None
        
        # Convert table queries concurrently
        tasks = [convert_table_queries(table, queries) for table, queries in table_queries.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for filename, java_code in results:
            if filename and java_code and java_code.strip():
                java_files[filename] = java_code
        
        return java_files
    
    def _extract_sql_queries(self, ast_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract SQL queries from AST results"""
        sql_queries = []
        
        # Extract from procedures
        for procedure in ast_results.get('procedures', []):
            for statement in procedure.get('statements', []):
                if statement.get('type') == 'sql_statement':
                    query_text = statement.get('text', '')
                    tables = statement.get('tables', []) or self._infer_tables_from_sql(query_text)
                    sql_queries.append({
                        'query': query_text,
                        'tables': tables,
                        'type': 'procedure'
                    })
        
        # Extract from functions
        for function in ast_results.get('functions', []):
            for statement in function.get('statements', []):
                if statement.get('type') == 'sql_statement':
                    query_text = statement.get('text', '')
                    tables = statement.get('tables', []) or self._infer_tables_from_sql(query_text)
                    sql_queries.append({
                        'query': query_text,
                        'tables': tables,
                        'type': 'function'
                    })
        
        # Extract from triggers
        for trigger in ast_results.get('triggers', []):
            for statement in trigger.get('statements', []):
                if statement.get('type') == 'sql_statement':
                    query_text = statement.get('text', '')
                    tables = statement.get('tables', []) or self._infer_tables_from_sql(query_text)
                    sql_queries.append({
                        'query': query_text,
                        'tables': tables,
                        'type': 'trigger'
                    })
        
        return sql_queries

    def _infer_tables_from_sql(self, sql_text: str) -> List[str]:
        """Infer table names from SQL text using lightweight regex patterns."""
        if not sql_text:
            return []
        tables = set()
        patterns = [
            r"\bfrom\s+([a-zA-Z_][a-zA-Z0-9_$#.]*)",
            r"\bjoin\s+([a-zA-Z_][a-zA-Z0-9_$#.]*)",
            r"\bupdate\s+([a-zA-Z_][a-zA-Z0-9_$#.]*)",
            r"\binsert\s+into\s+([a-zA-Z_][a-zA-Z0-9_$#.]*)",
            r"\bdelete\s+from\s+([a-zA-Z_][a-zA-Z0-9_$#.]*)",
            r"\bmerge\s+into\s+([a-zA-Z_][a-zA-Z0-9_$#.]*)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, sql_text, flags=re.IGNORECASE):
                table_name = match.group(1).split('.')[-1]
                if table_name:
                    tables.add(table_name)
        return list(tables)
    
    def _extract_columns_from_queries(self, queries: List[Dict[str, Any]]) -> List[str]:
        """Extract column names from SQL queries"""
        columns = set()
        
        for query in queries:
            query_text = query.get('query', '').upper()
            # Simple column extraction - in a real implementation, 
            # this would use a proper SQL parser
            if 'SELECT' in query_text and 'FROM' in query_text:
                select_part = query_text.split('FROM')[0]
                if 'SELECT' in select_part:
                    cols = select_part.split('SELECT')[1].strip()
                    # Extract column names (simplified)
                    for col in cols.split(','):
                        col = col.strip()
                        if col and col != '*':
                            columns.add(col)
        
        return list(columns)
    
    def _clean_java_code(self, java_code: str) -> str:
        """
        Clean up generated Java code
        
        Args:
            java_code (str): Raw Java code from LLM
            
        Returns:
            str: Cleaned Java code
        """
        if not java_code:
            return ""
        
        text = java_code.strip()
        
        # Prefer fenced code content when present.
        fence_match = re.search(r"```(?:java)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fence_match:
            text = fence_match.group(1).strip()
        
        lines = text.splitlines()
        start_idx = None
        
        # Start from first obvious Java declaration.
        decl_pattern = re.compile(r"^\s*(public\s+)?(class|interface|enum|record)\s+\w+")
        for i, line in enumerate(lines):
            if decl_pattern.search(line):
                start_idx = i
                break
        
        if start_idx is not None:
            return "\n".join(lines[start_idx:]).strip()
        
        # Fallback: keep full text if it already looks like Java source.
        java_markers = ("package ", "import ", "@", "class ", "interface ", "enum ", "record ")
        if any(marker in text for marker in java_markers):
            return text
        
        return text
    
    def get_conversion_stats(self) -> Dict[str, Any]:
        """Get conversion statistics"""
        return {
            'provider': self.provider.get_model_info(),
            'cache_size': len(self.conversion_cache),
            'concurrent_requests': self.max_concurrent_requests
        }


def create_llm_engine(config: Dict[str, Any]) -> LLMConversionEngine:
    """Create and return a configured LLM conversion engine"""
    return LLMConversionEngine(config)
