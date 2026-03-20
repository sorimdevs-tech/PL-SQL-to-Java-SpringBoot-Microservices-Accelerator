"""
LLM Conversion Engine for PL/SQL Modernization Platform

FIXES APPLIED:
  LCE-1  : Deprecated Anthropic model claude-3-sonnet-20240229
  LCE-2  : asyncio.Semaphore created at __init__ time (Python 3.12 RuntimeError)
  LCE-3  : entity_fields always {} because entity folder doesn't exist at conversion time
  LCE-4  : asyncio.gather results unpacked as tuples — TypeError on Exception items
  LCE-5  : Template KeyError on missing placeholder defaults
  LCE-6  : entity_fields injected as raw Python repr dict
  LCE-7  : Fallback entity setters always emit "No matching entity fields found"
  LCE-8  : OpenAI timeout= is not accepted by create() in openai>=1.0
  LCE-9  : Dead import `from email import errors`
  LCE-10 : False-positive empty-method validation fires on valid no-arg methods
  LCE-11 : @PostMapping validation regex spans entire file (cross-method false positives)
  LCE-12 : OpenRouter default model 'openai/gpt-oss-20b' does not exist
  LCE-13 : Multi-class LLM output causes broken import merging
  LCE-14 : Commented-out validation block removed (dead code)
  LCE-15 : conversion_cache implemented (was initialized but never used)
"""

import os
import json
import asyncio
import hashlib
import time
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
import logging

from ..utils.logger import get_logger
from ..utils.config import get_config_value

logger = get_logger(__name__)


@dataclass
class ConversionRequest:
    plsql_ast: Dict[str, Any]
    dependency_graph: Dict[str, Any]
    target_language: str = "Java"
    target_framework: str = "Spring Boot"
    package_name: str = "com.company.project"


@dataclass
class ConversionResult:
    success: bool
    java_code: Optional[str]
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]


class LLMProvider(ABC):

    @abstractmethod
    async def generate_code(self, prompt: str, max_tokens: int = 4000,
                            temperature: float = 0.1) -> str:
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        pass


class OpenAIProvider(LLMProvider):

    def __init__(self, api_key: str, model: str = "gpt-4", base_url: Optional[str] = None, timeout: int = 60):
        try:
            import openai
            # LCE-8 FIX: set timeout on the client, NOT on individual create() calls
            self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
            self.api_key = api_key
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
                # LCE-8 FIX: no timeout= here; it is set on the client instance above
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise

    def get_model_info(self) -> Dict[str, Any]:
        return {
            'provider': 'OpenAI',
            'model': self.model,
            'base_url': self.base_url or 'https://api.openai.com/v1',
            'max_tokens': 8000,
            'supports_streaming': True
        }


class OpenRouterProvider(LLMProvider):

    def __init__(
        self,
        api_key: str,
        # LCE-12 FIX: use a real, available model as default
        model: str = "openai/gpt-4o-mini",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 60,
    ):
        try:
            import openai
            # LCE-8 FIX: timeout on client, not on create()
            self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
            self.api_key = api_key
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
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenRouter API error: {str(e)}")
            raise

    def get_model_info(self) -> Dict[str, Any]:
        return {
            'provider': 'OpenRouter',
            'model': self.model,
            'base_url': self.base_url,
            'max_tokens': 8000,
            'supports_streaming': True
        }


class AnthropicProvider(LLMProvider):

    def __init__(
        self,
        api_key: str,
        # LCE-1 FIX: use current model ID
        model: str = "claude-sonnet-4-6",
        timeout: int = 60,
    ):
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(api_key=api_key)
            self.api_key = api_key
            self.model = model
            self.timeout = timeout
        except ImportError:
            raise ImportError("Anthropic library required. Install with: pip install anthropic")

    async def generate_code(self, prompt: str, max_tokens: int = 4000,
                            temperature: float = 0.1) -> str:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise

    def get_model_info(self) -> Dict[str, Any]:
        return {
            'provider': 'Anthropic',
            'model': self.model,
            'max_tokens': 100000,
            'supports_streaming': False
        }


