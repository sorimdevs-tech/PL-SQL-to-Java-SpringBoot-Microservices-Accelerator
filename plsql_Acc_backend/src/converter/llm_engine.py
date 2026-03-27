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
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass
from abc import ABC, abstractmethod
import logging

from ..utils.logger import get_logger
from ..utils.config import get_config_value
from ..utils.naming import normalize_column_name, to_pascal_case

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
            'procedure_to_service': self._get_strict_procedure_template(),
            'function_to_service': self._get_strict_function_template(),
            'trigger_to_event': self._get_trigger_template(),
            'package_to_class': self._get_strict_package_template(),
            'sql_to_repository': self._get_strict_repository_template(),
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
        format_context.setdefault('semantic_summary', '{}')
        format_context.setdefault('entity_sources', '(none)')
        format_context.setdefault('repository_sources', '(none)')
        format_context.setdefault('validation_feedback', '(none)')
        format_context.setdefault('object_name', '')
        format_context.setdefault('object_type', '')
        format_context.setdefault('operations', [])
        format_context.setdefault('lookup_keys', [])

        # LCE-6 FIX: serialize entity_fields as readable text, not raw Python dict repr
        raw_entity_fields = format_context.get('entity_fields', {})
        if isinstance(raw_entity_fields, dict) and raw_entity_fields:
            format_context['entity_fields'] = '\n'.join(
                f"{entity}: {', '.join(fields)}"
                for entity, fields in raw_entity_fields.items()
            )
        else:
            format_context['entity_fields'] = '(none — skip all entity setters)'

        format_context['entity_sources'] = self._format_code_context(format_context.get('entity_sources'))
        format_context['repository_sources'] = self._format_code_context(format_context.get('repository_sources'))
        format_context['validation_feedback'] = self._format_validation_feedback(
            format_context.get('validation_feedback')
        )
        format_context['semantic_summary'] = self._format_semantics(plsql_ast, format_context.get('semantic_summary'))
        format_context['plsql_code'] = self._format_raw_plsql(plsql_ast)
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
13. NEVER use undefined placeholder variables such as name, email, amount, status,
    orderId, customerId unless those variables are actually declared in the method body
    or are method parameters. Every variable referenced in a repository call must exist.
14. For UPDATE: findById(id).orElseThrow(), then setters, then save(entity).
    Do NOT call a generic .update() method — it does not exist.
15. When reading entity values, use the REAL generated accessor names from the entity
    fields. Example: customerId field -> getCustomerId(), NOT getId().
16. Do NOT call setters/getters for fields that do not exist on the entity.
    WRONG: payment.setStatus("UPDATED") when PaymentsEntity has no status field.
15. FK fields in entities are mapped as entity OBJECTS, not Long IDs.
    WRONG: order.setCustomerId(pCustomerId)   // no such setter exists
    RIGHT: CustomersEntity c = customersRepository.findById(pCustomerId).orElseThrow(...);
           order.setCustomersEntity(c);
17. The service method return type MUST be void. The controller handles the response.
18. Use BigDecimal for ALL decimal/monetary NUMBER columns. NEVER use Double or Float.
    NUMBER(10,2) -> BigDecimal.   Any NUMBER(p,s) where s > 0 -> BigDecimal.
19. Entity and Repository class names are PascalCase. NEVER use ALLCAPS.
    WRONG: CUSTOMERSEntity, ORDERSEntity, PAYMENTSEntity, CUSTOMERSRepository
    RIGHT: CustomersEntity, OrdersEntity, PaymentsEntity, CustomersRepository