class PromptTemplate:

    def __init__(self):
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
        if conversion_type not in self.templates:
            raise ValueError(f"Unknown conversion type: {conversion_type}")

        template = self.templates[conversion_type]
        format_context = dict(context)

        # LCE-5 FIX: provide defaults for EVERY placeholder used across all templates
        format_context.setdefault('package_name', 'com.company.project')
        format_context.setdefault('dependencies', [])
        format_context.setdefault('tables', [])
        format_context.setdefault('entity_names', [])
        format_context.setdefault('repository_names', [])
        format_context.setdefault('trigger_timing', 'BEFORE')
        format_context.setdefault('trigger_event', 'INSERT')
        format_context.setdefault('table', '')
        format_context.setdefault('procedures', [])
        format_context.setdefault('functions', [])
        format_context.setdefault('entity', '')
        format_context.setdefault('table_name', '')
        format_context.setdefault('primary_key', 'id')
        format_context.setdefault('relationships', [])
        format_context.setdefault('columns', [])

        # LCE-6 FIX: serialize entity_fields as readable text, not raw Python dict repr
        raw_entity_fields = format_context.get('entity_fields', {})
        if isinstance(raw_entity_fields, dict) and raw_entity_fields:
            format_context['entity_fields'] = '\n'.join(
                f"{entity}: {', '.join(fields)}"
                for entity, fields in raw_entity_fields.items()
            )
        else:
            format_context['entity_fields'] = '(none — skip all entity setters)'

        format_context['plsql_code'] = self._format_plsql_ast(plsql_ast)
        return template.format(**format_context)

    # ── Templates (unchanged content, only placeholders ensured) ─────────────

    def _get_procedure_template(self) -> str:
        return """
Convert the following PL/SQL procedure to a Java Spring Boot service class.

PL/SQL Procedure:
{plsql_code}

Requirements:
1. Create a Spring Boot @Service class with @Transactional on the method
2. Inject the repository with @Autowired field — ONE @Autowired field per repository
3. Use the injected repository for ALL DB operations (save/findById/deleteById/insertXxx)
4. Implement exception handling using BusinessException (already exists in the project)
5. Use the package name: {package_name}
6. Use Long for NUMBER ID/count parameters; BigDecimal ONLY for NUMBER(p,s) decimal params

Context:
- Tables: {tables}
- Allowed Entities: {entity_names}
- Allowed Repositories: {repository_names}

Allowed Entity Fields (USE ONLY THESE):
{entity_fields}

STRICT OUTPUT RULES — violating any of these causes compile errors:
1. Output EXACTLY ONE Java file: package declaration, then imports, then ONE public class.
2. The file MUST end with the closing brace of the class: last character must be }}.
3. Do NOT add ANY content after the class closing brace — no comments, no imports,
   no placeholder classes, no @Entity annotations, nothing whatsoever.
4. Do NOT duplicate @Autowired fields — inject each repository EXACTLY ONCE.
5. Entity classes have ONLY no-arg constructors. NEVER call new EntityClass(arg1, arg2,...).
   WRONG: new CustomersEntity(id, name, email)
   RIGHT: CustomersEntity e = new CustomersEntity(); e.setName(name); e.setEmail(email);
6. Do NOT use @Modifying or @Transactional in a @Service class — only in @Repository.
7. Do NOT use EntityManager, @PersistenceContext, or createNativeQuery.
8. Do NOT generate duplicate case labels in switch statements.
9. Implement ALL four switch cases (INSERT/UPDATE/DELETE/SELECT) with real repository calls.
   NEVER leave TODO stubs or throw "not implemented" exceptions.
10. For INSERT: call the repository insertXxx() native-SQL method, NOT save().
    The PK is Oracle-sequence-generated — do NOT pass the PK as a parameter.
    WRONG: customersRepository.insertCustomer(pCustomerId, pName, pEmail, pStatus)
    RIGHT: customersRepository.insertCustomer(pName, pEmail, pStatus)
11. When calling any repository method, the Java argument order MUST match the repository
    method signature EXACTLY. Never reorder parameters based on SQL column order or guesswork.
    Example repository signature:
    int insertOrder(Long customerId, BigDecimal amount, String status);
    WRONG call: ordersRepository.insertOrder(pAmount, pStatus, pCustomerId);
    RIGHT call: ordersRepository.insertOrder(pCustomerId, pAmount, pStatus);
12. Before emitting an insertXxx()/updateXxx()/deleteXxx() call, inspect the repository
    method name and copy its parameter list in the exact declared order and Java types.
    If the repository method accepts BigDecimal, pass BigDecimal in that exact slot.
13. For UPDATE: findById(id).orElseThrow(), then setters, then save(entity).
    Do NOT call a generic .update() method — it does not exist.
14. FK fields in entities are mapped as entity OBJECTS, not Long IDs.
    WRONG: order.setCustomerId(pCustomerId)   // no such setter exists
    RIGHT: CustomersEntity c = customersRepository.findById(pCustomerId).orElseThrow(...);
           order.setCustomersEntity(c);
15. The service method return type MUST be void. The controller handles the response.
16. Use BigDecimal for ALL decimal/monetary NUMBER columns. NEVER use Double or Float.
    NUMBER(10,2) -> BigDecimal.   Any NUMBER(p,s) where s > 0 -> BigDecimal.
17. Entity and Repository class names are PascalCase. NEVER use ALLCAPS.
    WRONG: CUSTOMERSEntity, ORDERSEntity, PAYMENTSEntity, CUSTOMERSRepository
    RIGHT: CustomersEntity, OrdersEntity, PaymentsEntity, CustomersRepository
18. Import only classes that actually exist in the project.
    NEVER import: com.example.demo.entity.Crud, com.example.demo.repository.CrudRepository,
    or any ALLCAPS entity/repository class name.

Output: ONE complete compilable Java file ending with exactly one closing }}.
No markdown, no explanations, no extra text before or after the Java code.
"""

    def _get_function_template(self) -> str:
        return """
Convert the following PL/SQL function to a Java Spring Boot service class.

PL/SQL Function:
{plsql_code}

Package: {package_name}
Allowed Entities: {entity_names}
Allowed Repositories: {repository_names}
Entity Fields (ONLY these):
{entity_fields}

STRICT OUTPUT RULES:
- NEVER use EntityManager, @PersistenceContext, or createNativeQuery
- ALWAYS use the injected @Autowired repository for all DB operations
- Use Long for NUMBER ID/count params; BigDecimal ONLY for NUMBER(p,s) decimal params
- If calling any repository method, the Java argument order MUST match the repository
  method signature exactly. Never reorder arguments by SQL column order.
- For insertXxx() methods, do NOT pass the PK when the query uses sequence.NEXTVAL.
- Output EXACTLY ONE Java file. The LAST character must be the class closing brace }}.
- Do NOT add any content after the class closing brace.

Output: ONE complete compilable Java file. Package + imports + single class.
No markdown, no explanations, no extra text after the closing }}.
"""

    def _get_trigger_template(self) -> str:
        return """
Convert the following PL/SQL trigger to a Java Spring Boot event listener.

PL/SQL Trigger:
{plsql_code}

Trigger timing: {trigger_timing}
Trigger event: {trigger_event}
Table: {table}
Package: {package_name}
Allowed Entities: {entity_names}

Output: ONE complete compilable Java file.
"""

    def _get_package_template(self) -> str:
        return """
Convert the following PL/SQL package to Java Spring Boot service classes.

PL/SQL Package:
{plsql_code}

Package: {package_name}
Procedures: {procedures}
Functions: {functions}
Allowed Entities: {entity_names}
Entity Fields:
{entity_fields}

STRICT OUTPUT RULES:
- Output EXACTLY ONE Java file ending with the class closing brace }}.
- Do NOT add any content after the closing brace.

Output: ONE complete compilable Java file (primary service class).
No markdown, no explanations, no extra text.
"""

    def _get_sql_template(self) -> str:
        return """
Convert the following SQL queries to a Spring Data JPA repository interface.

SQL:
{plsql_code}

Entity: {entity}
Table: {table}
Columns: {columns}
Package: {package_name}

STRICT OUTPUT RULES — violating any causes compile errors:
1. Output EXACTLY ONE Java interface file: package + imports + ONE public interface.
2. The file MUST end with the closing brace of the interface: last character is }}.
3. Do NOT add ANY content after the interface closing brace.
4. Each @Query method needs EXACTLY ONE @Modifying (if modifying) and EXACTLY ONE
   @Transactional — NEVER repeat the same annotation twice on a single method.
   The correct order is: @Modifying (line 1), @Transactional (line 2), @Query (line 3),
   then the method signature. Never write @Modifying @Transactional @Modifying @Transactional.
   NEVER emit a second annotation block before the same @Query method.
   WRONG:
   @Modifying
   @Transactional
   @Modifying
   @Transactional
   @Query(...)
   int updateX(...);
   RIGHT:
   @Modifying
   @Transactional
   @Query(...)
   int updateX(...);
5. Every named parameter :paramName in a @Query MUST have a matching @Param("paramName")
   annotation BEFORE the Java type: @Param("name") String name — NOT String @Param("name") name.
6. Use native SQL (nativeQuery = true) for INSERT/DELETE and for UPDATE on tables with FK columns.
7. All column names in native SQL must be real SQL column names (lowercase), not Java field names.
8. INSERT method signatures must match the non-PK bind parameters in the SQL in the same order.
   If SQL uses sequence.NEXTVAL for the PK, do NOT include the PK in the Java method parameters.
   Example:
   INSERT INTO orders (order_id, customer_id, amount, status, created_at)
   VALUES (orders_seq.NEXTVAL, :customerId, :amount, :status, SYSDATE)
   REQUIRED signature:
   int insertOrder(@Param("customerId") Long customerId,
                   @Param("amount") BigDecimal amount,
                   @Param("status") String status);

Output: ONE complete compilable Java interface file ending with }}.
No markdown, no explanations, no extra text.
"""

    def _get_entity_template(self) -> str:
        return """
Generate a JPA entity class for the following table.

{plsql_code}

Table name: {table_name}
Primary key: {primary_key}
Package: {package_name}.entity

Rules: @Entity + @Table, jakarta.persistence.*, one class only, no services/repos.
Output: ONE complete compilable Java entity file.
"""

    def _format_plsql_ast(self, ast: Dict[str, Any]) -> str:
        if not ast:
            return "No PL/SQL code provided"

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
        for proc in ast.get('procedures', []):
            formatted.append(f"PROCEDURE {proc.get('name', 'unknown')}")
            formatted.append(f"  Parameters: {proc.get('parameters', [])}")
        for func in ast.get('functions', []):
            formatted.append(f"FUNCTION {func.get('name', 'unknown')}")
            formatted.append(f"  Return Type: {func.get('return_type', 'unknown')}")
        for trigger in ast.get('triggers', []):
            formatted.append(f"TRIGGER {trigger.get('name', 'unknown')}")
            formatted.append(f"  Timing: {trigger.get('timing', 'unknown')}")
            formatted.append(f"  Event: {trigger.get('event', 'unknown')}")
            formatted.append(f"  Table: {trigger.get('table', 'unknown')}")
        for sql_stmt in ast.get('sql_statements', []):
            formatted.append(f"SQL: {sql_stmt.get('text', 'unknown')}")

        if formatted:
            return "\n".join(formatted)
        return json.dumps(ast, ensure_ascii=True, default=str, indent=2)