20. Import only classes that actually exist in the project.
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
- NEVER reference undeclared placeholder variables in repository/service calls.
- Use only real entity accessors derived from actual fields: getCustomerId() not getId().
- Never call a setter for a field that is not present on the entity.
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

    def _get_strict_procedure_template(self) -> str:
        return """
Convert the following PL/SQL object to one Java Spring Boot service class.

SOURCE OF TRUTH:
{plsql_code}

EXTRACTED SEMANTICS (supplemental only; raw PL/SQL wins on conflicts):
{semantic_summary}

ALREADY GENERATED ENTITIES:
{entity_sources}

ALREADY GENERATED REPOSITORIES:
{repository_sources}

Allowed Entity Fields:
{entity_fields}

Validation feedback from prior failed attempts:
{validation_feedback}

MANDATORY CONVERSION RULES:
1. Preserve behavior, not syntax. Raw PL/SQL execution semantics are authoritative.
2. CURSOR ... FOR UPDATE SKIP LOCKED must map to chunked processing with explicit locking semantics.
3. Preserve cursor WHERE filters in repository methods. Never drop filter predicates.
4. BULK COLLECT LIMIT must become a batch loop with explicit chunk size handling.
5. SQL aggregations (SUM/COUNT/NVL/GROUP BY) must become repository aggregation queries. Never use entity fetch for aggregation.
6. NVL(..., 0) must map to null-safe defaults (e.g., Optional.orElse(BigDecimal.ZERO)).
7. MERGE must become explicit UPSERT: find existing, update branch, insert branch.
8. Preserve audit fields during UPSERT (created_at/updated_at behavior must match source intent).
9. sequence.NEXTVAL must map to sequence-backed ID generation or explicit sequence access.
10. SAVEPOINT + conditional COMMIT/ROLLBACK must be simulated with per-batch transaction boundaries
    (REQUIRES_NEW or TransactionTemplate), never one global transaction for the whole run.
11. Business exception handlers and WHEN OTHERS must map to separate catch blocks.
12. INSERTs into audit/error tables must be preserved as explicit persistence calls.
13. Business validation rules (e.g., balance < 0 THEN RAISE) must be explicit checks that throw domain exceptions.
14. State variables such as v_has_error must be scoped/reset per batch as required by behavior.
15. Do not simplify loops, transaction branches, or side effects. Maintain data-flow order and outcomes.

FINAL SELF-CHECK BEFORE OUTPUT:
- Are all WHERE conditions preserved?
- Are all INSERT/UPDATE/MERGE side effects preserved (including audit/error logs)?
- Are aggregation paths query-based and null-safe?
- Are batch/transaction boundaries equivalent to PL/SQL intent?
- Are custom/business and system exceptions split correctly?
"""

    def _get_strict_function_template(self) -> str:
        return """
Convert the following PL/SQL function to one Java Spring Boot service class.

SOURCE OF TRUTH:
{plsql_code}

EXTRACTED SEMANTICS (supplemental only; raw PL/SQL wins on conflicts):
{semantic_summary}

ALREADY GENERATED ENTITIES:
{entity_sources}

ALREADY GENERATED REPOSITORIES:
{repository_sources}

Allowed Entity Fields:
{entity_fields}

Validation feedback from prior failed attempts:
{validation_feedback}

Rules:
- Raw PL/SQL is authoritative. Do not invent missing logic.
- Use only the repositories and entity accessors shown above.
- Preserve exception handling, transaction semantics, batching, and MERGE behavior if present.
- Never use EntityManager or native SQL inside the service.
- Output exactly one compilable Java class in package {package_name}.service.
"""

    def _get_strict_package_template(self) -> str:
        return """
Convert the following PL/SQL package to one Java Spring Boot class.

SOURCE OF TRUTH:
{plsql_code}

EXTRACTED SEMANTICS (supplemental only; raw PL/SQL wins on conflicts):
{semantic_summary}

ALREADY GENERATED ENTITIES:
{entity_sources}

ALREADY GENERATED REPOSITORIES:
{repository_sources}

Allowed Entity Fields:
{entity_fields}

Validation feedback from prior failed attempts:
{validation_feedback}

Rules:
- Preserve package member behavior from the raw PL/SQL package body.
- Do not invent repository methods or entity fields.
- Output exactly one compilable Java class in package {package_name}.service.
"""

    def _get_strict_repository_template(self) -> str:
        return """
Convert the following PL/SQL-derived SQL behavior to one Spring Data repository interface.

SOURCE OF TRUTH:
{plsql_code}

EXTRACTED SEMANTICS (supplemental only; raw PL/SQL wins on conflicts):
{semantic_summary}

ENTITY SOURCE:
{entity_sources}

Validation feedback from prior failed attempts:
{validation_feedback}

Repository target:
- Table: {table}
- Entity: {entity}
- Operations: {operations}
- Lookup keys: {lookup_keys}
- Columns: {columns}
- Package: {package_name}

MANDATORY RULES:
1. Output exactly one compilable repository interface.
2. Create only methods required by the SQL operations in the source PL/SQL.
3. Never invent methods unrelated to the extracted operations.
4. If MERGE exists for this table, expose the repository methods needed for UPSERT support
   such as existence lookup on the merge key and any required custom query methods.
5. If FOR UPDATE SKIP LOCKED or cursor pagination is present, generate the corresponding
   custom repository method instead of ignoring the locking semantics.
6. Every named query parameter must have a matching @Param annotation before the Java type.
7. The file must end with the interface closing brace and contain no markdown or explanations.
"""

    def _format_raw_plsql(self, payload: Dict[str, Any]) -> str:
        if isinstance(payload, dict):
            raw_plsql = payload.get('raw_plsql')
            if isinstance(raw_plsql, str) and raw_plsql.strip():
                return raw_plsql.strip()
        return self._format_plsql_ast(payload)

    def _format_semantics(self, payload: Dict[str, Any], explicit_summary: Any) -> str:
        if isinstance(explicit_summary, str) and explicit_summary.strip() and explicit_summary.strip() != '{}':
            return explicit_summary
        if isinstance(payload, dict):
            semantics = {
                key: value
                for key, value in payload.items()
                if key not in {'raw_plsql', 'body'}
            }
            if semantics:
                return json.dumps(semantics, ensure_ascii=True, default=str, indent=2)
        return '{}'

    def _format_code_context(self, value: Any) -> str:
        if isinstance(value, str):
            return value.strip() or '(none)'
        if isinstance(value, dict):
            blocks = []
            for filename, code in sorted(value.items()):
                blocks.append(f"// File: {filename}\n{str(code).strip()}")
            return "\n\n".join(blocks) if blocks else '(none)'
        return '(none)'

    def _format_validation_feedback(self, value: Any) -> str:
        if isinstance(value, str):
            return value.strip() or '(none)'
        if isinstance(value, list):
            return "\n".join(f"- {item}" for item in value) or '(none)'
        if isinstance(value, dict):
            lines = []
            for key, items in sorted(value.items()):
                lines.append(f"{key}:")
                if isinstance(items, list):
                    lines.extend(f"- {item}" for item in items)
                else:
                    lines.append(f"- {items}")
            return "\n".join(lines) if lines else '(none)'
        return '(none)'

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

    def _derive_entity_name_from_table(self, table_name: str, entities: Dict[str, str]) -> str:
        expected = f"{self._to_pascal_case(table_name)}Entity"
        if f"{expected}.java" in entities:
            return expected
        table_key = re.sub(r'[^A-Za-z0-9]', '', table_name or '').lower()
        for filename in entities:
            class_name = filename.replace('.java', '')
            if re.sub(r'[^A-Za-z0-9]', '', class_name.replace('Entity', '')).lower() == table_key:
                return class_name
        return expected

    def _derive_repository_name_from_entity(self, entity_name: str) -> str:
        base = entity_name[:-6] if entity_name.endswith('Entity') else entity_name
        return f"{base}Repository"

    def _build_entity_field_map(self, entities: Dict[str, str]) -> Dict[str, List[str]]:
        field_map: Dict[str, List[str]] = {}
        for filename, code in entities.items():
            class_name = filename.replace('.java', '')
            fields = re.findall(r'private\s+(?!static)(?:[\w<>?,\s]+)\s+(\w+);', code)
            if fields:
                field_map[class_name] = fields
        return field_map

    def _select_related_entities(self, unit: Dict[str, Any], entities: Dict[str, str]) -> Dict[str, str]:
        related: Dict[str, str] = {}
        for table_name in unit.get('tables_used', []):
            entity_name = self._derive_entity_name_from_table(table_name, entities)
            filename = f"{entity_name}.java"
            if filename in entities:
                related[filename] = entities[filename]
        return related

    def _select_related_repositories(
        self,
        unit: Dict[str, Any],
        entities: Dict[str, str],
        repositories: Dict[str, str],
    ) -> Dict[str, str]:
        related: Dict[str, str] = {}
        for table_name in unit.get('tables_used', []):
            entity_name = self._derive_entity_name_from_table(table_name, entities)
            repo_name = f"{self._derive_repository_name_from_entity(entity_name)}.java"
            if repo_name in repositories:
                related[repo_name] = repositories[repo_name]
        return related

    def _derive_service_filename(self, unit: Dict[str, Any]) -> str:
        return f"{self._derive_service_name(unit.get('name', 'Generated'))}.java"

    def _is_pseudo_table_name(self, table_name: str) -> bool:
        normalized = str(table_name or "").strip().upper()
        if not normalized:
            return True
        normalized = normalized.strip('"`')
        normalized = normalized.split(".")[-1]
        return normalized in {"DUAL"}

    def _resolve_entity_field(self, column_name: str, entity_field_types: Dict[str, str]) -> Optional[str]:
        normalized_column = normalize_column_name(column_name).lower()
        for field_name in (entity_field_types or {}).keys():
            if normalize_column_name(field_name).lower() == normalized_column:
                return field_name
        return None

    def _default_java_literal_for_type(self, java_type: str) -> str:
        normalized = (java_type or "").strip()
        primitive_defaults = {
            "long": "0L",
            "int": "0",
            "double": "0.0d",
            "float": "0.0f",
            "boolean": "false",
            "short": "(short) 0",
            "byte": "(byte) 0",
            "char": "'\\0'",
        }
        return primitive_defaults.get(normalized, "null")

    def _resolve_lookup_argument_expression(
        self,
        column_name: str,
        driving_fields: Dict[str, str],
        param_name_map: Dict[str, str],
        expected_type: str,
        param_specs: Optional[List[Dict[str, str]]] = None,
        prebound_var: Optional[str] = None,
        prebound_column: Optional[str] = None,
    ) -> str:
        normalized_column = normalize_column_name(column_name)
        if prebound_var and prebound_column:
            if normalize_column_name(prebound_column).lower() == normalized_column.lower():
                return prebound_var

        matched_field = self._resolve_entity_field(column_name, driving_fields)
        if matched_field:
            getter = f"get{matched_field[:1].upper() + matched_field[1:]}"
            return f"row.{getter}()"

        mapped_param = param_name_map.get(str(column_name).upper()) or param_name_map.get(normalized_column.upper())
        if mapped_param:
            return mapped_param

        if param_specs:
            inferred = self._best_param_for_field(column_name, param_specs, expected_type)
            if inferred and inferred.get("java_name"):
                return str(inferred["java_name"])

        return self._default_java_literal_for_type(expected_type)

    def _resolve_parameter_for_field(self, field_name: str, param_name_map: Dict[str, str]) -> str:
        normalized = normalize_column_name(field_name)
        return (
            param_name_map.get(str(field_name).upper())
            or param_name_map.get(normalized.upper())
            or ""
        )

    def _canonical_name_token(self, value: str) -> str:
        token = normalize_column_name(value or "").lower()
        for prefix in ("aux", "tmp", "var", "in", "out", "io", "p", "l", "v"):
            if token.startswith(prefix) and len(token) > len(prefix) + 2:
                token = token[len(prefix):]
                break
        return token

    def _collect_service_parameter_specs(self, unit: Dict[str, Any]) -> List[Dict[str, str]]:
        specs: List[Dict[str, str]] = []
        for param in unit.get('input_parameters', []) or []:
            raw_name = str(param.get('name', '')).strip()
            if not raw_name:
                continue
            java_name = normalize_column_name(raw_name)
            java_type = self._map_plsql_type_to_java(
                str(param.get('type', '')),
                raw_name,
                str(param.get('direction', 'IN')),
            )
            specs.append(
                {
                    "raw_name": raw_name,
                    "java_name": java_name,
                    "java_type": java_type,
                    "token": self._canonical_name_token(raw_name),
                }
            )
        return specs

    def _types_compatible(self, source_type: str, target_type: str) -> bool:
        source = (source_type or "").strip()
        target = (target_type or "").strip()
        if not source or not target:
            return True
        if source == target:
            return True
        numeric_types = {"Long", "Integer", "Double", "Float", "BigDecimal", "int", "long", "double", "float"}
        if source in numeric_types and target in numeric_types:
            return True
        return False

    def _best_param_for_field(
        self,
        field_name: str,
        param_specs: List[Dict[str, str]],
        expected_type: str = "",
    ) -> Optional[Dict[str, str]]:
        field_token = self._canonical_name_token(field_name)
        if not field_token:
            return None

        best_spec: Optional[Dict[str, str]] = None
        best_score = -1
        field_base = field_token[:-2] if field_token.endswith("id") else field_token
        for spec in param_specs:
            token = str(spec.get("token", "")).lower()
            if not token:
                continue
            if expected_type and not self._types_compatible(str(spec.get("java_type", "")), expected_type):
                continue

            score = -1
            if token == field_token:
                score = 100
            elif token.endswith(field_token) or field_token.endswith(token):
                score = 85
            else:
                token_base = token[:-2] if token.endswith("id") else token
                if field_base and token_base and (field_base in token_base or token_base in field_base):
                    score = 70
                elif field_token.endswith("id") and token.endswith("id"):
                    # Generic ID fallback when no exact semantic key is available.
                    score = 40

            if score > best_score:
                best_score = score
                best_spec = spec
        return best_spec if best_score > 0 else None

    def _build_target_population_lines(
        self,
        target_var: str,
        target_fields: Dict[str, str],
        driving_fields: Dict[str, str],
        param_name_map: Dict[str, str],
    ) -> List[str]:
        lines: List[str] = []
        if not target_fields:
            return lines

        # Prefer copying a value from the current driving row when a matching field exists.
        for field_name in target_fields.keys():
            driving_field = self._resolve_entity_field(field_name, driving_fields)
            if not driving_field:
                continue
            setter = f"set{field_name[:1].upper() + field_name[1:]}"
            getter = f"get{driving_field[:1].upper() + driving_field[1:]}"
            lines.append(f"{target_var}.{setter}(row.{getter}());")
            return lines

        # Then try mapping from procedure/function IN params.
        for field_name in target_fields.keys():
            param_name = self._resolve_parameter_for_field(field_name, param_name_map)
            if not param_name:
                continue
            setter = f"set{field_name[:1].upper() + field_name[1:]}"
            lines.append(f"{target_var}.{setter}({param_name});")
            return lines

        # Last resort: assign a compile-safe default literal for one field.
        for field_name, field_type in target_fields.items():
            setter = f"set{field_name[:1].upper() + field_name[1:]}"
            lines.append(f"{target_var}.{setter}({self._default_java_literal_for_type(field_type)});")
            return lines
        return lines

    def _extract_entity_from_repository_code(self, repository_code: str) -> str:
        match = re.search(
            r"extends\s+JpaRepository\s*<\s*([A-Za-z_][\w$#]*)",
            repository_code or "",
        )
        if match:
            return str(match.group(1)).strip()
        return ""

    def _fallback_binding_from_repositories(
        self,
        repositories: Dict[str, str],
        preferred_tokens: Optional[List[str]] = None,
    ) -> Optional[Dict[str, str]]:
        preferred: Set[str] = set()
        for token in (preferred_tokens or []):
            raw = str(token or "").strip()
            if not raw:
                continue
            normalized = normalize_column_name(raw).upper()
            if normalized:
                preferred.add(normalized)
            for part in re.split(r"[^A-Za-z0-9]+", raw):
                part_normalized = normalize_column_name(part).upper()
                if part_normalized:
                    preferred.add(part_normalized)
        ranked_filenames: List[str] = []
        if preferred:
            for repo_filename in sorted(repositories.keys()):
                repository_name = repo_filename.replace(".java", "")
                if not repository_name.endswith("Repository"):
                    continue
                table_key = repository_name[:-10].upper() if repository_name[:-10] else ""
                normalized_key = normalize_column_name(table_key).upper()
                score = 1 if normalized_key in preferred or any(
                    token in normalized_key or normalized_key in token for token in preferred
                ) else 0
                ranked_filenames.append((score, repo_filename))
            ranked_filenames = [name for _, name in sorted(ranked_filenames, key=lambda item: (-item[0], item[1]))]
        else:
            ranked_filenames = sorted(repositories.keys())
        for repo_filename in ranked_filenames:
            if not repo_filename.endswith(".java"):
                continue
            repository_name = repo_filename.replace(".java", "")
            if not repository_name.endswith("Repository"):
                continue
            entity_name = self._extract_entity_from_repository_code(repositories.get(repo_filename, ""))
            if not entity_name:
                base_name = repository_name[:-10]
                entity_name = f"{base_name}Entity" if base_name else "GeneratedEntity"
            table_key = repository_name[:-10].upper() if repository_name[:-10] else "PRIMARY"
            return {
                "table": table_key,
                "entity": entity_name,
                "repository": repository_name,
                "repository_var": self._lower_first(repository_name),
            }
        return None

    def _validate_repository_interface(self, code: str) -> List[str]:
        errors: List[str] = []
        if not code or not code.strip():
            return ["Empty repository code generated"]
        if 'interface ' not in code:
            errors.append("Repository output does not contain an interface")
        if 'JpaRepository' not in code:
            errors.append("Repository output does not extend JpaRepository")
        if code.count('{') != code.count('}'):
            errors.append("Repository output has unbalanced braces")
        return errors

    async def generate_repositories_from_semantics(
        self,
        source_units: List[Dict[str, Any]],
        entities: Dict[str, str],
        validation_feedback: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, str]:
        # Deterministic repository generation only. No LLM calls are allowed here.
        repositories: Dict[str, str] = {}
        table_specs: Dict[str, Dict[str, Any]] = {}
        entity_field_types = self._extract_entity_field_types(entities)

        for unit in source_units:
            raw_plsql = str(unit.get('raw_plsql', ''))
            lookup_map = unit.get('lookup_keys') or {}
            semantic = unit.get('semantic_analysis') or {}
            semantic_upserts = semantic.get('upsert_operations') or []
            aggregation_refs = semantic.get('aggregation', {}).get('columns', []) or []
            unit_aggregation_tables = {
                str(ref).split('.', 1)[0].strip().upper()
                for ref in aggregation_refs
                if "." in str(ref)
            }
            skip_locked_tables = {
                str(table).upper()
                for table in (unit.get('skip_locked_tables') or [])
                if table and not self._is_pseudo_table_name(str(table))
            }
            driving_table = str(unit.get('driving_table', '')).upper()
            if self._is_pseudo_table_name(driving_table):
                driving_table = ""
            if not skip_locked_tables and re.search(r"\bFOR\s+UPDATE\s+SKIP\s+LOCKED\b", raw_plsql, flags=re.IGNORECASE):
                if driving_table:
                    skip_locked_tables.add(driving_table)
            cursor_filters = self._extract_cursor_filter_conditions(raw_plsql, driving_table)

            def _default_spec() -> Dict[str, Any]:
                return {
                    'operations': set(),
                    'lookup_keys': [],
                    'lookup_key_variants': [],
                    'sum_key_variants': [],
                    'requires_upsert': False,
                    'requires_skip_locked': False,
                    'aggregation_columns': [],
                    'cursor_filters': [],
                }

            for table_name, operations in (unit.get('operations_by_table') or {}).items():
                normalized_table = str(table_name).upper()
                if self._is_pseudo_table_name(normalized_table):
                    continue
                spec = table_specs.setdefault(normalized_table, _default_spec())
                table_ops = {str(op).upper() for op in (operations or []) if op}
                spec['operations'].update(table_ops)
                unit_lookup_keys: List[str] = []
                for column in (lookup_map.get(normalized_table) or []):
                    normalized_column = str(column).upper()
                    if normalized_column not in spec['lookup_keys']:
                        spec['lookup_keys'].append(normalized_column)
                    if normalized_column not in unit_lookup_keys:
                        unit_lookup_keys.append(normalized_column)
                if unit_lookup_keys:
                    variant_key = tuple(unit_lookup_keys)
                    is_aggregation_only_context = (
                        normalized_table in unit_aggregation_tables
                        and (not table_ops or table_ops.issubset({"SELECT"}))
                    )
                    if not is_aggregation_only_context:
                        known_variants = {
                            tuple(str(value).upper() for value in (variant or []) if value)
                            for variant in (spec.get('lookup_key_variants') or [])
                        }
                        if variant_key not in known_variants:
                            spec['lookup_key_variants'].append(unit_lookup_keys)
                spec['requires_upsert'] = spec['requires_upsert'] or ('MERGE' in spec['operations'])
                spec['requires_skip_locked'] = spec['requires_skip_locked'] or (normalized_table in skip_locked_tables)
            for upsert in semantic_upserts:
                table_name = str(upsert.get('table', '')).upper()
                if not table_name or self._is_pseudo_table_name(table_name):
                    continue
                spec = table_specs.setdefault(table_name, _default_spec())
                spec['operations'].add('MERGE')
                spec['requires_upsert'] = True
            for aggregation_ref in aggregation_refs:
                parts = str(aggregation_ref).split('.', 1)
                if len(parts) != 2:
                    continue
                table_name = parts[0].strip().upper()
                column_name = parts[1].strip().upper()
                if not table_name or self._is_pseudo_table_name(table_name) or not column_name:
                    continue
                spec = table_specs.setdefault(table_name, _default_spec())
                spec['operations'].add('SELECT')
                if column_name not in spec['aggregation_columns']:
                    spec['aggregation_columns'].append(column_name)
                aggregation_lookup_keys: List[str] = []
                for column in (lookup_map.get(table_name) or []):
                    normalized_column = str(column).upper()
                    if normalized_column not in spec['lookup_keys']:
                        spec['lookup_keys'].append(normalized_column)
                    if normalized_column not in aggregation_lookup_keys:
                        aggregation_lookup_keys.append(normalized_column)
                if aggregation_lookup_keys:
                    variant_key = tuple(aggregation_lookup_keys)
                    known_sum_variants = {
                        tuple(str(value).upper() for value in (variant or []) if value)
                        for variant in (spec.get('sum_key_variants') or [])
                    }
                    if variant_key not in known_sum_variants:
                        spec['sum_key_variants'].append(aggregation_lookup_keys)
            for skip_table in skip_locked_tables:
                if self._is_pseudo_table_name(skip_table):
                    continue
                spec = table_specs.setdefault(skip_table, _default_spec())
                spec['operations'].add('SELECT')
                spec['requires_skip_locked'] = True
                if skip_table == driving_table and cursor_filters:
                    if not spec['cursor_filters']:
                        spec['cursor_filters'] = list(cursor_filters)
                    else:
                        existing = {
                            (item.get("column", "").upper(), item.get("expression", "").upper())
                            for item in spec['cursor_filters']
                        }
                        for item in cursor_filters:
                            key = (item.get("column", "").upper(), item.get("expression", "").upper())
                            if key not in existing:
                                spec['cursor_filters'].append(item)

        for table_name in sorted(table_specs):
            if self._is_pseudo_table_name(table_name):
                continue
            spec = table_specs[table_name]
            entity_name = self._derive_entity_name_from_table(table_name, entities)
            repo_name = self._derive_repository_name_from_entity(entity_name)
            entity_types = entity_field_types.get(entity_name, {})
            repositories[f"{repo_name}.java"] = self._generate_deterministic_repository_interface(
                table_name=table_name,
                entity_name=entity_name,
                repo_name=repo_name,
                spec=spec,
                entity_field_types=entity_types,
            )
        return repositories

    def _extract_entity_field_types(self, entities: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        result: Dict[str, Dict[str, str]] = {}
        pattern = re.compile(r"private\s+([\w<>, ?]+)\s+(\w+)\s*;")
        for filename, code in (entities or {}).items():
            class_name = filename.replace('.java', '')
            fields: Dict[str, str] = {}
            for type_name, field_name in pattern.findall(code):
                fields[field_name] = type_name.strip()
            result[class_name] = fields
        return result

    def _expected_lookup_method_name(self, lookup_keys: List[str]) -> str:
        normalized = [normalize_column_name(key) for key in lookup_keys if key]
        suffix = "And".join(
            name[:1].upper() + name[1:]
            for name in normalized
            if name
        )
        return f"findBy{suffix}" if suffix else "findById"

    def _resolve_lookup_key_type(self, key: str, entity_field_types: Dict[str, str]) -> str:
        normalized_key = normalize_column_name(key)
        for field_name, type_name in (entity_field_types or {}).items():
            if normalize_column_name(field_name).lower() == normalized_key.lower():
                return type_name
        return "Long"

    def _method_suffix_from_columns(self, columns: List[str]) -> str:
        normalized = [normalize_column_name(column) for column in (columns or []) if column]
        return "And".join(
            name[:1].upper() + name[1:]
            for name in normalized
            if name
        )

    def _resolve_entity_field_name(self, column_name: str, entity_field_types: Dict[str, str]) -> str:
        normalized_column = normalize_column_name(column_name)
        for field_name in (entity_field_types or {}).keys():
            if normalize_column_name(field_name).lower() == normalized_column.lower():
                return field_name
        return normalized_column

    def _extract_cursor_filter_conditions(self, raw_plsql: str, driving_table: str) -> List[Dict[str, str]]:
        cursor_pattern = re.compile(
            r"\bcursor\s+[A-Za-z_][\w$#]*\s+is\s+(select\b[\s\S]*?);",
            flags=re.IGNORECASE,
        )
        for match in cursor_pattern.finditer(raw_plsql or ""):
            statement = match.group(1)
            if driving_table and not re.search(
                rf"\bfrom\s+[`\"]?{re.escape(driving_table)}[`\"]?\b",
                statement,
                flags=re.IGNORECASE,
            ):
                continue
            where_match = re.search(
                r"\bwhere\b\s+(.*?)(?:\bfor\s+update\b|\border\s+by\b|$)",
                statement,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not where_match:
                continue
            where_clause = where_match.group(1)
            conditions: List[Dict[str, str]] = []
            seen: Set[Tuple[str, str]] = set()
            for token in re.split(r"\band\b", where_clause, flags=re.IGNORECASE):
                clause = token.strip().strip("()")
                if not clause or re.search(r"\bor\b", clause, flags=re.IGNORECASE):
                    continue
                eq_match = re.match(
                    r"(?i)(?:[A-Za-z_][\w$#]*\.)?([A-Za-z_][\w$#]*)\s*=\s*(.+)$",
                    clause,
                )
                if not eq_match:
                    continue
                column_name = eq_match.group(1).upper()
                expression = eq_match.group(2).strip().rstrip(";")
                key = (column_name, expression.upper())
                if key in seen:
                    continue
                seen.add(key)
                conditions.append({"column": column_name, "expression": expression})
            if conditions:
                return conditions
        return []

    def _skip_locked_method_name(self, filters: List[Dict[str, str]]) -> str:
        if not filters:
            return "findPageForUpdateSkipLocked"
        suffix = self._method_suffix_from_columns([item.get("column", "") for item in filters])
        return f"findPageForUpdateSkipLockedBy{suffix}" if suffix else "findPageForUpdateSkipLocked"

    def _aggregation_method_name(self, lookup_keys: List[str]) -> str:
        suffix = self._method_suffix_from_columns(lookup_keys)
        return f"sumBy{suffix}" if suffix else "sumAll"

    def _aggregation_batch_method_name(self, lookup_keys: List[str]) -> str:
        return f"{self._aggregation_method_name(lookup_keys)}In"

    def _java_expression_for_filter(
        self,
        expression: str,
        param_name_map: Dict[str, str],
        expected_type: str,
    ) -> str:
        expr = (expression or "").strip()
        string_match = re.match(r"^'(.*)'$", expr)
        if string_match:
            escaped = string_match.group(1).replace("\\", "\\\\").replace('"', '\\"')
            return f"\"{escaped}\""
        if re.match(r"^-?\d+\.\d+$", expr):
            return f"new BigDecimal(\"{expr}\")" if expected_type == "BigDecimal" else expr
        if re.match(r"^-?\d+$", expr):
            if expected_type in {"Long", "long"}:
                return f"{expr}L"
            if expected_type in {"BigDecimal"}:
                return f"new BigDecimal(\"{expr}\")"
            return expr
        cleaned = expr.strip().strip('"`')
        normalized = normalize_column_name(cleaned)
        return param_name_map.get(cleaned.upper(), param_name_map.get(normalized.upper(), normalized))

    def _generate_deterministic_repository_interface(
        self,
        table_name: str,
        entity_name: str,
        repo_name: str,
        spec: Dict[str, Any],
        entity_field_types: Dict[str, str],
    ) -> str:
        package_name = self.config.get('output', {}).get('package_name', 'com.company.project')
        lookup_keys = list(spec.get('lookup_keys', []))
        lookup_variants_raw = spec.get('lookup_key_variants') or []
        lookup_variants: List[List[str]] = []
        seen_lookup_variants: Set[Tuple[str, ...]] = set()
        for variant in lookup_variants_raw:
            normalized_variant = [str(key).upper() for key in (variant or []) if key]
            if not normalized_variant:
                continue
            signature = tuple(normalized_variant)
            if signature in seen_lookup_variants:
                continue
            seen_lookup_variants.add(signature)
            lookup_variants.append(normalized_variant)
        if not lookup_variants and lookup_keys:
            lookup_variants = [lookup_keys]
        custom_methods: List[str] = []
        imports = {
            "import org.springframework.data.jpa.repository.JpaRepository;",
            "import org.springframework.stereotype.Repository;",
            f"import {package_name}.entity.{entity_name};",
        }
        aggregation_columns = list(spec.get('aggregation_columns') or [])
        operations = {str(op).upper() for op in (spec.get('operations') or set()) if op}
        aggregation_only = bool(aggregation_columns) and (not operations or operations.issubset({"SELECT"}))

        if lookup_variants and not aggregation_only:
            imports.add("import java.util.Optional;")
            emitted_lookup_methods: Set[str] = set()
            for lookup_variant in lookup_variants:
                lookup_method_name = self._expected_lookup_method_name(lookup_variant)
                if not lookup_method_name or lookup_method_name in emitted_lookup_methods:
                    continue
                params = []
                for key in lookup_variant:
                    param_name = normalize_column_name(key)
                    param_type = self._resolve_lookup_key_type(key, entity_field_types)
                    params.append(f"{param_type} {param_name}")
                custom_methods.append(f"    Optional<{entity_name}> {lookup_method_name}({', '.join(params)});")
                emitted_lookup_methods.add(lookup_method_name)

        if spec.get('requires_skip_locked'):
            cursor_filters = list(spec.get('cursor_filters') or [])
            method_name = self._skip_locked_method_name(cursor_filters)
            query_sql = f"SELECT * FROM {table_name.lower()}"
            method_params: List[str] = []
            imports.update(
                {
                    "import org.springframework.data.domain.Page;",
                    "import org.springframework.data.domain.Pageable;",
                    "import org.springframework.data.jpa.repository.Query;",
                    "import org.springframework.data.repository.query.Param;",
                }
            )
            if cursor_filters:
                where_clauses = []
                for filter_item in cursor_filters:
                    column_name = str(filter_item.get("column", "")).strip()
                    if not column_name:
                        continue
                    param_name = normalize_column_name(column_name)
                    param_type = self._resolve_lookup_key_type(column_name, entity_field_types)
                    where_clauses.append(f"{column_name.lower()} = :{param_name}")
                    method_params.append(f"@Param(\"{param_name}\") {param_type} {param_name}")
                if where_clauses:
                    query_sql += " WHERE " + " AND ".join(where_clauses)
            query_sql += " FOR UPDATE SKIP LOCKED"
            method_params.append("Pageable pageable")
            custom_methods.append(
                f"    @Query(value = \"{query_sql}\", nativeQuery = true)\n"
                f"    Page<{entity_name}> {method_name}({', '.join(method_params)});"
            )

        if aggregation_columns:
            sum_column = aggregation_columns[0]
            sum_field = self._resolve_entity_field_name(sum_column, entity_field_types)
            imports.update(
                {
                    "import java.math.BigDecimal;",
                    "import org.springframework.data.jpa.repository.Query;",
                    "import org.springframework.data.repository.query.Param;",
                    "import org.springframework.transaction.annotation.Transactional;",
                }
            )
            sum_lookup_variants: List[List[str]] = []
            seen_sum_variants: Set[Tuple[str, ...]] = set()
            raw_sum_variants = (
                spec.get('sum_key_variants')
                or lookup_variants
                or ([lookup_keys] if lookup_keys else [[]])
            )
            for variant in raw_sum_variants:
                normalized_variant = [str(key).upper() for key in (variant or []) if key]
                signature = tuple(normalized_variant)
                if signature in seen_sum_variants:
                    continue
                seen_sum_variants.add(signature)
                sum_lookup_variants.append(normalized_variant)
            if not sum_lookup_variants:
                sum_lookup_variants = [[]]

            emitted_sum_methods: Set[str] = set()
            for lookup_for_sum in sum_lookup_variants:
                sum_method_name = self._aggregation_method_name(lookup_for_sum)
                if sum_method_name in emitted_sum_methods:
                    continue
                emitted_sum_methods.add(sum_method_name)

                if lookup_for_sum:
                    where_fragments = []
                    method_params = []
                    for key in lookup_for_sum:
                        field_name = self._resolve_entity_field_name(key, entity_field_types)
                        param_name = normalize_column_name(key)
                        param_type = self._resolve_lookup_key_type(key, entity_field_types)
                        where_fragments.append(f"e.{field_name} = :{param_name}")
                        method_params.append(f"@Param(\"{param_name}\") {param_type} {param_name}")
                    where_clause = " WHERE " + " AND ".join(where_fragments)
                    query = f"SELECT COALESCE(SUM(e.{sum_field}), 0) FROM {entity_name} e{where_clause}"
                    custom_methods.append(
                        f"    @Transactional(readOnly = true)\n"
                        f"    @Query(\"{query}\")\n"
                        f"    BigDecimal {sum_method_name}({', '.join(method_params)});"
                    )
                else:
                    query = f"SELECT COALESCE(SUM(e.{sum_field}), 0) FROM {entity_name} e"
                    custom_methods.append(
                        f"    @Transactional(readOnly = true)\n"
                        f"    @Query(\"{query}\")\n"
                        f"    BigDecimal {sum_method_name}();"
                    )

        methods_block = "\n\n".join(custom_methods)
        if methods_block:
            methods_block = f"\n\n{methods_block}\n"
        return (
            f"package {package_name}.repository;\n\n"
            f"{chr(10).join(sorted(imports))}\n\n"
            "@Repository\n"
            f"public interface {repo_name} extends JpaRepository<{entity_name}, Long> {{{methods_block}"
            "}\n"
        )

    async def generate_services_from_semantics(
        self,
        source_units: List[Dict[str, Any]],
        entities: Dict[str, str],
        repositories: Dict[str, str],
        validation_feedback: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, str]:
        # Deterministic service generation with semantic constraints.
        services: Dict[str, str] = {}
        for unit in source_units:
            object_type = str(unit.get('object_type', 'PROCEDURE')).upper()
            if object_type in {'TRIGGER', 'PACKAGE'}:
                continue
            filename = self._derive_service_filename(unit)
            services[filename] = self._generate_deterministic_service_from_unit(
                unit=unit,
                entities=entities,
                repositories=repositories,
            )
        return services

    def _build_service_parameters(self, unit: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
        params = []
        name_map: Dict[str, str] = {}
        for spec in self._collect_service_parameter_specs(unit):
            param_name = spec["java_name"]
            java_type = spec["java_type"]
            raw_name = spec["raw_name"]
            params.append(f"{java_type} {param_name}")
            normalized_raw = normalize_column_name(raw_name)
            canonical_token = self._canonical_name_token(raw_name)
            keys = {
                raw_name.upper(),
                normalized_raw.upper(),
                canonical_token.upper() if canonical_token else "",
                normalize_column_name(param_name).upper(),
            }
            # Map "p_customer_id" -> "CUSTOMER_ID" style lookups dynamically.
            stripped = re.sub(r"^(?:p|v|l|aux|tmp)_*", "", str(raw_name), flags=re.IGNORECASE)
            if stripped:
                keys.add(stripped.upper())
                keys.add(normalize_column_name(stripped).upper())
            for key in keys:
                if key:
                    name_map[key] = param_name
        return ", ".join(params), name_map

    def _derive_primary_table(self, unit: Dict[str, Any]) -> str:
        operations = unit.get('operations_by_table') or {}
        if operations:
            real_tables = sorted(
                str(name).upper()
                for name in operations.keys()
                if not self._is_pseudo_table_name(str(name))
            )
            if real_tables:
                return real_tables[0]
        tables = unit.get('tables_used') or []
        real_tables = [
            str(table).upper()
            for table in tables
            if table and not self._is_pseudo_table_name(str(table))
        ]
        return real_tables[0] if real_tables else "DUAL"

    def _derive_driving_table(self, unit: Dict[str, Any]) -> str:
        driving = str(unit.get('driving_table', '')).upper()
        if driving and not self._is_pseudo_table_name(driving):
            return driving
        cursor = unit.get('cursor') or {}
        cursor_driving = str(cursor.get('driving_table', '')).upper()
        if cursor_driving and not self._is_pseudo_table_name(cursor_driving):
            return cursor_driving
        cursor_tables = [
            str(table).upper()
            for table in (cursor.get('tables') or [])
            if table and not self._is_pseudo_table_name(str(table))
        ]
        if cursor_tables:
            return cursor_tables[0]
        return self._derive_primary_table(unit)

    def _derive_target_tables(self, unit: Dict[str, Any]) -> List[str]:
        declared = [
            str(table).upper()
            for table in (unit.get('target_tables') or [])
            if table and not self._is_pseudo_table_name(str(table))
        ]
        if declared:
            return sorted(dict.fromkeys(declared))
        targets: List[str] = []
        for table_name, operations in (unit.get('operations_by_table') or {}).items():
            if self._is_pseudo_table_name(str(table_name)):
                continue
            upper_ops = {str(op).upper() for op in (operations or [])}
            if upper_ops.intersection({'INSERT', 'UPDATE', 'DELETE', 'MERGE'}):
                targets.append(str(table_name).upper())
        return sorted(dict.fromkeys(targets))

    def _derive_merge_table(self, unit: Dict[str, Any]) -> str:
        semantic = unit.get('semantic_analysis') or {}
        for upsert in semantic.get('upsert_operations') or []:
            table_name = str(upsert.get('table', '')).upper()
            if table_name and not self._is_pseudo_table_name(table_name):
                return table_name
        raw_plsql = str(unit.get('raw_plsql', ''))
        match = re.search(r'\bMERGE\s+INTO\s+([`"\w$#\.]+)', raw_plsql, flags=re.IGNORECASE)
        if match:
            table_name = str(match.group(1)).strip('"`').split(".")[-1].upper()
            if not self._is_pseudo_table_name(table_name):
                return table_name
        return ""

    def _lookup_keys_for_table(self, unit: Dict[str, Any], table_name: str) -> List[str]:
        if self._is_pseudo_table_name(str(table_name)):
            return []
        lookup_map = unit.get('lookup_keys') or {}
        table_key = str(table_name).upper()
        return sorted(str(col).upper() for col in (lookup_map.get(table_key) or []) if col)

    def _infer_function_return_type(
        self,
        unit: Dict[str, Any],
        bindings: Dict[str, Dict[str, str]],
        entity_field_types: Dict[str, Dict[str, str]],
        driving_entity: str,
    ) -> str:
        if str(unit.get("object_type", "")).upper() != "FUNCTION":
            return "void"

        raw_plsql = str(unit.get("raw_plsql", ""))
        match = re.search(r"\bfunction\b[\s\S]*?\breturn\s+([A-Za-z_][\w$#%.()]+)", raw_plsql, flags=re.IGNORECASE)
        declared = str(match.group(1)).strip() if match else ""
        declared_upper = declared.upper()
        if declared_upper.endswith("%ROWTYPE"):
            return driving_entity
        if "%TYPE" in declared_upper:
            type_match = re.match(r"([A-Za-z_][\w$#]*)\.([A-Za-z_][\w$#]*)%TYPE", declared_upper)
            if type_match:
                table_name = type_match.group(1)
                column_name = type_match.group(2)
                binding = bindings.get(table_name)
                if binding:
                    field_types = entity_field_types.get(binding["entity"], {})
                    resolved_field = self._resolve_entity_field_name(column_name, field_types)
                    if resolved_field in field_types:
                        return field_types[resolved_field]
            return "String"
        if declared:
            if declared_upper.startswith("NUMBER"):
                function_name = str(unit.get("name", "")).lower()
                if any(token in function_name for token in ("amount", "rate", "cost", "balance", "total", "vat")):
                    return "BigDecimal"
            return self._map_plsql_type_to_java(declared)
        return "String"

    def _repository_has_method(self, repository_code: str, method_name: str) -> bool:
        return bool(re.search(rf"\b{re.escape(method_name)}\s*\(", repository_code or ""))

    def _find_delete_method_name(
        self,
        repository_code: str,
        entity_name: str,
        lookup_keys: List[str],
    ) -> str:
        if not lookup_keys:
            return ""
        suffix = self._method_suffix_from_columns(lookup_keys)
        if not suffix:
            return ""
        entity_base = entity_name[:-6] if entity_name.endswith("Entity") else entity_name
        candidates = [
            f"deleteBy{suffix}",
            f"delete{entity_base}By{suffix}",
        ]
        for candidate in candidates:
            if self._repository_has_method(repository_code, candidate):
                return candidate
        return ""

    def _infer_lookup_keys_from_repository(
        self,
        repository_code: str,
        parameter_specs: List[Dict[str, str]],
        table_fields: Dict[str, str],
    ) -> List[str]:
        candidates = re.findall(r"\bfindBy([A-Za-z0-9_]+)\s*\(", repository_code or "")
        best_keys: List[str] = []
        best_score = -1
        for suffix in candidates:
            parts = [part for part in re.split(r"And", suffix) if part]
            if not parts:
                continue
            resolved_keys: List[str] = []
            score = 0
            valid = True
            for part in parts:
                key_name = normalize_column_name(part)
                expected_type = self._resolve_lookup_key_type(key_name, table_fields)
                param_spec = self._best_param_for_field(key_name, parameter_specs, expected_type)
                if not param_spec:
                    valid = False
                    break
                sql_key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(part)).upper()
                resolved_keys.append(sql_key)
                score += 10
                if str(param_spec.get("token", "")).lower() == self._canonical_name_token(key_name):
                    score += 4
            if valid and score > best_score:
                best_score = score
                best_keys = resolved_keys
        return best_keys

    def _generate_deterministic_service_from_unit(
        self,
        unit: Dict[str, Any],
        entities: Dict[str, str],
        repositories: Dict[str, str],
    ) -> str:
        package_name = self.config.get('output', {}).get('package_name', 'com.company.project')
        service_name = self._derive_service_name(unit.get('name', 'Generated'))
        method_name = self._to_camel_case(unit.get('name', 'execute'))
        method_params, param_name_map = self._build_service_parameters(unit)

        raw_plsql = str(unit.get('raw_plsql', ''))
        semantic = unit.get('semantic_analysis') or {}
        operations_by_table = unit.get('operations_by_table') or {}
        entity_field_types = self._extract_entity_field_types(entities)

        driving_table = self._derive_driving_table(unit)
        target_tables = self._derive_target_tables(unit)
        merge_table = self._derive_merge_table(unit)
        if merge_table and merge_table not in target_tables:
            target_tables.append(merge_table)
        target_tables = sorted(dict.fromkeys([table for table in target_tables if table]))

        select_tables = [
            str(table).upper()
            for table, ops in operations_by_table.items()
            if not self._is_pseudo_table_name(str(table))
            if 'SELECT' in {str(op).upper() for op in (ops or [])}
        ]
        aggregation_tables: List[str] = []
        aggregation_columns: List[Tuple[str, str]] = []
        for ref in semantic.get('aggregation', {}).get('columns', []) or []:
            parts = str(ref).split('.', 1)
            if len(parts) != 2:
                continue
            table_name = parts[0].strip().upper()
            column_name = parts[1].strip()
            if not table_name or self._is_pseudo_table_name(table_name) or not column_name:
                continue
            aggregation_columns.append((table_name, column_name))
            if table_name not in aggregation_tables:
                aggregation_tables.append(table_name)
        aggregation_only_tables: Set[str] = set()
        for table_name in aggregation_tables:
            table_ops = {str(op).upper() for op in (operations_by_table.get(table_name) or []) if op}
            if not table_ops or table_ops.issubset({"SELECT"}):
                aggregation_only_tables.add(table_name)

        table_order: List[str] = []
        for table_name in [
            driving_table,
            *select_tables,
            *aggregation_tables,
            *target_tables,
        ]:
            normalized = str(table_name).upper()
            if (
                normalized
                and not self._is_pseudo_table_name(normalized)
                and normalized not in table_order
            ):
                table_order.append(normalized)

        bindings: Dict[str, Dict[str, str]] = {}
        for table_name in table_order:
            entity_name = self._derive_entity_name_from_table(table_name, entities)
            repository_name = self._derive_repository_name_from_entity(entity_name)
            repository_filename = f"{repository_name}.java"
            if repository_filename not in repositories:
                continue
            bindings[table_name] = {
                'entity': entity_name,
                'repository': repository_name,
                'repository_var': self._lower_first(repository_name),
            }

        if not bindings:
            fallback_tokens: List[str] = [
                str(unit.get("name", "")),
                driving_table,
                *target_tables,
                *select_tables,
                *aggregation_tables,
            ]
            fallback_binding = self._fallback_binding_from_repositories(
                repositories,
                preferred_tokens=fallback_tokens,
            )
            if fallback_binding:
                fallback_table = fallback_binding['table']
                bindings[fallback_table] = {
                    'entity': fallback_binding['entity'],
                    'repository': fallback_binding['repository'],
                    'repository_var': fallback_binding['repository_var'],
                }
                if not driving_table or driving_table not in bindings:
                    driving_table = fallback_table
            else:
                fallback_table = self._derive_primary_table(unit)
                fallback_entity = self._derive_entity_name_from_table(fallback_table, entities)
                fallback_repo = self._derive_repository_name_from_entity(fallback_entity)
                bindings[fallback_table] = {
                    'entity': fallback_entity,
                    'repository': fallback_repo,
                    'repository_var': self._lower_first(fallback_repo),
                }
                if not driving_table:
                    driving_table = fallback_table

        if driving_table not in bindings:
            driving_table = next(iter(bindings.keys()))

        driving_binding = bindings[driving_table]
        driving_entity = driving_binding['entity']
        driving_repo = driving_binding['repository']
        driving_repo_var = driving_binding['repository_var']

        insert_tables = [
            str(table_name).upper()
            for table_name, ops in operations_by_table.items()
            if 'INSERT' in {str(op).upper() for op in (ops or [])}
        ]
        audit_table = next((table for table in insert_tables if 'AUDIT' in table), '')
        error_table = next((table for table in insert_tables if 'ERROR' in table), '')
        audit_binding = bindings.get(audit_table) if audit_table else None
        error_binding = bindings.get(error_table) if error_table else None

        imports = {
            'import org.springframework.stereotype.Service;',
            f'import {package_name}.entity.{driving_entity};',
        }
        for binding in bindings.values():
            imports.add(f"import {package_name}.repository.{binding['repository']};")
            imports.add(f"import {package_name}.entity.{binding['entity']};")

        has_bulk_collect = any(
            str(op.get('type', '')).upper() == 'BULK_COLLECT'
            for op in (unit.get('bulk_operations') or [])
        )
        has_cursor = bool(unit.get('cursor')) or bool(re.search(r"\bCURSOR\b", raw_plsql, flags=re.IGNORECASE))
        requires_pagination = has_bulk_collect or has_cursor
        transaction = unit.get('transaction') or {}
        has_savepoint_control = bool(
            transaction.get('has_savepoint')
            or re.search(r"\bsavepoint\b", raw_plsql, flags=re.IGNORECASE)
        )
        has_commit_control = bool(
            transaction.get('has_commit')
            or re.search(r"\bcommit\b", raw_plsql, flags=re.IGNORECASE)
        )
        has_rollback_to_control = bool(
            transaction.get('has_partial_rollback')
            or re.search(r"\brollback\s+to(?:\s+savepoint)?\b", raw_plsql, flags=re.IGNORECASE)
        )
        requires_batch_transaction = has_savepoint_control or has_commit_control or has_rollback_to_control
        requires_transactional_method = bool(
            transaction.get('required')
            or transaction.get('has_rollback')
            or re.search(r"\brollback\b", raw_plsql, flags=re.IGNORECASE)
        ) and not requires_batch_transaction
        if requires_transactional_method:
            imports.add('import org.springframework.transaction.annotation.Transactional;')
        if requires_batch_transaction:
            imports.update(
                {
                    'import org.springframework.transaction.PlatformTransactionManager;',
                    'import org.springframework.transaction.support.TransactionTemplate;',
                }
            )

        skip_locked_tables = {
            str(table).upper()
            for table in (unit.get('skip_locked_tables') or [])
            if table
        }
        cursor_locking = str((unit.get('cursor') or {}).get('locking', '')).upper()
        if not skip_locked_tables and 'SKIP LOCKED' in cursor_locking and driving_table:
            skip_locked_tables.add(driving_table)
        cursor_filters = self._extract_cursor_filter_conditions(raw_plsql, driving_table)
        skip_locked_method = self._skip_locked_method_name(cursor_filters)
        skip_locked_driving_cursor = driving_table in skip_locked_tables

        if requires_pagination:
            imports.update(
                {
                    'import org.springframework.data.domain.Page;',
                    'import org.springframework.data.domain.PageRequest;',
                }
            )
        else:
            imports.add('import org.springframework.data.domain.PageRequest;')
            imports.add('import java.util.List;')

        has_merge = bool(merge_table) or bool(re.search(r"\bMERGE\s+INTO\b", raw_plsql, flags=re.IGNORECASE))
        if has_merge or aggregation_columns:
            imports.add('import java.util.Optional;')

        uses_big_decimal = bool(aggregation_columns)
        if uses_big_decimal:
            imports.add('import java.math.BigDecimal;')

        merge_target_for_import = merge_table or (target_tables[0] if target_tables else "")
        merge_binding_for_import = bindings.get(merge_target_for_import) if merge_target_for_import else None
        if merge_binding_for_import:
            merge_fields_for_import = entity_field_types.get(merge_binding_for_import['entity'], {})
            if any(
                normalize_column_name(field_name).lower()
                in {
                    normalize_column_name("created_at").lower(),
                    normalize_column_name("updated_at").lower(),
                }
                for field_name in merge_fields_for_import
            ):
                imports.add('import java.time.LocalDateTime;')
        if audit_binding or error_binding:
            imports.add('import java.time.LocalDateTime;')

        constructor_lines: List[str] = []
        field_lines: List[str] = []
        init_lines: List[str] = []
        for binding in bindings.values():
            repository_name = binding['repository']
            repository_var = binding['repository_var']
            field_lines.append(f"    private final {repository_name} {repository_var};")
            constructor_lines.append(f"{repository_name} {repository_var}")
            init_lines.append(f"        this.{repository_var} = {repository_var};")
        if requires_batch_transaction:
            field_lines.append("    private final TransactionTemplate batchTransactionTemplate;")
            constructor_lines.append("PlatformTransactionManager transactionManager")
            init_lines.append("        this.batchTransactionTemplate = new TransactionTemplate(transactionManager);")

        parameter_specs = self._collect_service_parameter_specs(unit)
        method_return_type = self._infer_function_return_type(
            unit=unit,
            bindings=bindings,
            entity_field_types=entity_field_types,
            driving_entity=driving_entity,
        )
        is_direct_mode = not requires_pagination and not requires_batch_transaction
        if is_direct_mode:
            normalized_ops_by_table: Dict[str, Set[str]] = {
                str(table).upper(): {str(op).upper() for op in (ops or []) if op}
                for table, ops in (operations_by_table or {}).items()
                if table and not self._is_pseudo_table_name(str(table))
            }
            has_mutation = any(
                ops.intersection({"INSERT", "UPDATE", "DELETE", "MERGE"})
                for ops in normalized_ops_by_table.values()
            )

            direct_lines: List[str] = []
            if method_return_type != "void":
                imports.add("import java.util.Optional;")
            if method_return_type == "BigDecimal":
                imports.add("import java.math.BigDecimal;")
            error_message_literals = self._extract_plsql_error_literals(raw_plsql)
            for idx, literal in enumerate(error_message_literals):
                escaped_literal = self._escape_java_string_literal(literal)
                direct_lines.append(f'String preservedPlsqlLiteral{idx} = "{escaped_literal}";')

            aggregation_return_var = ""
            for table_name, column_name in aggregation_columns:
                binding = bindings.get(table_name)
                if not binding:
                    continue
                table_repo_var = binding["repository_var"]
                lookup_keys = self._lookup_keys_for_table(unit, table_name)
                sum_method = self._aggregation_method_name(lookup_keys)
                call_args: List[str] = []
                table_entity_types = entity_field_types.get(binding["entity"], {})
                for key in lookup_keys:
                    expected_type = self._resolve_lookup_key_type(key, table_entity_types)
                    call_args.append(
                        self._resolve_lookup_argument_expression(
                            column_name=key,
                            driving_fields={},
                            param_name_map=param_name_map,
                            expected_type=expected_type,
                            param_specs=parameter_specs,
                        )
                    )
                args_expression = ", ".join(call_args)
                var_name = f"{normalize_column_name(table_name.lower())}Amount"
                if args_expression:
                    direct_lines.append(
                        f"BigDecimal {var_name} = Optional.ofNullable({table_repo_var}.{sum_method}({args_expression})).orElse(BigDecimal.ZERO);"
                    )
                else:
                    direct_lines.append(
                        f"BigDecimal {var_name} = Optional.ofNullable({table_repo_var}.{sum_method}()).orElse(BigDecimal.ZERO);"
                    )
                if not aggregation_return_var:
                    aggregation_return_var = var_name

            mutation_tables = [
                table_name
                for table_name in sorted(normalized_ops_by_table.keys())
                if normalized_ops_by_table.get(table_name, set()).intersection({"INSERT", "UPDATE", "DELETE", "MERGE"})
            ]
            if not mutation_tables:
                mutation_tables = [table for table in target_tables if table in bindings]

            for table_name in mutation_tables:
                binding = bindings.get(table_name)
                if not binding:
                    continue
                table_ops = normalized_ops_by_table.get(table_name, set())
                repository_var = binding["repository_var"]
                repository_code = repositories.get(f"{binding['repository']}.java", "")
                table_entity = binding["entity"]
                table_fields = entity_field_types.get(table_entity, {})
                lookup_keys = self._lookup_keys_for_table(unit, table_name)
                lookup_method = self._expected_lookup_method_name(lookup_keys) if lookup_keys else ""
                lookup_args: List[str] = []
                for key in lookup_keys:
                    expected_type = self._resolve_lookup_key_type(key, table_fields)
                    lookup_args.append(
                        self._resolve_lookup_argument_expression(
                            column_name=key,
                            driving_fields={},
                            param_name_map=param_name_map,
                            expected_type=expected_type,
                            param_specs=parameter_specs,
                        )
                    )

                if "DELETE" in table_ops:
                    delete_method = self._find_delete_method_name(repository_code, table_entity, lookup_keys)
                    if delete_method and lookup_args:
                        direct_lines.append(f"{repository_var}.{delete_method}({', '.join(lookup_args)});")
                    elif lookup_method and lookup_args and self._repository_has_method(repository_code, lookup_method):
                        direct_lines.append(
                            f"{repository_var}.{lookup_method}({', '.join(lookup_args)}).ifPresent({repository_var}::delete);"
                        )
                    elif lookup_args:
                        direct_lines.append(f"{repository_var}.deleteById({lookup_args[0]});")
                    continue

                if "UPDATE" in table_ops:
                    target_var = f"{self._lower_first(table_entity)}Target"
                    if lookup_method and lookup_args and self._repository_has_method(repository_code, lookup_method):
                        direct_lines.append(
                            f"{table_entity} {target_var} = {repository_var}.{lookup_method}({', '.join(lookup_args)}).orElse(new {table_entity}());"
                        )
                    elif lookup_args:
                        direct_lines.append(
                            f"{table_entity} {target_var} = {repository_var}.findById({lookup_args[0]}).orElse(new {table_entity}());"
                        )
                    else:
                        direct_lines.append(f"{table_entity} {target_var} = new {table_entity}();")
                    for field_name, field_type in table_fields.items():
                        if normalize_column_name(field_name).upper() in {normalize_column_name(k).upper() for k in lookup_keys}:
                            continue
                        param_spec = self._best_param_for_field(field_name, parameter_specs, field_type)
                        if not param_spec:
                            continue
                        if not self._types_compatible(param_spec.get("java_type", ""), field_type):
                            continue
                        setter = f"set{field_name[:1].upper() + field_name[1:]}"
                        direct_lines.append(f"{target_var}.{setter}({param_spec['java_name']});")
                    direct_lines.append(f"{repository_var}.save({target_var});")
                    continue

                if "INSERT" in table_ops:
                    target_var = f"{self._lower_first(table_entity)}Target"
                    direct_lines.append(f"{table_entity} {target_var} = new {table_entity}();")
                    assigned_fields: Set[str] = set()
                    for field_name, field_type in table_fields.items():
                        param_spec = self._best_param_for_field(field_name, parameter_specs, field_type)
                        if not param_spec:
                            continue
                        if not self._types_compatible(param_spec.get("java_type", ""), field_type):
                            continue
                        setter = f"set{field_name[:1].upper() + field_name[1:]}"
                        direct_lines.append(f"{target_var}.{setter}({param_spec['java_name']});")
                        assigned_fields.add(field_name)
                    if "sysdate" in raw_plsql.lower():
                        for field_name, field_type in table_fields.items():
                            normalized = normalize_column_name(field_name).lower()
                            if field_name in assigned_fields:
                                continue
                            if field_type == "LocalDateTime" and ("date" in normalized or "time" in normalized):
                                imports.add("import java.time.LocalDateTime;")
                                setter = f"set{field_name[:1].upper() + field_name[1:]}"
                                direct_lines.append(f"{target_var}.{setter}(LocalDateTime.now());")
                                assigned_fields.add(field_name)
                    if not assigned_fields and table_fields:
                        fallback_field, fallback_type = next(iter(table_fields.items()))
                        setter = f"set{fallback_field[:1].upper() + fallback_field[1:]}"
                        direct_lines.append(f"{target_var}.{setter}({self._default_java_literal_for_type(fallback_type)});")
                    if method_return_type != "void":
                        saved_var = f"saved{table_entity}"
                        direct_lines.append(f"{table_entity} {saved_var} = {repository_var}.save({target_var});")
                        id_field = next(
                            (
                                field_name
                                for field_name in table_fields
                                if normalize_column_name(field_name).lower().endswith("id")
                            ),
                            "",
                        )
                        if id_field and method_return_type in {"Long", "String"}:
                            getter = f"get{id_field[:1].upper() + id_field[1:]}"
                            direct_lines.append(f"return {saved_var}.{getter}();")
                    else:
                        direct_lines.append(f"{repository_var}.save({target_var});")

            if not has_mutation and select_tables:
                ranked_selects = [
                    table_name
                    for table_name in [driving_table, *select_tables]
                    if table_name in bindings and table_name not in aggregation_only_tables
                ]
                if not ranked_selects:
                    ranked_selects = [table_name for table_name in [driving_table, *select_tables] if table_name in bindings]
                select_table = ranked_selects[0] if ranked_selects else ""
                binding = bindings.get(select_table) if select_table else None
                if binding and select_table not in aggregation_only_tables:
                    table_fields = entity_field_types.get(binding["entity"], {})
                    lookup_keys = self._lookup_keys_for_table(unit, select_table)
                    repository_code = repositories.get(f"{binding['repository']}.java", "")
                    if not lookup_keys:
                        lookup_keys = self._infer_lookup_keys_from_repository(
                            repository_code=repository_code,
                            parameter_specs=parameter_specs,
                            table_fields=table_fields,
                        )
                    lookup_method = self._expected_lookup_method_name(lookup_keys) if lookup_keys else ""
                    lookup_args = []
                    for key in lookup_keys:
                        expected_type = self._resolve_lookup_key_type(key, table_fields)
                        lookup_args.append(
                            self._resolve_lookup_argument_expression(
                                column_name=key,
                                driving_fields={},
                                param_name_map=param_name_map,
                                expected_type=expected_type,
                                param_specs=parameter_specs,
                            )
                        )
                    if lookup_method and lookup_args and self._repository_has_method(repository_code, lookup_method):
                        direct_lines.append(
                            f"Optional<{binding['entity']}> found = {binding['repository_var']}.{lookup_method}({', '.join(lookup_args)});"
                        )
                        if method_return_type == binding["entity"]:
                            direct_lines.append("return found.orElse(null);")
                        elif method_return_type == "String":
                            first_string_field = next(
                                (
                                    field_name
                                    for field_name, field_type in table_fields.items()
                                    if field_type == "String"
                                ),
                                "",
                            )
                            if first_string_field:
                                getter = f"get{first_string_field[:1].upper() + first_string_field[1:]}"
                                direct_lines.append(f"return found.map({binding['entity']}::{getter}).orElse(null);")
                            else:
                                direct_lines.append("return null;")
                        elif method_return_type != "void":
                            direct_lines.append("return null;")

            if method_return_type != "void" and not any(line.strip().startswith("return ") for line in direct_lines):
                if aggregation_return_var and method_return_type == "BigDecimal":
                    direct_lines.append(f"return {aggregation_return_var};")
                elif method_return_type in {"Long", "Integer", "Double", "Float", "BigDecimal"}:
                    default_expr = self._default_value_for_java_type(method_return_type)
                    default_expr = default_expr.replace("java.math.", "").replace("java.time.", "")
                    direct_lines.append(f"return {default_expr};")
                else:
                    direct_lines.append("return null;")

            if re.search(r"\bexception\b", raw_plsql, flags=re.IGNORECASE):
                wrapped_lines: List[str] = ["try {"]
                for line in direct_lines:
                    wrapped_lines.append(f"    {line}")
                wrapped_lines.append("} catch (Exception exception) {")
                if method_return_type != "void":
                    default_expr = self._default_value_for_java_type(method_return_type)
                    default_expr = default_expr.replace("java.math.", "").replace("java.time.", "")
                    if not default_expr:
                        default_expr = "null"
                    wrapped_lines.append(f"    return {default_expr};")
                else:
                    wrapped_lines.append("    // Preserve PL/SQL EXCEPTION fallback semantics.")
                wrapped_lines.append("}")
                direct_lines = wrapped_lines

            method_body = "\n".join(f"        {line}" for line in direct_lines) if direct_lines else "        // No deterministic operation could be inferred."
            constructor_args = ", ".join(constructor_lines)
            field_block = "\n".join(field_lines)
            init_block = "\n".join(init_lines)
            helper_block = "\n".join(
                [
                    "    private String safeMessage(Exception exception) {",
                    "        return exception.getMessage() != null ? exception.getMessage() : exception.getClass().getSimpleName();",
                    "    }",
                ]
            )
            generated_symbols = "\n".join([method_params, field_block, init_block, method_body, helper_block, method_return_type])
            if "LocalDateTime" in generated_symbols:
                imports.add('import java.time.LocalDateTime;')
            if "BigDecimal" in generated_symbols:
                imports.add('import java.math.BigDecimal;')
            if "Optional<" in generated_symbols or "Optional." in generated_symbols:
                imports.add('import java.util.Optional;')
            method_annotation = "    @Transactional\n" if requires_transactional_method else ""
            return (
                f"package {package_name}.service;\n\n"
                f"{chr(10).join(sorted(imports))}\n\n"
                "@Service\n"
                f"public class {service_name} {{\n\n"
                f"{field_block}\n\n"
                f"    public {service_name}({constructor_args}) {{\n"
                f"{init_block}\n"
                "    }\n\n"
                f"{method_annotation}    public {method_return_type} {method_name}({method_params}) {{\n"
                f"{method_body}\n"
                "    }\n\n"
                f"{helper_block}\n"
                "}\n"
            )

        body_lines: List[str] = ['boolean hasError = false;']
        if requires_pagination and not skip_locked_driving_cursor:
            body_lines.insert(0, 'int page = 0;')
        batch_param = next(
            (
                normalize_column_name(param.get('name', ''))
                for param in (unit.get('input_parameters') or [])
                if 'batch' in str(param.get('name', '')).lower()
            ),
            '',
        )
        if batch_param == 'batchSize':
            body_lines.append('int size = (batchSize != null) ? batchSize.intValue() : 100;')
        elif batch_param:
            body_lines.append(f"int size = ({batch_param} != null) ? Integer.parseInt(String.valueOf({batch_param})) : 100;")
        else:
            body_lines.append('int size = 100;')

        mode_param = next(
            (
                normalize_column_name(param.get('name', ''))
                for param in (unit.get('input_parameters') or [])
                if 'mode' in str(param.get('name', '')).lower()
            ),
            '',
        )

        join_key_candidates: List[str] = []
        for table_name in [merge_table, *aggregation_tables, *target_tables]:
            for key in self._lookup_keys_for_table(unit, table_name):
                if key not in join_key_candidates:
                    join_key_candidates.append(key)
        driving_fields = entity_field_types.get(driving_entity, {})
        join_key = ''
        join_field = ''
        for candidate in join_key_candidates:
            resolved_field = self._resolve_entity_field(candidate, driving_fields)
            if resolved_field:
                join_key = candidate
                join_field = resolved_field
                break
        join_var = normalize_column_name(join_field) if join_field else ''
        join_type = driving_fields.get(join_field, 'Long') if join_field else 'Long'

        row_logic: List[str] = []
        if join_var:
            join_getter = f"get{join_field[:1].upper() + join_field[1:]}"
            row_logic.append(f"{join_type} {join_var} = row.{join_getter}();")

        agg_var_by_table: Dict[str, str] = {}
        for table_name, column_name in aggregation_columns:
            binding = bindings.get(table_name)
            if not binding:
                continue
            table_repo_var = binding['repository_var']
            lookup_keys = self._lookup_keys_for_table(unit, table_name)
            sum_method = self._aggregation_method_name(lookup_keys)
            call_args: List[str] = []
            table_entity_types = entity_field_types.get(binding['entity'], {})
            for key in lookup_keys:
                expected_type = self._resolve_lookup_key_type(key, table_entity_types)
                call_args.append(
                    self._resolve_lookup_argument_expression(
                        column_name=key,
                        driving_fields=driving_fields,
                        param_name_map=param_name_map,
                        expected_type=expected_type,
                        param_specs=parameter_specs,
                        prebound_var=join_var if join_var else None,
                        prebound_column=join_key if join_key else None,
                    )
                )
            value_var = f"{normalize_column_name(table_name.lower())}Amount"
            args_expression = ", ".join(call_args)
            if args_expression:
                row_logic.append(
                    f"BigDecimal {value_var} = Optional.ofNullable({table_repo_var}.{sum_method}({args_expression})).orElse(BigDecimal.ZERO);"
                )
            else:
                row_logic.append(
                    f"BigDecimal {value_var} = Optional.ofNullable({table_repo_var}.{sum_method}()).orElse(BigDecimal.ZERO);"
                )
            agg_var_by_table[table_name] = value_var

        # Consume deterministic lookup repository methods for SELECT routines so
        # generated custom repository contracts are actually exercised.
        emitted_lookup_calls: Set[Tuple[str, str, Tuple[str, ...]]] = set()
        lookup_call_tables: List[str] = []
        for table_name in [*select_tables, *operations_by_table.keys()]:
            normalized_table = str(table_name).upper()
            if (
                normalized_table
                and not self._is_pseudo_table_name(normalized_table)
                and normalized_table not in lookup_call_tables
            ):
                lookup_call_tables.append(normalized_table)
        for table_name in lookup_call_tables:
            binding = bindings.get(table_name)
            if not binding:
                continue
            # Aggregation-only flows must remain query-based (`sumBy...`) and
            # should not emit extra entity fetch (`findBy...`) calls.
            if table_name in aggregation_only_tables:
                continue
            lookup_keys = self._lookup_keys_for_table(unit, table_name)
            if not lookup_keys:
                continue
            lookup_method = self._expected_lookup_method_name(lookup_keys)
            repository_code = repositories.get(f"{binding['repository']}.java", "")
            if lookup_method not in repository_code:
                continue
            table_entity_types = entity_field_types.get(binding['entity'], {})
            lookup_args: List[str] = []
            for key in lookup_keys:
                expected_type = self._resolve_lookup_key_type(key, table_entity_types)
                lookup_args.append(
                    self._resolve_lookup_argument_expression(
                        column_name=key,
                        driving_fields=driving_fields,
                        param_name_map=param_name_map,
                        expected_type=expected_type,
                        param_specs=parameter_specs,
                        prebound_var=join_var if join_var else None,
                        prebound_column=join_key if join_key else None,
                    )
                )
            if not lookup_args:
                continue
            signature = (binding['repository_var'], lookup_method, tuple(lookup_args))
            if signature in emitted_lookup_calls:
                continue
            emitted_lookup_calls.add(signature)
            row_logic.append(f"{binding['repository_var']}.{lookup_method}({', '.join(lookup_args)});")

        balance_var = ''
        if len(agg_var_by_table) >= 2:
            ordered_values = [agg_var_by_table[table] for table in aggregation_tables if table in agg_var_by_table]
            if len(ordered_values) >= 2:
                balance_var = 'computedBalance'
                row_logic.append(f"BigDecimal {balance_var} = {ordered_values[0]}.subtract({ordered_values[1]});")
        elif len(agg_var_by_table) == 1:
            balance_var = 'computedBalance'
            single_value = next(iter(agg_var_by_table.values()))
            row_logic.append(f"BigDecimal {balance_var} = {single_value};")

        has_business_exception = any(
            str(item.get("type", "")).lower() == "business_exception"
            for item in (semantic.get("error_handling_semantics") or [])
        )
        if not has_business_exception and re.search(r"\braise\s+[A-Za-z_][\w$#]*", raw_plsql, flags=re.IGNORECASE):
            has_business_exception = True
        error_message_literals = self._extract_plsql_error_literals(raw_plsql)
        for idx, literal in enumerate(error_message_literals):
            escaped_literal = self._escape_java_string_literal(literal)
            body_lines.append(f'String preservedPlsqlLiteral{idx} = "{escaped_literal}";')
        negative_balance_message = self._prefer_error_literal(error_message_literals, "negative balance")

        business_exception_name = "BusinessRuleException"
        for item in (semantic.get("error_handling_semantics") or []):
            if str(item.get("type", "")).lower() != "business_exception":
                continue
            raw_name = str(item.get("name", "")).strip()
            if not raw_name:
                continue
            parsed_name = self._to_pascal_case(raw_name)
            business_exception_name = parsed_name if parsed_name.endswith("Exception") else f"{parsed_name}Exception"
            break

        has_negative_balance_rule = any(
            '< 0' in str(rule.get('condition', '')).replace('<=', '<')
            for rule in (semantic.get('business_rules') or [])
        )
        if has_negative_balance_rule:
            has_business_exception = True
        if has_negative_balance_rule and balance_var:
            balance_message = negative_balance_message or self._prefer_error_literal(error_message_literals) or "Negative balance"
            escaped_balance_message = self._escape_java_string_literal(balance_message)
            row_logic.append(
                f'if ({balance_var}.compareTo(BigDecimal.ZERO) < 0) {{ throw new {business_exception_name}("{escaped_balance_message}"); }}'
            )

        if has_merge:
            merge_table_name = merge_table or (target_tables[0] if target_tables else driving_table)
            merge_binding = bindings.get(merge_table_name)
            if merge_binding:
                merge_entity = merge_binding['entity']
                merge_repo_var = merge_binding['repository_var']
                merge_fields = entity_field_types.get(merge_entity, {})
                balance_field = next(
                    (
                        field_name
                        for field_name in merge_fields
                        if normalize_column_name(field_name).lower() == normalize_column_name("balance").lower()
                    ),
                    "",
                )
                created_at_field = next(
                    (
                        field_name
                        for field_name in merge_fields
                        if normalize_column_name(field_name).lower() == normalize_column_name("created_at").lower()
                    ),
                    "",
                )
                updated_at_field = next(
                    (
                        field_name
                        for field_name in merge_fields
                        if normalize_column_name(field_name).lower() == normalize_column_name("updated_at").lower()
                    ),
                    "",
                )
                merge_lookup_keys = self._lookup_keys_for_table(unit, merge_table_name)
                merge_lookup_method = self._expected_lookup_method_name(merge_lookup_keys) if merge_lookup_keys else 'findById'
                merge_repo_code = repositories.get(f"{merge_binding['repository']}.java", '')
                if merge_lookup_method != 'findById' and merge_lookup_method not in merge_repo_code:
                    merge_lookup_method = 'findById'
                merge_args: List[str] = []
                if merge_lookup_method == 'findById':
                    merge_args = ['0L']
                else:
                    merge_entity_types = entity_field_types.get(merge_entity, {})
                    for key in merge_lookup_keys:
                        expected_type = self._resolve_lookup_key_type(key, merge_entity_types)
                        merge_args.append(
                            self._resolve_lookup_argument_expression(
                                column_name=key,
                                driving_fields=driving_fields,
                                param_name_map=param_name_map,
                                expected_type=expected_type,
                                param_specs=parameter_specs,
                                prebound_var=join_var if join_var else None,
                                prebound_column=join_key if join_key else None,
                            )
                        )
                row_logic.append(
                    f"Optional<{merge_entity}> existing = {merge_repo_var}.{merge_lookup_method}({', '.join(merge_args)});"
                )
                row_logic.append('if (existing.isPresent()) {')
                row_logic.append(f"    {merge_entity} target = existing.get();")
                if balance_var and balance_field:
                    row_logic.append(f"    target.set{balance_field[:1].upper() + balance_field[1:]}({balance_var});")
                if updated_at_field:
                    row_logic.append(f"    target.set{updated_at_field[:1].upper() + updated_at_field[1:]}(LocalDateTime.now());")
                row_logic.append(f"    {merge_repo_var}.save(target);")
                row_logic.append('} else {')
                new_target_assignment_lines: List[str] = []
                if join_var and join_key:
                    setter = f"set{join_var[:1].upper() + join_var[1:]}"
                    new_target_assignment_lines.append(f"target.{setter}({join_var});")
                if balance_var and balance_field:
                    new_target_assignment_lines.append(
                        f"target.set{balance_field[:1].upper() + balance_field[1:]}({balance_var});"
                    )
                if created_at_field:
                    new_target_assignment_lines.append(
                        f"target.set{created_at_field[:1].upper() + created_at_field[1:]}(LocalDateTime.now());"
                    )
                if not new_target_assignment_lines:
                    new_target_assignment_lines.extend(
                        self._build_target_population_lines(
                            target_var="target",
                            target_fields=merge_fields,
                            driving_fields=driving_fields,
                            param_name_map=param_name_map,
                        )
                    )
                if new_target_assignment_lines:
                    row_logic.append(f"    {merge_entity} target = new {merge_entity}();")
                    for assignment in new_target_assignment_lines:
                        row_logic.append(f"    {assignment}")
                    row_logic.append(f"    {merge_repo_var}.save(target);")
                else:
                    row_logic.append(f"    {merge_repo_var}.save(row);")
                row_logic.append('}')
        elif target_tables:
            first_target = bindings.get(target_tables[0])
            if first_target:
                target_entity = first_target['entity']
                target_repo_var = first_target['repository_var']
                target_fields = entity_field_types.get(target_entity, {})
                target_population_lines = self._build_target_population_lines(
                    target_var="target",
                    target_fields=target_fields,
                    driving_fields=driving_fields,
                    param_name_map=param_name_map,
                )
                if target_population_lines:
                    row_logic.append(f"{target_entity} target = new {target_entity}();")
                    for assignment in target_population_lines:
                        row_logic.append(assignment)
                    row_logic.append(f"{target_repo_var}.save(target);")
                else:
                    row_logic.append(f"{target_repo_var}.save(row);")

        if audit_binding:
            audit_entity = audit_binding['entity']
            audit_repo_var = audit_binding['repository_var']
            audit_fields = entity_field_types.get(audit_entity, {})
            join_audit_field = next(
                (
                    field_name
                    for field_name in audit_fields
                    if normalize_column_name(field_name).lower() == normalize_column_name(join_key).lower()
                ),
                "",
            ) if join_key else ""
            old_balance_field = next(
                (
                    field_name
                    for field_name in audit_fields
                    if normalize_column_name(field_name).lower() == normalize_column_name("old_balance").lower()
                ),
                "",
            )
            new_balance_field = next(
                (
                    field_name
                    for field_name in audit_fields
                    if normalize_column_name(field_name).lower() == normalize_column_name("new_balance").lower()
                ),
                "",
            )
            action_date_field = next(
                (
                    field_name
                    for field_name in audit_fields
                    if normalize_column_name(field_name).lower() == normalize_column_name("action_date").lower()
                ),
                "",
            )
            row_logic.append(f"{audit_entity} auditRecord = new {audit_entity}();")
            if join_audit_field and join_var:
                row_logic.append(f"auditRecord.set{join_audit_field[:1].upper() + join_audit_field[1:]}({join_var});")
            if old_balance_field:
                row_logic.append(f"auditRecord.set{old_balance_field[:1].upper() + old_balance_field[1:]}(null);")
            if new_balance_field and balance_var:
                row_logic.append(f"auditRecord.set{new_balance_field[:1].upper() + new_balance_field[1:]}({balance_var});")
            if action_date_field:
                row_logic.append(f"auditRecord.set{action_date_field[:1].upper() + action_date_field[1:]}(LocalDateTime.now());")
            row_logic.append(f"{audit_repo_var}.save(auditRecord);")

        if requires_pagination:
            if skip_locked_driving_cursor:
                skip_locked_args: List[str] = []
                for filter_item in cursor_filters:
                    column_name = str(filter_item.get("column", "")).strip()
                    expression = str(filter_item.get("expression", "")).strip()
                    if not column_name:
                        continue
                    expected_type = self._resolve_lookup_key_type(column_name, driving_fields)
                    skip_locked_args.append(
                        self._java_expression_for_filter(expression, param_name_map, expected_type)
                    )
                skip_locked_args.append("PageRequest.of(0, size)")
                fetch_call = f"{driving_repo_var}.{skip_locked_method}({', '.join(skip_locked_args)})"
            else:
                fetch_call = f"{driving_repo_var}.findAll(PageRequest.of(page, size))"
            if requires_batch_transaction:
                body_lines.extend(
                    [
                        'boolean hasMore = true;',
                        'while (hasMore) {',
                        f"    Page<{driving_entity}> pageBatch = {fetch_call};",
                        '    hasMore = pageBatch.hasContent();',
                        '    if (!hasMore) {',
                        '        continue;',
                        '    }',
                        '    final boolean[] batchHasError = new boolean[] { false };',
                        '    batchTransactionTemplate.executeWithoutResult(status -> {',
                        f"        for ({driving_entity} row : pageBatch.getContent()) {{",
                        '            try {',
                    ]
                )
                body_lines.extend(f"                {line}" for line in row_logic)
                if has_business_exception:
                    body_lines.extend(
                        [
                            f'            }} catch ({business_exception_name} e) {{',
                            '                batchHasError[0] = true;',
                            '                saveErrorRecord(e.getMessage());',
                            '                continue;',
                            '            } catch (Exception e) {',
                            '                batchHasError[0] = true;',
                            '                saveErrorRecord("Unexpected error: " + safeMessage(e));',
                            '                continue;',
                            '            }',
                            '        }',
                        ]
                    )
                else:
                    body_lines.extend(
                        [
                            '            } catch (Exception e) {',
                            '                batchHasError[0] = true;',
                            '                saveErrorRecord("Unexpected error: " + safeMessage(e));',
                            '                continue;',
                            '            }',
                            '        }',
                        ]
                    )
                if mode_param:
                    body_lines.extend(
                        [
                            f'        if ({mode_param} != null && !"FULL".equalsIgnoreCase({mode_param})) {{',
                            '            status.setRollbackOnly();',
                            '        }',
                        ]
                    )
                body_lines.extend(
                    [
                        '        if (batchHasError[0]) {',
                        '            status.setRollbackOnly();',
                        '        }',
                        '    });',
                        '    hasError = hasError || batchHasError[0];',
                    ]
                )
                if not skip_locked_driving_cursor:
                    body_lines.append('    page++;')
                body_lines.append('}')
            else:
                body_lines.extend(
                    [
                        'boolean hasMore = true;',
                        'while (hasMore) {',
                        '    boolean batchHasError = false;',
                        f"    Page<{driving_entity}> pageBatch = {fetch_call};",
                        '    hasMore = pageBatch.hasContent();',
                        f"    for ({driving_entity} row : pageBatch.getContent()) {{",
                        '        try {',
                    ]
                )
                body_lines.extend(f"            {line}" for line in row_logic)
                if has_business_exception:
                    body_lines.extend(
                        [
                            f'        }} catch ({business_exception_name} e) {{',
                            '            batchHasError = true;',
                            '            saveErrorRecord(e.getMessage());',
                            '            continue;',
                            '        } catch (Exception e) {',
                            '            batchHasError = true;',
                            '            saveErrorRecord("Unexpected error: " + safeMessage(e));',
                            '            continue;',
                            '        }',
                            '    }',
                        ]
                    )
                else:
                    body_lines.extend(
                        [
                            '        } catch (Exception e) {',
                            '            batchHasError = true;',
                            '            saveErrorRecord("Unexpected error: " + safeMessage(e));',
                            '            continue;',
                            '        }',
                            '    }',
                        ]
                    )
                if mode_param:
                    body_lines.extend(
                        [
                            f'    if ({mode_param} != null) {{',
                            f'        if ("FULL".equalsIgnoreCase({mode_param}) && !batchHasError) {{',
                            '            // commit boundary handled per batch',
                            '        } else {',
                            '            // rollback boundary handled per batch',
                            '        }',
                            '    }',
                        ]
                    )
                body_lines.extend(
                    [
                        '    hasError = hasError || batchHasError;',
                    ]
                )
                if not skip_locked_driving_cursor:
                    body_lines.append('    page++;')
                body_lines.append('}')
        else:
            if requires_batch_transaction:
                body_lines.extend(
                    [
                        'final boolean[] batchHasError = new boolean[] { false };',
                        'batchTransactionTemplate.executeWithoutResult(status -> {',
                        f'    List<{driving_entity}> fallbackRows = {driving_repo_var}.findAll(PageRequest.of(0, size)).getContent();',
                        f'    for ({driving_entity} row : fallbackRows) {{',
                        '        try {',
                    ]
                )
                body_lines.extend(f"            {line}" for line in row_logic)
                if has_business_exception:
                    body_lines.extend(
                        [
                            f'        }} catch ({business_exception_name} e) {{',
                            '            batchHasError[0] = true;',
                            '            saveErrorRecord(e.getMessage());',
                            '            continue;',
                            '        } catch (Exception e) {',
                            '            batchHasError[0] = true;',
                            '            saveErrorRecord("Unexpected error: " + safeMessage(e));',
                            '            continue;',
                            '        }',
                            '    }',
                        ]
                    )
                else:
                    body_lines.extend(
                        [
                            '        } catch (Exception e) {',
                            '            batchHasError[0] = true;',
                            '            saveErrorRecord("Unexpected error: " + safeMessage(e));',
                            '            continue;',
                            '        }',
                            '    }',
                        ]
                    )
                if mode_param:
                    body_lines.extend(
                        [
                            f'    if ({mode_param} != null && !"FULL".equalsIgnoreCase({mode_param})) {{',
                            '        status.setRollbackOnly();',
                            '    }',
                        ]
                    )
                body_lines.extend(
                    [
                        '    if (batchHasError[0]) {',
                        '        status.setRollbackOnly();',
                        '    }',
                        '});',
                        'hasError = hasError || batchHasError[0];',
                    ]
                )
            else:
                body_lines.extend(
                    [
                        f'List<{driving_entity}> fallbackRows = {driving_repo_var}.findAll(PageRequest.of(0, size)).getContent();',
                        f'for ({driving_entity} row : fallbackRows) {{',
                        '    try {',
                    ]
                )
                body_lines.extend(f"        {line}" for line in row_logic)
                if has_business_exception:
                    body_lines.extend(
                        [
                            f'    }} catch ({business_exception_name} e) {{',
                            '        hasError = true;',
                            '        saveErrorRecord(e.getMessage());',
                            '        continue;',
                            '    } catch (Exception e) {',
                            '        hasError = true;',
                            '        saveErrorRecord("Unexpected error: " + safeMessage(e));',
                            '        continue;',
                            '    }',
                            '}',
                        ]
                    )
                else:
                    body_lines.extend(
                        [
                            '    } catch (Exception e) {',
                            '        hasError = true;',
                            '        saveErrorRecord("Unexpected error: " + safeMessage(e));',
                            '        continue;',
                            '    }',
                            '}',
                        ]
                    )

        method_body = "\n".join(f"        {line}" for line in body_lines)
        constructor_args = ", ".join(constructor_lines)
        field_block = "\n".join(field_lines)
        init_block = "\n".join(init_lines)
        helper_methods: List[str] = []
        if error_binding:
            error_entity = error_binding['entity']
            error_repo_var = error_binding['repository_var']
            error_fields = entity_field_types.get(error_entity, {})
            error_message_field = next(
                (
                    field_name
                    for field_name in error_fields
                    if normalize_column_name(field_name).lower() == normalize_column_name("error_message").lower()
                ),
                "",
            )
            error_date_field = next(
                (
                    field_name
                    for field_name in error_fields
                    if normalize_column_name(field_name).lower() == normalize_column_name("error_date").lower()
                ),
                "",
            )
            helper_lines = [
                "    private void saveErrorRecord(String message) {",
                f"        {error_entity} errorRecord = new {error_entity}();",
            ]
            if error_message_field:
                helper_lines.append(
                    f"        errorRecord.set{error_message_field[:1].upper() + error_message_field[1:]}(message);"
                )
            if error_date_field:
                helper_lines.append(
                    f"        errorRecord.set{error_date_field[:1].upper() + error_date_field[1:]}(LocalDateTime.now());"
                )
            helper_lines.append(f"        {error_repo_var}.save(errorRecord);")
            helper_lines.append("    }")
            helper_methods.append("\n".join(helper_lines))
        else:
            helper_methods.append(
                "\n".join(
                    [
                        "    private void saveErrorRecord(String message) {",
                        "        // No error table discovered for this unit.",
                        "    }",
                    ]
                )
            )
        helper_methods.append(
            "\n".join(
                [
                    "    private String safeMessage(Exception exception) {",
                    "        return exception.getMessage() != null ? exception.getMessage() : exception.getClass().getSimpleName();",
                    "    }",
                ]
            )
        )
        if has_business_exception:
            helper_methods.append(
                "\n".join(
                    [
                        f"    private static final class {business_exception_name} extends RuntimeException {{",
                        f"        private {business_exception_name}(String message) {{",
                        "            super(message);",
                        "        }",
                        "    }",
                    ]
                )
            )
        helper_block = "\n\n".join(helper_methods)
        generated_symbols = "\n".join(
            [
                method_params,
                field_block,
                init_block,
                method_body,
                helper_block,
            ]
        )
        if "LocalDateTime" in generated_symbols:
            imports.add('import java.time.LocalDateTime;')
        if "BigDecimal" in generated_symbols:
            imports.add('import java.math.BigDecimal;')
        if "Optional<" in generated_symbols or "Optional." in generated_symbols:
            imports.add('import java.util.Optional;')
        if "PageRequest" in generated_symbols:
            imports.add('import org.springframework.data.domain.PageRequest;')
        if "Page<" in generated_symbols:
            imports.add('import org.springframework.data.domain.Page;')
        method_annotation = "    @Transactional\n" if requires_transactional_method else ""
        return (
            f"package {package_name}.service;\n\n"
            f"{chr(10).join(sorted(imports))}\n\n"
            "@Service\n"
            f"public class {service_name} {{\n\n"
            f"{field_block}\n\n"
            f"    public {service_name}({constructor_args}) {{\n"
            f"{init_block}\n"
            "    }\n\n"
            f"{method_annotation}    public void {method_name}({method_params}) {{\n"
            f"{method_body}\n"
            "    }\n\n"
            f"{helper_block}\n"
            "}\n"
        )

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
        return normalize_column_name(value)

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
            'LocalTime': 'java.time.LocalTime.now()',
            'LocalDate': 'java.time.LocalDate.now()',
            'void': '',
        }
        return defaults.get(java_type, 'null')

    def _to_pascal_case(self, value: str) -> str:
        return to_pascal_case(value) or 'Generated'

    def _to_camel_case(self, value: str) -> str:
        pascal = self._to_pascal_case(value)
        return pascal[:1].lower() + pascal[1:] if pascal else 'generated'

    def _lower_first(self, value: str) -> str:
        return value[:1].lower() + value[1:] if value else value

    def _escape_java_comment(self, value: str) -> str:
        return (value or '').replace('*/', '* /').replace('\r', ' ').replace('\n', ' ')

    def _escape_java_string_literal(self, value: str) -> str:
        return (value or "").replace("\\", "\\\\").replace('"', '\\"')

    def _extract_plsql_error_literals(self, raw_plsql: str) -> List[str]:
        literals: List[str] = []
        for match in re.finditer(
            r"\braise_application_error\s*\(\s*[^,]+,\s*([\s\S]*?)\)",
            raw_plsql or "",
            flags=re.IGNORECASE,
        ):
            argument_expression = match.group(1) or ""
            for literal_match in re.finditer(r"'((?:''|[^'])*)'", argument_expression):
                candidate = literal_match.group(1).replace("''", "'")
                if candidate and candidate not in literals:
                    literals.append(candidate)
        return literals

    def _prefer_error_literal(self, literals: List[str], keyword: str = "") -> str:
        if not literals:
            return ""
        normalized_keyword = (keyword or "").strip().lower()
        if normalized_keyword:
            for literal in literals:
                if normalized_keyword in literal.lower():
                    return literal
        return literals[0]

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
            "You are repairing a generated Java Spring Boot project with one objective: 0 compile errors.\n"
            "Treat compilation success as the only priority for this pass.\n"
            "Do not optimize architecture, style, or feature completeness unless required to remove a compiler error.\n"
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
            "5. Fix the reported build/compiler errors directly and aggressively.\n"
            "6. Prefer the smallest safe edit that removes a compile error.\n"
            "7. If a method, annotation block, or trailing fragment is incomplete or syntactically broken, complete it or remove the broken fragment.\n"
            "8. If a type is used but not imported, add the exact missing import.\n"
            "9. In service classes, if Optional<...>, Optional., or Optional(...) appears, ensure `import java.util.Optional;` exists.\n"
            "10. If imports are missing in a Java file that needs them, create a valid import section directly below the package declaration.\n"
            "11. If a class/entity/repository name does not exist, replace it with the real existing generated class name instead of inventing a new one.\n"
            "12. If an argument list, method signature, or generic type does not match existing code, rewrite it to match the declared existing signature exactly.\n"
            "13. If the code references undefined local variables, replace them with existing in-scope variables or compile-safe literals/constants.\n"
            "14. If a field accessor/mutator does not exist, switch to a real existing accessor/mutator or remove that line.\n"
            "15. Never leave a file half-written. Every edited Java file must end with balanced braces and valid syntax.\n"
            "16. In service classes, replace TODOs, placeholders, disconnected branches, and no-op CRUD logic with actual repository calls whenever the repository method already exists.\n"
            "17. In service classes, prefer calling existing custom repository methods first; if none exist, use findById/save/deleteById as the compile-safe fallback.\n"
            "18. If a service is not calling its repository at all, wire it to the matching repository instead of leaving the logic disconnected.\n"
            "19. Do not make speculative runtime/business-logic improvements in this pass.\n"
            "20. Focus first on the files named in the compiler output. Do not touch unrelated files unless one of those files cannot compile without it.\n"
            "21. Assume the build will be rerun immediately. Your response should maximize the chance that the next compile has fewer errors, ideally zero.\n\n"
            "Common compile-only fixes allowed in this pass:\n"
            "- add missing imports such as Optional, LocalTime, Timestamp, BigDecimal, Arrays, ArrayList, Pattern, AtomicReference\n"
            "- fix truncated repository/service/interface/class files\n"
            "- replace wrong lowercase entity names in JpaRepository generics/imports\n"
            "- remove duplicate annotations on a single repository method\n"
            "- rewrite wrong repository call arguments to match the actual signature\n"
            "- replace undefined placeholders with compile-safe literals\n"
            "- replace getId()/setStatus() style calls with real existing entity accessors when necessary\n"
            "- replace disconnected service stubs with actual repository invocations when matching repository methods already exist\n\n"
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