class LLMConversionEngine:

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.request_timeout = int(config.get('timeout', 60))
        self.retry_attempts = max(1, int(config.get('retry_attempts', 3)))
        self.retry_base_delay = float(config.get('retry_base_delay_seconds', 0.5))
        self.provider = self._create_provider()
        self.fallback_provider = self._create_fallback_provider()
        self.repair_provider = self._create_repair_provider()
        self.prompt_template = PromptTemplate()

        # LCE-15 FIX: conversion_cache is now actually used (keyed by prompt hash)
        self._conversion_cache: Dict[str, str] = {}

        self.max_concurrent_requests = config.get('batch_size', 5)

        # LCE-2 FIX: do NOT create Semaphore at __init__ time.
        # It is created lazily inside async context.
        self._semaphore: Optional[asyncio.Semaphore] = None

        logger.info(f"LLM Conversion Engine initialized with {self.provider.get_model_info()}")

    def _get_semaphore(self) -> asyncio.Semaphore:
        """LCE-2 FIX: create Semaphore lazily inside running event loop."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        return self._semaphore

    def _create_provider(self) -> LLMProvider:
        return self._create_provider_from_config(self.config)

    def _create_provider_from_config(self, provider_cfg: Dict[str, Any]) -> LLMProvider:
        provider_name = (provider_cfg.get('provider') or 'openai').lower()
        if provider_name == 'openai':
            return OpenAIProvider(
                api_key=provider_cfg.get('api_key'),
                model=provider_cfg.get('model', 'gpt-4'),
                base_url=provider_cfg.get('base_url'),
                timeout=provider_cfg.get('timeout', 60)
            )
        if provider_name == 'anthropic':
            return AnthropicProvider(
                api_key=provider_cfg.get('api_key'),
                model=provider_cfg.get('model', 'claude-sonnet-4-6'),
                timeout=provider_cfg.get('timeout', 60)
            )
        if provider_name == 'openrouter':
            return OpenRouterProvider(
                api_key=provider_cfg.get('api_key'),
                model=provider_cfg.get('model', 'openai/gpt-4o-mini'),
                base_url=provider_cfg.get('base_url') or 'https://openrouter.ai/api/v1',
                timeout=provider_cfg.get('timeout', 60)
            )
        raise ValueError(f"Unsupported LLM provider: {provider_name}")

    def _create_fallback_provider(self) -> Optional[LLMProvider]:
        fallback_cfg = self.config.get('fallback')
        if not fallback_cfg or not isinstance(fallback_cfg, dict):
            return None
        fallback_cfg = dict(fallback_cfg)
        provider_name = (fallback_cfg.get('provider') or '').lower()
        if not provider_name:
            return None
        try:
            if provider_name == 'openai':
                fallback_cfg['api_key'] = fallback_cfg.get('api_key') or os.getenv('OPENAI_API_KEY') or self.config.get('api_key')
            elif provider_name == 'anthropic':
                fallback_cfg['api_key'] = fallback_cfg.get('api_key') or os.getenv('ANTHROPIC_API_KEY') or self.config.get('api_key')
            elif provider_name == 'openrouter':
                fallback_cfg['api_key'] = fallback_cfg.get('api_key') or os.getenv('OPENROUTER_API_KEY') or self.config.get('api_key')
                fallback_cfg['base_url'] = fallback_cfg.get('base_url') or 'https://openrouter.ai/api/v1'
            else:
                logger.warning(f"Ignoring unsupported fallback provider: {provider_name}")
                return None
            fallback_cfg['timeout'] = fallback_cfg.get('timeout', self.request_timeout)
            return self._create_provider_from_config(fallback_cfg)
        except Exception as e:
            logger.warning(f"Failed to initialize fallback provider: {e}")
            return None

    def _create_repair_provider(self) -> Optional[LLMProvider]:
        repair_cfg = self.config.get('backup_llm')
        if not repair_cfg or not isinstance(repair_cfg, dict) or not repair_cfg.get('enabled'):
            return None
        resolved = dict(repair_cfg)
        provider_name = (resolved.get('provider') or self.config.get('provider') or '').lower()
        if not provider_name:
            return None
        resolved['provider'] = provider_name
        if provider_name == 'openrouter':
            resolved['api_key'] = resolved.get('api_key') or os.getenv('OPENROUTER_API_KEY') or self.config.get('api_key')
            resolved['base_url'] = resolved.get('base_url') or 'https://openrouter.ai/api/v1'
            resolved.setdefault('model', 'openai/gpt-oss-120b')
        elif provider_name == 'openai':
            resolved['api_key'] = resolved.get('api_key') or os.getenv('OPENAI_API_KEY') or self.config.get('api_key')
        elif provider_name == 'anthropic':
            resolved['api_key'] = resolved.get('api_key') or os.getenv('ANTHROPIC_API_KEY') or self.config.get('api_key')
        else:
            logger.warning("Ignoring unsupported repair provider: %s", provider_name)
            return None
        resolved['timeout'] = resolved.get('timeout', max(self.request_timeout, 180))
        try:
            return self._create_provider_from_config(resolved)
        except Exception as e:
            logger.warning(f"Failed to initialize repair provider: {e}")
            return None

    def _extract_entity_fields_from_files(self, base_path: str, package_name: str) -> Dict[str, List[str]]:
        """
        LCE-3 NOTE: This method reads from disk. It will return {} if called before
        entity files are generated. The orchestrator must call this AFTER SpringBootGenerator
        has written entity files, then pass the result into convert() context.
        """
        entity_fields = {}
        entity_folder = os.path.join(base_path, "src", "main", "java",
                                     *package_name.split("."), "entity")
        if not os.path.exists(entity_folder):
            logger.warning(f"Entity folder not found: {entity_folder}")
            return entity_fields

        for file in os.listdir(entity_folder):
            if not file.endswith(".java"):
                continue
            entity_name = file.replace(".java", "")
            file_path = os.path.join(entity_folder, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                matches = re.findall(r'private\s+(?!static)(?:[\w<>?,\s]+)\s+(\w+);', content)
                if matches:
                    entity_fields[entity_name] = matches
            except Exception as e:
                logger.warning(f"Failed to parse entity {entity_name}: {e}")

        return entity_fields

    def _cache_key(self, prompt: str) -> str:
        """LCE-15 FIX: produce a stable cache key from the prompt."""
        return hashlib.sha256(prompt.encode('utf-8')).hexdigest()

    async def _generate_with_retries(self, prompt: str) -> str:
        # LCE-15 FIX: check cache before calling LLM
        cache_key = self._cache_key(prompt)
        if cache_key in self._conversion_cache:
            logger.debug("Cache hit for prompt (sha256=%s)", cache_key[:12])
            return self._conversion_cache[cache_key]

        last_error: Optional[Exception] = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                result = await self.provider.generate_code(
                    prompt,
                    max_tokens=self.config.get('max_tokens', 4000),
                    temperature=self.config.get('temperature', 0.1),
                )
                self._conversion_cache[cache_key] = result
                return result
            except Exception as e:
                last_error = e
                if self._is_non_retryable_error(e):
                    break
                if attempt < self.retry_attempts:
                    delay = self.retry_base_delay * attempt
                    logger.warning(f"Primary attempt {attempt}/{self.retry_attempts} failed: {e}. Retry in {delay:.1f}s.")
                    await asyncio.sleep(delay)

        if self.fallback_provider:
            if self._should_skip_fallback(last_error):
                raise last_error if last_error else RuntimeError("Code generation failed")
            logger.warning("Switching to fallback provider.")
            for attempt in range(1, self.retry_attempts + 1):
                try:
                    result = await self.fallback_provider.generate_code(
                        prompt,
                        max_tokens=self.config.get('max_tokens', 4000),
                        temperature=self.config.get('temperature', 0.1),
                    )
                    self._conversion_cache[cache_key] = result
                    return result
                except Exception as e:
                    last_error = e
                    if self._is_non_retryable_error(e):
                        break
                    if attempt < self.retry_attempts:
                        delay = self.retry_base_delay * attempt
                        await asyncio.sleep(delay)

        raise last_error if last_error else RuntimeError("Code generation failed")

    def _is_non_retryable_error(self, error: Exception) -> bool:
        message = str(error).lower()
        non_retryable_markers = (
            'token_quota_exceeded', 'tokens per day limit exceeded',
            'insufficient_quota', 'quota exceeded', 'quota has been exceeded',
            'invalid api key', 'authentication', 'unauthorized',
        )
        return any(marker in message for marker in non_retryable_markers)

    def _should_skip_fallback(self, error: Optional[Exception]) -> bool:
        if error is None or not self.fallback_provider:
            return False
        if not self._is_non_retryable_error(error):
            return False
        if type(self.provider) is not type(self.fallback_provider):
            return False
        primary_key = getattr(self.provider, 'api_key', None)
        fallback_key = getattr(self.fallback_provider, 'api_key', None)
        return bool(primary_key and fallback_key and primary_key == fallback_key)

    async def convert(self, ast_results: Dict[str, Any], dependency_graph: Dict[str, Any],
                      entity_fields: Optional[Dict[str, List[str]]] = None) -> Dict[str, str]:
        """
        LCE-3 FIX: accept entity_fields as an optional parameter so the orchestrator
        can pass pre-generated field data after entity files have been written.
        """
        logger.info("Starting LLM conversion process...")
        context = self._prepare_conversion_context(ast_results, dependency_graph, entity_fields)
        java_files = {}

        procedures = ast_results.get('procedures', [])
        if procedures:
            logger.info(f"Converting {len(procedures)} procedures...")
            java_files.update(await self._convert_procedures(procedures, context))

        functions = ast_results.get('functions', [])
        if functions:
            logger.info(f"Converting {len(functions)} functions...")
            java_files.update(await self._convert_functions(functions, context))

        triggers = ast_results.get('triggers', [])
        if triggers:
            logger.info(f"Converting {len(triggers)} triggers...")
            java_files.update(await self._convert_triggers(triggers, context))

        packages = ast_results.get('packages', [])
        if packages:
            logger.info(f"Converting {len(packages)} packages...")
            java_files.update(await self._convert_packages(packages, context))

        sql_queries = self._extract_sql_queries(ast_results)
        if sql_queries:
            logger.info(f"Converting {len(sql_queries)} SQL queries to repositories...")
            java_files.update(await self._convert_sql_to_repositories(sql_queries, context))

        logger.info(f"LLM conversion completed. Generated {len(java_files)} Java files.")
        return java_files

    def _prepare_conversion_context(
        self,
        ast_results: Dict[str, Any],
        dependency_graph: Dict[str, Any],
        entity_fields: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        context = {
            'package_name': self.config.get('output', {}).get('package_name', 'com.company.project'),
            'dependencies': dependency_graph.get('dependencies', []),
            'tables': dependency_graph.get('tables', []),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'model_info': self.provider.get_model_info()
        }

        # LCE-3 FIX: prefer caller-supplied entity_fields; only fall back to disk read
        # if caller explicitly passes None AND the folder already exists.
        if entity_fields is not None:
            context['entity_fields'] = entity_fields
        else:
            output_base = self.config.get("output", {}).get("base_path", "")
            package_name = context['package_name']
            context['entity_fields'] = self._extract_entity_fields_from_files(output_base, package_name)

        tables = context.get('tables') or []

        # LCE-FIX: if the dependency graph provided no tables, extract them from
        # the AST's SQL statements as a fallback. This ensures entity_names and
        # repository_names are never empty when the SQL parser resolved table refs.
        if not tables:
            seen_tables: set = set()
            for section in ('procedures', 'functions', 'triggers'):
                for obj in ast_results.get(section, []):
                    for stmt in obj.get('statements', []):
                        if stmt.get('type') == 'sql_statement':
                            inferred = self._infer_tables_from_sql(stmt.get('text', ''))
                            for t in inferred:
                                if t.upper() not in seen_tables:
                                    seen_tables.add(t.upper())
                                    tables.append(t.upper())
            if tables:
                logger.info(f"LCE-FIX: inferred {len(tables)} tables from AST SQL statements: {tables}")
            context['tables'] = tables

        entity_names: List[str] = []
        repository_names: List[str] = []
        for table in tables:
            if not table:
                continue
            entity_base = self._to_pascal_case(str(table))
            entity_name = f"{entity_base}Entity"
            repo_name = f"{entity_base}Repository"
            if entity_name not in entity_names:
                entity_names.append(entity_name)
            if repo_name not in repository_names:
                repository_names.append(repo_name)
        context['entity_names'] = entity_names
        context['repository_names'] = repository_names

        context['procedures'] = [p.get('name') for p in ast_results.get('procedures', [])]
        context['functions'] = [f.get('name') for f in ast_results.get('functions', [])]
        context['triggers'] = [t.get('name') for t in ast_results.get('triggers', [])]
        context['packages'] = [p.get('name') for p in ast_results.get('packages', [])]

        return context

    # ── Conversion helpers ────────────────────────────────────────────────────

    async def _convert_procedures(self, procedures: List[Dict[str, Any]],
                                  context: Dict[str, Any]) -> Dict[str, str]:
        java_files = {}

        async def convert_single(procedure: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
            # LCE-2 FIX: semaphore created lazily inside async context
            async with self._get_semaphore():
                try:
                    prompt = self.prompt_template.get_prompt('procedure_to_service', procedure, context)
                    java_code = await self._generate_with_retries(prompt)
                    cleaned = self._clean_java_code(java_code)
                    errors = self._validate_java_code(cleaned)
                    for attempt in range(2):
                        if not errors:
                            break
                        logger.warning(f"[FIX {attempt+1}] {procedure.get('name')}: {errors}")
                        fix_prompt = self._build_fix_prompt(cleaned, errors, context)
                        cleaned = self._clean_java_code(await self._generate_with_retries(fix_prompt))
                        errors = self._validate_java_code(cleaned)
                    if errors:
                        logger.error(f"[FINAL FAILED] {procedure.get('name')}: {errors}")
                        cleaned = self._force_fix_controller(cleaned)
                    return f"{procedure.get('name', 'Procedure')}.java", cleaned
                except Exception as e:
                    logger.error(f"Failed to convert procedure {procedure.get('name')}: {e}")
                    fn, code = self._generate_procedure_fallback(procedure, context, e)
                    return fn, code

        # LCE-4 FIX: filter Exception objects from gather results before unpacking
        tasks = [convert_single(proc) for proc in procedures]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Procedure conversion task raised: {result}")
                continue
            filename, java_code = result
            if filename and java_code and java_code.strip():
                java_files[filename] = java_code
        return java_files

    async def _convert_functions(self, functions: List[Dict[str, Any]],
                                 context: Dict[str, Any]) -> Dict[str, str]:
        java_files = {}

        async def convert_single(function: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
            async with self._get_semaphore():
                try:
                    prompt = self.prompt_template.get_prompt('function_to_service', function, context)
                    java_code = await self._generate_with_retries(prompt)
                    cleaned = self._clean_java_code(java_code)
                    errors = self._validate_java_code(cleaned)
                    for attempt in range(2):
                        if not errors:
                            break
                        fix_prompt = self._build_fix_prompt(cleaned, errors, context)
                        cleaned = self._clean_java_code(await self._generate_with_retries(fix_prompt))
                        errors = self._validate_java_code(cleaned)
                    return f"{function.get('name', 'Function')}.java", cleaned
                except Exception as e:
                    logger.error(f"Failed to convert function {function.get('name')}: {e}")
                    fn, code = self._generate_function_fallback(function, context, e)
                    return fn, code

        results = await asyncio.gather(*[convert_single(f) for f in functions], return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Function conversion task raised: {result}")
                continue
            filename, java_code = result
            if filename and java_code and java_code.strip():
                java_files[filename] = java_code
        return java_files

    async def _convert_triggers(self, triggers: List[Dict[str, Any]],
                                context: Dict[str, Any]) -> Dict[str, str]:
        java_files = {}

        async def convert_single(trigger: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
            async with self._get_semaphore():
                try:
                    trigger_context = {
                        **context,
                        'trigger_timing': trigger.get('timing', 'BEFORE'),
                        'trigger_event': trigger.get('event', 'INSERT'),
                        'table': trigger.get('table', ''),
                    }
                    prompt = self.prompt_template.get_prompt('trigger_to_event', trigger, trigger_context)
                    java_code = await self._generate_with_retries(prompt)
                    cleaned = self._clean_java_code(java_code)
                    errors = self._validate_java_code(cleaned)
                    for attempt in range(2):
                        if not errors:
                            break
                        fix_prompt = self._build_fix_prompt(cleaned, errors, context)
                        cleaned = self._clean_java_code(await self._generate_with_retries(fix_prompt))
                        errors = self._validate_java_code(cleaned)
                    return f"{trigger.get('name', 'Trigger')}Handler.java", cleaned
                except Exception as e:
                    logger.error(f"Failed to convert trigger {trigger.get('name')}: {e}")
                    return None, None

        results = await asyncio.gather(*[convert_single(t) for t in triggers], return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                continue
            filename, java_code = result
            if filename and java_code and java_code.strip():
                java_files[filename] = java_code
        return java_files

    async def _convert_packages(self, packages: List[Dict[str, Any]],
                                context: Dict[str, Any]) -> Dict[str, str]:
        java_files = {}

        async def convert_single(package: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
            async with self._get_semaphore():
                try:
                    pkg_context = {
                        **context,
                        'procedures': [p.get('name') for p in package.get('procedures', [])],
                        'functions': [f.get('name') for f in package.get('functions', [])],
                    }
                    prompt = self.prompt_template.get_prompt('package_to_class', package, pkg_context)
                    java_code = await self._generate_with_retries(prompt)
                    cleaned = self._clean_java_code(java_code)
                    return f"{package.get('name', 'Package')}.java", cleaned
                except Exception as e:
                    logger.error(f"Failed to convert package {package.get('name')}: {e}")
                    return None, None

        results = await asyncio.gather(*[convert_single(p) for p in packages], return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                continue
            filename, java_code = result
            if filename and java_code and java_code.strip():
                java_files[filename] = java_code
        return java_files

    async def _convert_sql_to_repositories(self, sql_queries: List[Dict[str, Any]],
                                           context: Dict[str, Any]) -> Dict[str, str]:
        java_files = {}
        table_queries: Dict[str, List] = {}
        for query in sql_queries:
            for table in query.get('tables', []):
                table_queries.setdefault(table, []).append(query)

        async def convert_table(table_name: str, queries: List) -> Tuple[Optional[str], Optional[str]]:
            async with self._get_semaphore():
                try:
                    table_context = {
                        **context,
                        'entity': f"{table_name}Entity",
                        'table': table_name,
                        'columns': self._extract_columns_from_queries(queries),
                    }
                    combined_sql = "\n\n".join([q.get('query', '') for q in queries])
                    prompt = self.prompt_template.get_prompt(
                        'sql_to_repository', {'sql_statements': [{'text': combined_sql}]}, table_context
                    )
                    java_code = await self._generate_with_retries(prompt)
                    cleaned = self._clean_java_code(java_code)
                    return f"{table_name}Repository.java", cleaned
                except Exception as e:
                    logger.error(f"Failed to convert SQL for table {table_name}: {e}")
                    return None, None

        results = await asyncio.gather(
            *[convert_table(t, q) for t, q in table_queries.items()], return_exceptions=True
        )
        for result in results:
            if isinstance(result, Exception):
                continue
            filename, java_code = result
            if filename and java_code and java_code.strip():
                java_files[filename] = java_code
        return java_files

    def _build_fix_prompt(self, code: str, errors: List[str], context: Dict[str, Any]) -> str:
        return f"""Fix this Java Spring Boot code to compile correctly.

Errors:
{chr(10).join(errors)}

Code:
{code}

STRICT FIX RULES:
- Use ONLY these entities: {context.get('entity_names', [])}
- Use ONLY these repositories: {context.get('repository_names', [])}
- Fix ALL missing imports
- Fix type mismatches: BigDecimal for NUMBER(p,s) decimal columns, Long for IDs/counts
- NEVER use Double or Float for monetary/decimal values — always BigDecimal
- Service methods must return void — NEVER return an entity type
- NEVER use EntityManager, @PersistenceContext, or createNativeQuery in a @Service class
- ALWAYS inject the repository with @Autowired and use it for all DB operations
- Do NOT generate duplicate case labels in switch statements
- File MUST end with the closing brace — nothing after it (no comments, no imports, no @Entity)
- Repository interfaces: each method gets EXACTLY ONE @Modifying and ONE @Transactional
- @Param annotation goes BEFORE the Java type: @Param("id") Long id — NOT Long @Param("id") id
- Implement ALL switch cases (INSERT/UPDATE/DELETE/SELECT) with real repository calls — no TODOs
- Entity classes have ONLY no-arg constructors — never new EntityClass(arg1, arg2, ...)
- For INSERT: call repository insertXxx() method; do NOT pass the PK — it's Oracle-sequence-generated
- For UPDATE: findById().orElseThrow(), then setters, then save() — no generic .update() method
- FK fields are entity OBJECTS, not Long IDs: use setCustomersEntity(entity) not setCustomerId(id)
- Entity/Repository names are PascalCase — NEVER ALLCAPS (CustomersEntity not CUSTOMERSEntity)
- Do NOT import non-existent classes: no CrudRepository<Object,Long>, no ALLCAPS entity imports

Return ONLY the corrected complete Java code. No markdown, no explanations.
"""

    def _extract_sql_queries(self, ast_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        sql_queries = []
        for section in ('procedures', 'functions', 'triggers'):
            for obj in ast_results.get(section, []):
                for statement in obj.get('statements', []):
                    if statement.get('type') == 'sql_statement':
                        query_text = statement.get('text', '')
                        tables = statement.get('tables', []) or self._infer_tables_from_sql(query_text)
                        sql_queries.append({'query': query_text, 'tables': tables, 'type': section})
        return sql_queries

    def _infer_tables_from_sql(self, sql_text: str) -> List[str]:
        if not sql_text:
            return []
        tables = set()
        blocked = {"TABLE", "DUAL"}
        patterns = [
            r"\bfrom\s+([a-zA-Z_][a-zA-Z0-9_$#.]*)",
            r"\bjoin\s+([a-zA-Z_][a-zA-Z0-9_$#.]*)",
            r"\bupdate\s+([a-zA-Z_][a-zA-Z0-9_$#.]*)",
            r"\binsert\s+into\s+([a-zA-Z_][a-zA-Z0-9_$#.]*)",
            r"\bdelete\s+from\s+([a-zA-Z_][a-zA-Z0-9_$#.]*)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, sql_text, flags=re.IGNORECASE):
                table_name = match.group(1).split('.')[-1]
                if table_name and table_name.upper() not in blocked:
                    tables.add(table_name)
        return list(tables)

    def _extract_columns_from_queries(self, queries: List[Dict[str, Any]]) -> List[str]:
        columns = set()
        for query in queries:
            query_text = query.get('query', '').upper()
            if 'SELECT' in query_text and 'FROM' in query_text:
                select_part = query_text.split('FROM')[0]
                if 'SELECT' in select_part:
                    cols = select_part.split('SELECT')[1].strip()
                    for col in cols.split(','):
                        col = col.strip()
                        if col and col != '*':
                            columns.add(col)
        return list(columns)

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate_java_code(self, code: str) -> List[str]:
        errors = []
        if not code or not code.strip():
            errors.append("Empty code generated")
            return errors

        # LCE-11 FIX: scope @PostMapping check to the method immediately following the annotation
        post_method_match = re.search(
            r'@PostMapping[^\n]*\n\s*public\s+\S+\s+\w+\s*\(\s*\)',
            code
        )
        if post_method_match:
            errors.append("POST method missing @RequestBody or parameters")

        # LCE-10 FIX: empty method = braces with ONLY whitespace between them
        if re.search(r'public\s+[\w<>\[\], ?]+\s+\w+\s*\([^)]*\)\s*\{\s*\}', code):
            errors.append("Empty method body detected")

        if not re.search(r'\bclass\s+\w+', code):
            errors.append("No class definition found")

        if "@RestController" in code and "import org.springframework.web.bind.annotation" not in code:
            errors.append("Missing Spring Web imports")

        if "class " in code and any(x in code for x in ["Controller", "Service", "Repository"]):
            if not any(x in code for x in ["@Service", "@RestController", "@Repository"]):
                errors.append("Spring stereotype annotation missing")

        if re.search(r'return\s+ResponseEntity\.ok\s*\(\s*\w+\.\w+\(', code):
            errors.append("CRITICAL: Controller returning service call directly")

        # FIX: detect EntityManager / native query usage in a service — must use repository instead
        if 'createNativeQuery' in code or (
            '@PersistenceContext' in code and '@Service' in code
        ):
            errors.append(
                "Service uses EntityManager/createNativeQuery — MUST use injected @Autowired repository instead"
            )

        return errors

    def _force_fix_controller(self, code: str) -> str:
        pattern = re.compile(r'return\s+ResponseEntity\.ok\s*\(\s*(\w+)\.(\w+)\((.*?)\)\s*\);')

        def replacer(match: re.Match) -> str:
            service = match.group(1)
            method = match.group(2)
            params = match.group(3)
            return f"{service}.{method}({params});\n        return ResponseEntity.ok(\"Success\");"

        return pattern.sub(replacer, code)

    # ── Code cleaning ─────────────────────────────────────────────────────────

    def _clean_java_code(self, java_code: str) -> str:
        if not java_code:
            return ""

        text = java_code.strip()

        fence_match = re.search(r"```(?:java)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fence_match:
            text = fence_match.group(1).strip()

        package_index = text.find("package ")
        if package_index != -1:
            text = text[package_index:]

        lines = text.splitlines()

        package_lines = list(dict.fromkeys(l.strip() for l in lines if l.strip().startswith("package ")))
        import_lines = list(dict.fromkeys(l.strip() for l in lines if l.strip().startswith("import ")))

        # LCE-13 FIX: if multiple public classes found, keep only the first one
        decl_pattern = re.compile(r"^\s*(public\s+)?(class|interface|enum|record)\s+(\w+)")
        class_starts = []
        for i, line in enumerate(lines):
            m = decl_pattern.search(line)
            if m:
                class_starts.append((i, m.group(3)))

        if len(class_starts) > 1:
            # Keep only the primary (first) class
            second_class_start = class_starts[1][0]
            lines = lines[:second_class_start]
            logger.debug("LCE-13: truncated secondary class starting at line %d", second_class_start)

        start_idx = None
        for i, line in enumerate(lines):
            if decl_pattern.search(line):
                start_idx = i
                break

        if start_idx is not None:
            body = lines[start_idx:]
            cleaned = "\n".join(package_lines + import_lines + body).strip()
            # SBG-27 / LCE prompt FIX: strip any content the LLM appended after the
            # class/interface closing brace (placeholder imports, bare @Entity, comments).
            cleaned = self._strip_trailing_garbage(cleaned)
            return self._ensure_spring_stereotype(cleaned)

        text = self._strip_trailing_garbage(text)
        return self._ensure_spring_stereotype(text)


    def _strip_trailing_garbage(self, code: str) -> str:
        """
        LCE prompt FIX: Strip any content appended after the outermost class/interface
        closing brace. The LLM occasionally outputs placeholder imports, bare @Entity
        annotations, or comments after the closing }}, which are illegal Java syntax.

        Tracks brace depth from the first top-level type declaration and returns only
        through (and including) the final closing brace of that type.
        """
        if not code:
            return code
        lines = code.splitlines(keepends=True)
        depth = 0
        in_type = False
        close_line = -1
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not in_type:
                if re.search(r'\b(class|interface|enum|record)\b', stripped):
                    in_type = True
            if in_type:
                depth += line.count('{') - line.count('}')
                if depth <= 0 and '{' in ''.join(lines[:i+1]):
                    close_line = i
                    break
        if close_line >= 0 and close_line < len(lines) - 1:
            return ''.join(lines[:close_line + 1]).rstrip()
        return code

    def _ensure_spring_stereotype(self, code: str) -> str:
        if not code:
            return code
        if "@Service" in code or "@RestController" in code or "@Repository" in code:
            return code

        class_match = re.search(r'^\s*(public\s+)?class\s+([A-Za-z_]\w+)', code, flags=re.MULTILINE)
        if not class_match:
            return code
        class_name = class_match.group(2)

        if class_name.endswith("Controller"):
            annotation = "@RestController"
            import_line = "import org.springframework.web.bind.annotation.RestController;"
        elif class_name.endswith("Repository"):
            annotation = "@Repository"
            import_line = "import org.springframework.stereotype.Repository;"
        else:
            annotation = "@Service"
            import_line = "import org.springframework.stereotype.Service;"

        lines = code.splitlines()
        package_index = None
        last_import_index = None
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("package "):
                package_index = idx
            if stripped.startswith("import "):
                last_import_index = idx

        if import_line and import_line not in lines:
            insert_at = (last_import_index + 1) if last_import_index is not None else (
                package_index + 1 if package_index is not None else 0
            )
            lines.insert(insert_at, import_line)

        for idx, line in enumerate(lines):
            if re.search(r'^\s*(public\s+)?class\s+' + re.escape(class_name) + r'\b', line):
                if idx == 0 or lines[idx - 1].strip() != annotation:
                    lines.insert(idx, annotation)
                break

        return "\n".join(lines).strip()

    # ── Fallback generators ───────────────────────────────────────────────────

    def _generate_procedure_fallback(self, procedure: Dict[str, Any], context: Dict[str, Any],
                                     error: Exception) -> Tuple[Optional[str], Optional[str]]:
        try:
            procedure_name = procedure.get('name', 'Procedure')
            service_name = self._derive_service_name(procedure_name)
            method_name = self._to_camel_case(procedure_name)
            package_name = context.get('package_name', 'com.company.project')
            in_params = [p for p in procedure.get('parameters', []) if p.get('mode', 'IN').upper() == 'IN']
            out_params = [p for p in procedure.get('parameters', []) if p.get('mode', 'IN').upper() != 'IN']
            entity_name = self._derive_entity_name_from_name(procedure_name)
            entity_var = self._lower_first(entity_name)
            repository_name = f"{entity_name}Repository"
            repository_var = self._lower_first(repository_name)

            method_signature = ", ".join(
                f"{self._map_plsql_type_to_java(p.get('type'), p.get('name'), p.get('mode'))} "
                f"{self._to_camel_case(p.get('name', 'param'))}"
                for p in in_params
            )

            return_type = "void"
            if len(out_params) == 1:
                return_type = self._map_plsql_type_to_java(
                    out_params[0].get('type'), out_params[0].get('name'), out_params[0].get('mode')
                )

            # LCE-7 FIX: build setters from IN parameters directly, bypass entity_fields
            setter_lines = []
            for param in in_params:
                field_name = self._normalize_field_name(param.get('name', 'param'))
                setter_name = field_name[:1].upper() + field_name[1:]
                value_name = self._to_camel_case(param.get('name', 'param'))
                setter_lines.append(f"        {entity_var}.set{setter_name}({value_name}); // set if field exists")
            setters = "\n".join(setter_lines) if setter_lines else "        // No IN parameters to set"

            return_stmt = f"        return {self._default_value_for_java_type(return_type)};" if return_type != "void" else ""

            java_code = f"""package {package_name}.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class {service_name} {{

    @Autowired
    private {repository_name} {repository_var};

    @Transactional
    public {return_type} {method_name}({method_signature}) {{
        // Deterministic fallback — LLM error: {self._escape_java_comment(str(error))}
        {entity_name} {entity_var} = new {entity_name}();
{setters}
        {repository_var}.save({entity_var});
{return_stmt}
    }}
}}
"""
            return f"{service_name}.java", java_code
        except Exception as fallback_error:
            logger.error(f"Fallback generation failed for {procedure.get('name')}: {fallback_error}")
            return None, None

    def _generate_function_fallback(self, function: Dict[str, Any], context: Dict[str, Any],
                                    error: Exception) -> Tuple[Optional[str], Optional[str]]:
        try:
            function_name = function.get('name', 'Function')
            service_name = self._derive_service_name(function_name)
            method_name = self._to_camel_case(function_name)
            package_name = context.get('package_name', 'com.company.project')
            return_type = self._map_plsql_type_to_java(function.get('return_type'), function_name, 'OUT')
            parameters = [p for p in function.get('parameters', []) if p.get('mode', 'IN').upper() == 'IN']
            method_signature = ", ".join(
                f"{self._map_plsql_type_to_java(p.get('type'), p.get('name'), p.get('mode'))} "
                f"{self._to_camel_case(p.get('name', 'param'))}"
                for p in parameters
            )
            java_code = f"""package {package_name}.service;

import org.springframework.stereotype.Service;

@Service
public class {service_name} {{

    public {return_type} {method_name}({method_signature}) {{
        // Fallback stub — LLM error: {self._escape_java_comment(str(error))}
        return {self._default_value_for_java_type(return_type)};
    }}
}}
"""
            return f"{service_name}.java", java_code
        except Exception as fb_err:
            logger.error(f"Function fallback failed for {function.get('name')}: {fb_err}")
            return None, None

    # ── Type / name utilities ─────────────────────────────────────────────────

    def _derive_service_name(self, object_name: str) -> str:
        base_name = self._to_pascal_case(object_name)
        return base_name if base_name.endswith('Service') else f"{base_name}Service"

    def _derive_entity_name_from_name(self, object_name: str) -> str:
        tokens = [t for t in re.split(r'[^A-Za-z0-9]+', object_name or '') if t]
        if tokens and tokens[0].lower() in {'process', 'create', 'update', 'delete', 'save', 'get', 'find', 'load'}:
            tokens = tokens[1:]
        base_name = ''.join(t.capitalize() for t in tokens) or 'Record'
        if base_name.endswith('Service'):
            base_name = base_name[:-7] or 'Record'
        return base_name

    def _normalize_field_name(self, value: str) -> str:
        normalized = re.sub(r'^(p|v)_+', '', value or '', flags=re.IGNORECASE)
        normalized = normalized.strip('_')
        return self._to_camel_case(normalized or value or 'value')

    def _map_plsql_type_to_java(self, plsql_type: Optional[str], field_name: Optional[str] = None,
                                 mode: Optional[str] = None) -> str:
        type_name = (plsql_type or '').upper()
        normalized_name = (field_name or '').lower()
        if 'VARCHAR' in type_name or 'CHAR' in type_name or 'CLOB' in type_name or normalized_name.endswith('status'):
            return 'String'
        if 'DATE' in type_name or 'TIMESTAMP' in type_name:
            return 'LocalDateTime'
        if 'BOOLEAN' in type_name:
            return 'Boolean'
        if 'NUMBER' in type_name:
            # LCE-8 FIX: NUMBER with scale (e.g. NUMBER(10,2)) -> BigDecimal for decimal precision.
            # NUMBER without scale used as an ID -> Long.
            # NUMBER without scale used as any other numeric param -> Long (not Integer).
            # Rationale: JPA repository keys are always Long; using Integer for IN params
            # caused 'incompatible types: Integer cannot be converted to Long' compile errors
            # when the param was passed to findById/deleteById/existsById.
            if ',' in type_name:
                return 'BigDecimal'
            if normalized_name.endswith('id') or normalized_name.endswith('_id'):
                return 'Long'
            # Default non-ID NUMBER to Long for consistency with JPA key type
            return 'Long'
        return 'String'

    def _default_value_for_java_type(self, java_type: str) -> str:
        defaults = {
            'String': 'null', 'Long': 'null', 'Integer': '0',
            'Double': '0.0', 'Float': '0.0f', 'Boolean': 'false',
            'BigDecimal': 'java.math.BigDecimal.ZERO',
            'LocalDateTime': 'java.time.LocalDateTime.now()',
            'void': '',
        }
        return defaults.get(java_type, 'null')

    def _to_pascal_case(self, value: str) -> str:
        # LCE-FIX A1: use .capitalize() not p[:1].upper() + p[1:] so that
        # ALLCAPS input like 'CUSTOMERS' becomes 'Customers' not 'CUSTOMERS'.
        # .capitalize() lowercases the whole word then uppercases the first char.
        parts = [p for p in re.split(r'[^A-Za-z0-9]+', value or '') if p]
        return ''.join(p.capitalize() for p in parts) or 'Generated'

    def _to_camel_case(self, value: str) -> str:
        pascal = self._to_pascal_case(value)
        return pascal[:1].lower() + pascal[1:] if pascal else 'generated'

    def _lower_first(self, value: str) -> str:
        return value[:1].lower() + value[1:] if value else value

    def _escape_java_comment(self, value: str) -> str:
        return (value or '').replace('*/', '* /').replace('\r', ' ').replace('\n', ' ')

    # ── Stats / suggestions ───────────────────────────────────────────────────

    def get_conversion_stats(self) -> Dict[str, Any]:
        return {
            'provider': self.provider.get_model_info(),
            # LCE-15 FIX: cache is now real
            'cache_size': len(self._conversion_cache),
            'concurrent_requests': self.max_concurrent_requests
        }

    async def suggest_dependencies(self, context: Dict[str, Any]) -> List[Dict[str, str]]:
        prompt = (
            "You are a senior Java Spring Boot architect. "
            "Given the PL/SQL discovery context below, recommend OPTIONAL dependencies. "
            "Return JSON only as an array of objects with keys `name`, `reason`, and `coordinate` "
            "(groupId:artifactId). No prose, no markdown.\n\n"
            f"Context JSON:\n{json.dumps(context, ensure_ascii=True, indent=2)}"
        )
        try:
            raw = await self.provider.generate_code(prompt, max_tokens=400, temperature=0.2)
        except Exception as exc:
            logger.error(f"Dependency suggestion failed: {exc}")
            return []
        return self._parse_dependency_suggestions(raw or "")

    async def repair_generated_project(self, repair_context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.repair_provider:
            return {"success": False, "reason": "repair_provider_disabled", "files": []}

        prompt = self._build_repair_prompt(repair_context)
        try:
            raw = await self.repair_provider.generate_code(
                prompt,
                max_tokens=int(self.config.get('backup_llm', {}).get('max_tokens', 6000)),
                temperature=float(self.config.get('backup_llm', {}).get('temperature', 0.0)),
            )
        except Exception as exc:
            logger.error("Backup LLM repair call failed: %s", exc)
            return {"success": False, "reason": str(exc), "files": []}

        parsed = self._parse_repair_response(raw or "")
        if not parsed.get("files"):
            parsed["success"] = False
            parsed.setdefault("reason", "no_files_returned")
        return parsed

    def _build_repair_prompt(self, repair_context: Dict[str, Any]) -> str:
        return (
            "You are repairing a generated Java Spring Boot project so it compiles successfully.\n"
            "Return JSON only. No markdown. No prose outside JSON.\n\n"
            "Required schema:\n"
            "{\n"
            "  \"summary\": \"short reasoned summary\",\n"
            "  \"files\": [\n"
            "    {\n"
            "      \"path\": \"relative/path/from/project/root\",\n"
            "      \"content\": \"full replacement file content\"\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "1. Only include files you are changing.\n"
            "2. Every file entry must contain the ENTIRE replacement file content.\n"
            "3. Do not invent files unless required for compilation.\n"
            "4. Keep package names and project structure consistent.\n"
            "5. Fix the reported build/compiler errors directly.\n"
            "6. If one fix requires import changes or method signature changes, include them in the full file content.\n"
            "7. Prefer minimal edits.\n\n"
            f"Repair context JSON:\n{json.dumps(repair_context, ensure_ascii=True, indent=2)}"
        )

    def _parse_repair_response(self, raw: str) -> Dict[str, Any]:
        text = (raw or "").strip()
        if not text:
            return {"success": False, "reason": "empty_response", "files": []}

        fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fence_match:
            text = fence_match.group(1).strip()

        decoder = json.JSONDecoder()
        parsed = None
        for token in ("{", "["):
            start = text.find(token)
            if start == -1:
                continue
            try:
                parsed, _ = decoder.raw_decode(text[start:])
                break
            except Exception:
                parsed = None

        if isinstance(parsed, list):
            parsed = {"summary": "", "files": parsed}
        if not isinstance(parsed, dict):
            return {"success": False, "reason": "invalid_json", "files": []}

        files = []
        for item in parsed.get("files", []):
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            content = item.get("content")
            if isinstance(path, str) and path.strip() and isinstance(content, str):
                files.append({"path": path.strip().replace("\\", "/"), "content": content})

        return {
            "success": bool(files),
            "summary": parsed.get("summary", ""),
            "files": files,
        }

    def _parse_dependency_suggestions(self, raw: str) -> List[Dict[str, str]]:
        if not raw:
            return []
        text = raw.strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fence_match:
            text = fence_match.group(1).strip()

        decoder = json.JSONDecoder()
        parsed = None
        for token in ("[", "{"):
            start = text.find(token)
            if start == -1:
                continue
            try:
                parsed, _ = decoder.raw_decode(text[start:])
                break
            except Exception:
                parsed = None

        if isinstance(parsed, dict) and isinstance(parsed.get("suggestions"), list):
            parsed = parsed.get("suggestions")
        if not isinstance(parsed, list):
            return []

        suggestions: List[Dict[str, str]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            reason = item.get("reason")
            coordinate = item.get("coordinate") or item.get("mavenCoordinate")
            if isinstance(name, str) and isinstance(reason, str):
                payload = {"name": name.strip(), "reason": reason.strip()}
                if isinstance(coordinate, str) and coordinate.strip():
                    payload["coordinate"] = coordinate.strip()
                suggestions.append(payload)
        return suggestions


def create_llm_engine(config: Dict[str, Any]) -> LLMConversionEngine:
    return LLMConversionEngine(config)
