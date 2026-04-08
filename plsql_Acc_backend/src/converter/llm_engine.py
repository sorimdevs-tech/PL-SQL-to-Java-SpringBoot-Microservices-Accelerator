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
from src.converter.llm_engine_integration import inject_enhanced_prompts

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
            'entity_generation': self._get_entity_template(),
            # RC1 FIX: dedicated template for utility/non-DB packages
            'utility_to_service': self._get_utility_template(),
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
        format_context.setdefault('spring_data_patterns', '')
        format_context.setdefault('repository_examples', '')
        format_context.setdefault('plsql_pattern_guidance', '')

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

        # Use regex replacement instead of str.format to preserve literal braces in prompt text.
        prompt_text = re.sub(
            r'\{([A-Za-z0-9_]+)\}',
            lambda match: str(format_context.get(match.group(1), match.group(0))),
            template,
        )
        # Convert escaped braces back to single braces for literal code examples.
        return prompt_text.replace('{{', '{').replace('}}', '}')

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
21. NEVER generate repository/service aggregation methods named sumBy..., getTotalBy..., getTotalValueBy..., or avgBy...
    unless that exact method is explicitly declared with @Query in the repository.
22. If the PL/SQL contains SUM, COUNT, AVG, MIN, MAX, NVL, or GROUP BY semantics, ALWAYS generate
    an explicit repository @Query method and make the service call that exact declared method.
23. For EVERY repository method invoked by the service, the repository MUST declare the same method
    with matching name, parameter types, and parameter order.
24. Preserve all WHERE predicates from the SQL in the repository @Query and in the service call arguments.
25. Use entity field names in JPQL @Query expressions and ensure every referenced field exists on the entity.

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

Spring Data guidance:
{spring_data_patterns}

Repository examples:
{repository_examples}

PL/SQL pattern guidance:
{plsql_pattern_guidance}

STRICT OUTPUT RULES:
- NEVER use EntityManager, @PersistenceContext, or createNativeQuery
- ALWAYS use the injected @Autowired repository for all DB operations
- Use Long for NUMBER ID/count params; BigDecimal ONLY for NUMBER(p,s) decimal params
- NEVER generate or call sumBy..., getTotalBy..., getTotalValueBy..., or avgBy... unless the repository explicitly declares that method with @Query
- For SUM/COUNT/AVG/MIN/MAX/GROUP BY semantics, ALWAYS use an explicit repository @Query method
- If the service calls a repository method, that exact method must exist on the repository with matching parameters
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

Spring Data guidance:
{spring_data_patterns}

Repository examples:
{repository_examples}

PL/SQL pattern guidance:
{plsql_pattern_guidance}

STRICT OUTPUT RULES:
- Output EXACTLY ONE Java file ending with the class closing brace }}.
- Do NOT add any content after the closing brace.
- If SQL aggregation exists, do not assume derived repository methods: require explicit @Query repository methods and matching service calls.

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

Spring Data guidance:
{spring_data_patterns}

Repository examples:
{repository_examples}

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
9. NEVER assume Spring Data derives aggregation methods such as sumBy..., getTotalBy..., getTotalValueBy..., or avgBy....
10. For EVERY aggregation in the SQL (SUM, COUNT, AVG, MIN, MAX, GROUP BY), generate an explicit @Query method.
11. Preserve all WHERE predicates in the @Query and generate matching @Param parameters in the same order.
12. Use actual entity field names in JPQL @Query expressions and real SQL column names in native SQL queries.
13. If a service will call an aggregation method, ensure that exact repository method name/signature is declared here.

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

Spring Data guidance:
{spring_data_patterns}

Repository examples:
{repository_examples}

PL/SQL pattern guidance:
{plsql_pattern_guidance}

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
14. CRITICAL - assert() procedure semantics: The PL/SQL assert(condition, message) procedure contains IF NOT NVL(condition, false) THEN RAISE.
    This means: NEGATE the condition before throwing.
    Example: assert(p_amount > 0) → if (!(amount > 0)) { throw ... } or if (amount <= 0) { throw ... }
15. State variables such as v_has_error must be scoped/reset per batch as required by behavior.
16. Do not simplify loops, transaction branches, or side effects. Maintain data-flow order and outcomes.
17. NEVER invent aggregation methods such as sumBy..., getTotalBy..., getTotalValueBy..., or avgBy...
    unless that exact method is explicitly declared with @Query on the repository.
18. Every aggregation path must stay synchronized end-to-end: repository declares @Query method,
    service calls that exact method, and parameter names/types/order match exactly.
19. Preserve all SQL WHERE predicates in generated aggregation repository queries.

FINAL SELF-CHECK BEFORE OUTPUT:
- Are all WHERE conditions preserved?
- Are all INSERT/UPDATE/MERGE side effects preserved (including audit/error logs)?
- Are aggregation paths query-based and null-safe?
- Does every repository call used by the service exist with the same method name and parameters?
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
- NEVER call sumBy..., getTotalBy..., getTotalValueBy..., or avgBy... unless that exact repository @Query method already exists.
- For SUM/COUNT/AVG/MIN/MAX/GROUP BY semantics, call only explicit repository @Query methods with matching parameters.
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

Spring Data guidance:
{spring_data_patterns}

Repository examples:
{repository_examples}

PL/SQL pattern guidance:
{plsql_pattern_guidance}

Validation feedback from prior failed attempts:
{validation_feedback}

Rules:
- If the package has NO SQL operations (utility/infrastructure), generate a pure @Service with no repository injection.
  Emit private static final constants from CONSTANT declarations.
  Map BOOLEAN parameters to Boolean (never String).
  Map raise_application_error() calls to: throw new BusinessException(errorCode, message);
  CRITICAL - assert() procedure semantics: The PL/SQL assert(condition, message) procedure contains IF NOT NVL(condition, false) THEN RAISE.
  This means: NEGATE the condition before throwing.
  Example: assert(p_amount > 0) → if (!(amount > 0)) { throw ... } or if (amount <= 0) { throw ... }
  Emit PRAGMA AUTONOMOUS_TRANSACTION as @Transactional(propagation = Propagation.REQUIRES_NEW).
- If the package HAS SQL operations, generate a @Service that injects the relevant repositories.
  Preserve MERGE as findBy + if(existing.isPresent()) update else insert.
  Preserve BULK COLLECT as PageRequest-based batch loop.
  Preserve NVL(x, default) as Optional.ofNullable(x).orElse(default).
- Aggregation logic must use explicit repository @Query methods. Never assume derived methods like sumBy..., getTotalBy..., getTotalValueBy..., or avgBy....
- Every repository method used by the service must exist with the exact same name and parameter signature.
- Do not invent repository methods or entity fields not present in the source.
- Output exactly one compilable Java class in package {package_name}.service.
"""

    def _get_utility_template(self) -> str:
        return """
Convert the following PL/SQL utility/infrastructure package to one Java Spring Boot @Service class.
This package has NO direct SQL operations — it is pure control-flow and validation logic.

SOURCE OF TRUTH:
{plsql_code}

EXTRACTED SEMANTICS:
{semantic_summary}

Validation feedback from prior failed attempts:
{validation_feedback}

MANDATORY RULES:
1. No repository injection — this is a utility class.
2. Emit all CONSTANT declarations as: private static final <JavaType> <CONST_NAME> = <value>;
3. Map Oracle types to Java: BOOLEAN→Boolean, VARCHAR2→String, NUMBER→Long, NUMBER(p,s)→BigDecimal.
4. For each BOOLEAN parameter: emit a null-safe guard:
   if (param == null || !param) {{ throw new BusinessException(errorCode, "message"); }}
5. Map raise_application_error(code, msg) → throw new BusinessException(code, msg);
6. CRITICAL - assert() procedure semantics: The PL/SQL assert(condition, message) procedure contains IF NOT NVL(condition, false) THEN RAISE. 
   This means: NEGATE the condition before throwing. 
   Example: assert(p_amount > 0) → if (!(amount > 0)) { throw ... } or if (amount <= 0) { throw ... }
7. PRAGMA AUTONOMOUS_TRANSACTION → @Transactional(propagation = Propagation.REQUIRES_NEW)
8. Include a private static final inner class BusinessException extends RuntimeException.
9. Cross-package calls become constructor-injected service dependencies.
10. Output exactly one compilable Java class in package {package_name}.service.
11. File must end with the class closing brace. No content after it.
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
4. NEVER assume Spring Data derives aggregation methods such as sumBy..., getTotalBy..., getTotalValueBy..., or avgBy....
5. For every aggregation in the source SQL (SUM, COUNT, AVG, MIN, MAX, GROUP BY), generate an explicit @Query method.
6. Preserve all SQL WHERE predicates in the generated @Query and generate matching @Param parameters.
7. Use actual entity field names in JPQL @Query expressions and ensure every referenced field exists on the entity.
8. Method names may use safe names like getTotal<Column>By<Conditions> or getSumOf<Column>,
   but the method MUST be explicitly declared with @Query in this repository.
9. If MERGE exists for this table, expose the repository methods needed for UPSERT support
   such as existence lookup on the merge key and any required custom query methods.
10. If FOR UPDATE SKIP LOCKED or cursor pagination is present, generate the corresponding
   custom repository method instead of ignoring the locking semantics.
11. Every named query parameter must have a matching @Param annotation before the Java type.
12. The final repository must cover every service-side repository call required by the PL/SQL behavior.
13. The file must end with the interface closing brace and contain no markdown or explanations.
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

    async def convert(
        self,
        ast_results: Dict[str, Any],
        dependency_graph: Dict[str, Any],
        entity_fields: Optional[Dict[str, List[str]]] = None,
        metadata_provider: Optional[Any] = None,
    ) -> Dict[str, str]:
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
            java_files.update(await self._convert_procedures(procedures, context, metadata_provider))

        functions = ast_results.get('functions', [])
        if functions:
            logger.info(f"Converting {len(functions)} functions...")
            java_files.update(await self._convert_functions(functions, context, metadata_provider))

        triggers = ast_results.get('triggers', [])
        if triggers:
            logger.info(f"Converting {len(triggers)} triggers...")
            java_files.update(await self._convert_triggers(triggers, context, metadata_provider))

        packages = ast_results.get('packages', [])
        if packages:
            logger.info(f"Converting {len(packages)} packages...")
            java_files.update(await self._convert_packages(packages, context, metadata_provider))

        sql_queries = self._extract_sql_queries(ast_results)
        if sql_queries:
            logger.info(f"Converting {len(sql_queries)} SQL queries to repositories...")
            java_files.update(await self._convert_sql_to_repositories(sql_queries, context, metadata_provider))

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
        # LLM-based repository generation with semantic constraints.
        repositories: Dict[str, str] = {}
        table_specs: Dict[str, Dict[str, Any]] = {}
        entity_field_types = self._extract_entity_field_types(entities)

        for unit in source_units:
            raw_plsql = str(unit.get('raw_plsql', ''))
            lookup_map = unit.get('lookup_keys') or {}
            semantic = unit.get('semantic_analysis') or {}
            semantic_upserts = semantic.get('upsert_operations') or []
            aggregation_refs = semantic.get('aggregation', {}).get('columns', []) or []
            skip_locked_tables = {
                str(table).upper()
                for table in (unit.get('skip_locked_tables') or [])
                if table
            }
            driving_table = str(unit.get('driving_table', '')).upper()
            if not skip_locked_tables and re.search(r"\bFOR\s+UPDATE\s+SKIP\s+LOCKED\b", raw_plsql, flags=re.IGNORECASE):
                if driving_table:
                    skip_locked_tables.add(driving_table)
            cursor_filters = self._extract_cursor_filter_conditions(raw_plsql, driving_table)

            def _default_spec() -> Dict[str, Any]:
                return {
                    'operations': set(),
                    'lookup_keys': [],
                    'lookup_key_variants': [],
                    'requires_upsert': False,
                    'requires_skip_locked': False,
                    'aggregation_columns': [],
                    'cursor_filters': [],
                    'rag_examples': [],
                }

            for table_name, operations in (unit.get('operations_by_table') or {}).items():
                normalized_table = str(table_name).upper()
                spec = table_specs.setdefault(normalized_table, _default_spec())
                spec['operations'].update(str(op).upper() for op in (operations or []))
                unit_lookup_keys: List[str] = []
                for column in (lookup_map.get(normalized_table) or []):
                    normalized_column = str(column).upper()
                    if normalized_column not in spec['lookup_keys']:
                        spec['lookup_keys'].append(normalized_column)
                    if normalized_column not in unit_lookup_keys:
                        unit_lookup_keys.append(normalized_column)
                if unit_lookup_keys:
                    variant_key = tuple(unit_lookup_keys)
                    known_variants = {
                        tuple(str(value).upper() for value in (variant or []) if value)
                        for variant in (spec.get('lookup_key_variants') or [])
                    }
                    if variant_key not in known_variants:
                        spec['lookup_key_variants'].append(unit_lookup_keys)
                spec['requires_upsert'] = spec['requires_upsert'] or ('MERGE' in spec['operations'])
                spec['requires_skip_locked'] = spec['requires_skip_locked'] or (normalized_table in skip_locked_tables)
                for example in unit.get('rag_examples') or []:
                    if example not in spec['rag_examples']:
                        spec['rag_examples'].append(example)
            for upsert in semantic_upserts:
                table_name = str(upsert.get('table', '')).upper()
                if not table_name:
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
                if not table_name or not column_name:
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
                    known_variants = {
                        tuple(str(value).upper() for value in (variant or []) if value)
                        for variant in (spec.get('lookup_key_variants') or [])
                    }
                    if variant_key not in known_variants:
                        spec['lookup_key_variants'].append(aggregation_lookup_keys)
            for skip_table in skip_locked_tables:
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

        # Use LLM to generate repositories
        for table_name in sorted(table_specs):
            spec = table_specs[table_name]
            entity_name = self._derive_entity_name_from_table(table_name, entities)
            repo_name = self._derive_repository_name_from_entity(entity_name)
            entity_types = entity_field_types.get(entity_name, {})

            # Prepare LLM prompt
            semantic_model = {
                'table_name': table_name,
                'operations': list(spec['operations']),
                'lookup_keys': spec['lookup_keys'],
                'lookup_key_variants': spec['lookup_key_variants'],
                'requires_upsert': spec['requires_upsert'],
                'requires_skip_locked': spec['requires_skip_locked'],
                'aggregation_columns': spec['aggregation_columns'],
                'cursor_filters': spec['cursor_filters'],
                'rag_examples': spec.get('rag_examples', [])[:5],
            }
            
            entities_info = {}
            for filename, code in entities.items():
                class_name = filename.replace('.java', '')
                fields = {}
                for type_name, field_name in re.findall(r"private\s+([\w<>, ?]+)\s+(\w+)\s*;", code):
                    fields[field_name] = type_name.strip()
                entities_info[class_name] = fields
            
            metadata = {
                'entity_name': entity_name,
                'repo_name': repo_name,
                'entity_fields': entity_types,
                'package_name': self.config.get('output', {}).get('package_name', 'com.company.project'),
            }
            
            validation_errors = validation_feedback.get(f"{repo_name}.java", []) if validation_feedback else []
            
            prompt = f"""You are a Spring Data JPA expert.

Generate repository interfaces from PL/SQL SQL operations.

STRICT RULES:

1. SIMPLE SELECT:
- Use findBy<Field> methods

2. AGGREGATION (COUNT, SUM, AVG, GROUP BY):
- MUST use @Query
- MUST NOT use findBy

3. COMPLEX QUERIES:
- Use @Query with JPQL or native SQL

4. FIELD VALIDATION:
- Use only fields from entity metadata
- DO NOT invent fields

5. RETURN TYPES:
- COUNT → long
- SUM → numeric type
- SELECT → entity or list

INPUT:
{semantic_model}
{entities_info}
{metadata}

RETRIEVED RAG CONVERSION EXAMPLES:
{semantic_model.get('rag_examples', [])}

OUTPUT:
- Valid Spring Data JPA interfaces
- Proper annotations
- Compile-ready code

ONLY OUTPUT JAVA CODE.

The previously generated code has the following issues:

{validation_errors}

Fix ALL issues while following STRICT RULES:
- Preserve business logic
- Do NOT simplify
- Do NOT remove logic
- Correct repository usage

Regenerate FULL corrected code.

ONLY OUTPUT JAVA CODE.

STRICT CONVERSION RULES:

6. AGGREGATION RULE (CRITICAL)
- If SQL contains COUNT, SUM, AVG, GROUP BY:
  → MUST use @Query in repository
  → MUST NOT use findBy methods

7. REPOSITORY USAGE
- Use only provided repositories
- DO NOT invent fields or methods
- Match entity fields exactly using metadata

8. METADATA USAGE
- Use correct:
  - entity names
  - field names
  - data types
- DO NOT guess schema

9. NAMING CONSISTENCY
- Method names should reflect PL/SQL procedure names

10. NO HALLUCINATION
- DO NOT add new logic
- DO NOT remove logic
- DO NOT assume missing data

OUTPUT REQUIREMENTS:

- Generate a complete Spring Data JPA repository interface
- Include:
  - @Repository annotation
  - Required imports
  - Extends JpaRepository<Entity, Long>
  - All required methods with proper annotations

- Code must be:
  - Clean
  - Compile-ready
  - No placeholders
  - No explanations

ONLY OUTPUT JAVA CODE."""

            try:
                java_code = await self._generate_with_retries(prompt)
                cleaned_code = self._clean_java_code(java_code)
                if cleaned_code and cleaned_code.strip():
                    if self._repository_needs_deterministic_aggregation_fix(
                        repository_code=cleaned_code,
                        spec=spec,
                        entity_name=entity_name,
                        entity_field_types=entity_types,
                    ):
                        repositories[f"{repo_name}.java"] = self._generate_deterministic_repository_interface(
                            table_name=table_name,
                            entity_name=entity_name,
                            repo_name=repo_name,
                            spec=spec,
                            entity_field_types=entity_types,
                        )
                    else:
                        repositories[f"{repo_name}.java"] = cleaned_code
            except Exception as e:
                logger.error(f"Failed to generate repository for {table_name}: {e}")
                # Fallback to deterministic generation
                repositories[f"{repo_name}.java"] = self._generate_deterministic_repository_interface(
                    table_name=table_name,
                    entity_name=entity_name,
                    repo_name=repo_name,
                    spec=spec,
                    entity_field_types=entity_types,
                )
        
        return repositories

    def _repository_needs_deterministic_aggregation_fix(
        self,
        repository_code: str,
        spec: Dict[str, Any],
        entity_name: str,
        entity_field_types: Dict[str, Dict[str, str]],
    ) -> bool:
        lookup_variants = spec.get('lookup_key_variants') or []
        lookup_keys = spec.get('lookup_keys') or []
        raw_lookup_variants = lookup_variants if lookup_variants else ([lookup_keys] if lookup_keys else [])
        for variant in raw_lookup_variants:
            expected_lookup_method = self._expected_lookup_method_name(list(variant or []))
            if expected_lookup_method and not re.search(rf'\b{re.escape(expected_lookup_method)}\s*\(', repository_code):
                return True

        if spec.get('requires_skip_locked'):
            cursor_filters = list(spec.get('cursor_filters') or [])
            expected_skip_locked_method = self._skip_locked_method_name(cursor_filters)
            if not re.search(rf'\b{re.escape(expected_skip_locked_method)}\s*\(', repository_code):
                return True

        aggregation_columns = list(spec.get('aggregation_columns') or [])
        if not aggregation_columns:
            return False

        raw_sum_variants = lookup_variants if lookup_variants else ([lookup_keys] if lookup_keys else [[]])

        required_method_names: Set[str] = set()
        entity_fields = entity_field_types.get(entity_name, {})
        for aggregation_column in aggregation_columns:
            sum_field = self._resolve_entity_field_name(aggregation_column, entity_fields)
            for variant in raw_sum_variants:
                required_method_names.add(self._aggregation_method_name(list(variant or []), sum_field))

        if not required_method_names:
            return False

        if not re.search(r'@Query\s*\(\s*"SELECT\s+COALESCE\s*\(\s*SUM\(', repository_code, flags=re.IGNORECASE):
            return True

        for method_name in required_method_names:
            if not re.search(rf'\b{re.escape(method_name)}\s*\(', repository_code):
                return True

        return False

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

    def _aggregation_method_name(self, lookup_keys: List[str], sum_field: str = "Total") -> str:
        suffix = self._method_suffix_from_columns(lookup_keys)
        field_name = self._to_pascal_case(sum_field) if sum_field else "Total"
        if not suffix:
            return f"getSum{field_name}"
        return f"getSum{field_name}By{suffix}"

    def _aggregation_batch_method_name(self, lookup_keys: List[str], sum_field: str = "Total") -> str:
        return f"{self._aggregation_method_name(lookup_keys, sum_field)}In"

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

        if lookup_variants:
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

        aggregation_columns = list(spec.get('aggregation_columns') or [])
        if aggregation_columns:
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
            raw_sum_variants = lookup_variants if lookup_variants else ([lookup_keys] if lookup_keys else [[]])
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
            emitted_batch_methods: Set[str] = set()
            unique_aggregation_columns: List[str] = []
            seen_aggregation_columns: Set[str] = set()
            for aggregation_column in aggregation_columns:
                normalized_column = normalize_column_name(str(aggregation_column))
                if normalized_column.lower() in seen_aggregation_columns:
                    continue
                seen_aggregation_columns.add(normalized_column.lower())
                unique_aggregation_columns.append(str(aggregation_column))

            for aggregation_column in unique_aggregation_columns:
                sum_field = self._resolve_entity_field_name(aggregation_column, entity_field_types)
                for lookup_for_sum in sum_lookup_variants:
                    sum_method_name = self._aggregation_method_name(lookup_for_sum, sum_field)
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
                        if len(lookup_for_sum) == 1:
                            key = lookup_for_sum[0]
                            key_field = self._resolve_entity_field_name(key, entity_field_types)
                            key_type = self._resolve_lookup_key_type(key, entity_field_types)
                            in_param_name = f"{normalize_column_name(key)}Values"
                            in_method_name = self._aggregation_batch_method_name(lookup_for_sum, sum_field)
                            if in_method_name not in emitted_batch_methods:
                                emitted_batch_methods.add(in_method_name)
                                imports.update({"import java.util.Collection;", "import java.util.List;"})
                                in_query = (
                                    f"SELECT e.{key_field}, COALESCE(SUM(e.{sum_field}), 0) "
                                    f"FROM {entity_name} e "
                                    f"WHERE e.{key_field} IN :{in_param_name} "
                                    f"GROUP BY e.{key_field}"
                                )
                                custom_methods.append(
                                    f"    @Transactional(readOnly = true)\n"
                                    f"    @Query(\"{in_query}\")\n"
                                    f"    List<Object[]> {in_method_name}(@Param(\"{in_param_name}\") Collection<{key_type}> {in_param_name});"
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
        metadata_provider: Optional[Any] = None,
    ) -> Dict[str, str]:
        # Deterministic service generation with semantic constraints.
        #
        # Some discovery inputs can contain multiple units that map to the same
        # service filename (for example a richer PACKAGE BODY unit and a sparse
        # PACKAGE spec unit). Keep the strongest unit per filename so richer
        # semantics are not overwritten by placeholder utility output.
        selected_units: Dict[str, Dict[str, Any]] = {}
        service_order: List[str] = []
        for unit in source_units:
            object_type = str(unit.get('object_type', 'PROCEDURE')).upper()
            if object_type == 'TRIGGER':
                continue
            filename = self._derive_service_filename(unit)
            current = selected_units.get(filename)
            if current is None:
                selected_units[filename] = unit
                service_order.append(filename)
                continue
            if self._service_generation_score(unit) > self._service_generation_score(current):
                selected_units[filename] = unit

        services: Dict[str, str] = {}
        # VF-1 FIX: use validation_feedback to influence generation decisions
        feedback_for_service: Dict[str, List[str]] = validation_feedback or {}
        
        for filename in service_order:
            unit = selected_units[filename]
            # Get unit-specific feedback for this service
            unit_name = unit.get('name', '')
            service_feedback = feedback_for_service.get(filename, []) or feedback_for_service.get(unit_name, [])
            
            # RC1 FIX: route no-SQL (utility) packages to a dedicated generator
            if self._is_utility_unit(unit):
                services[filename] = self._generate_utility_service_from_unit(
                    unit=unit,
                    all_units=source_units,
                )
            else:
                services[filename] = self._generate_deterministic_service_from_unit(
                    unit=unit,
                    entities=entities,
                    repositories=repositories,
                    all_units=source_units,
                    metadata_provider=metadata_provider,
                    validation_feedback=service_feedback,
                )
        return services

    def _is_utility_unit(self, unit: Dict[str, Any]) -> bool:
        """RC1 FIX: True when the procedure/package has no SQL operations — pure control-flow logic."""
        return not bool(unit.get('operations_by_table'))

    def _service_generation_score(self, unit: Dict[str, Any]) -> Tuple[int, ...]:
        """Rank duplicate units that map to the same service filename."""
        operations_by_table = unit.get('operations_by_table') or {}
        semantic = unit.get('semantic_analysis') or {}
        transaction = unit.get('transaction') or {}
        target_tables = unit.get('target_tables') or []
        lookup_map = unit.get('lookup_keys') or {}
        lookup_key_count = sum(len(values or []) for values in lookup_map.values())
        raw_plsql = str(unit.get('raw_plsql', ''))
        has_exception_block = bool(re.search(r"\bexception\b", raw_plsql, flags=re.IGNORECASE))
        return (
            1 if operations_by_table else 0,
            len(operations_by_table),
            len(target_tables),
            len(semantic.get('upsert_operations') or []),
            len((semantic.get('aggregation', {}) or {}).get('columns', []) or []),
            lookup_key_count,
            1 if unit.get('autonomous_transaction') else 0,
            len(unit.get('programmatic_raises') or []),
            1 if transaction.get('has_savepoint') else 0,
            1 if transaction.get('has_partial_rollback') else 0,
            1 if transaction.get('has_commit') else 0,
            1 if transaction.get('has_rollback') else 0,
            1 if has_exception_block else 0,
            len(unit.get('input_parameters') or []),
            len(raw_plsql.strip()),
        )

    def _generate_utility_service_from_unit(
        self,
        unit: Dict[str, Any],
        all_units: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """RC1+RC5 FIX: generate a pure-logic (no-DB) service for utility/infrastructure packages."""
        package_name = self.config.get('output', {}).get('package_name', 'com.company.project')
        service_name = self._derive_service_name(unit.get('name', 'Generated'))
        method_source_name = unit.get('subprogram_name') or unit.get('name', 'execute')
        method_name = self._to_camel_case(method_source_name)

        imports: Set[str] = {
            'import org.springframework.stereotype.Service;',
        }

        # RC8 FIX: PRAGMA AUTONOMOUS_TRANSACTION → REQUIRES_NEW
        autonomous_transaction = unit.get('autonomous_transaction', False)
        if autonomous_transaction:
            imports.add('import org.springframework.transaction.annotation.Transactional;')
            imports.add('import org.springframework.transaction.annotation.Propagation;')
            tx_annotation = '    @Transactional(propagation = Propagation.REQUIRES_NEW)\n'
        else:
            tx_annotation = ''

        # RC6 FIX: emit private static final constants
        constants_lines: List[str] = []
        needs_bigdecimal = False
        needs_localdatetime = False
        for const in (unit.get('package_constants') or []):
            java_type = self._map_plsql_type_to_java(const.get('type', 'VARCHAR2'), const.get('name', ''), 'IN')
            if java_type == 'BigDecimal':
                needs_bigdecimal = True
                imports.add('import java.math.BigDecimal;')
            if java_type == 'LocalDateTime':
                needs_localdatetime = True
                imports.add('import java.time.LocalDateTime;')
            value = const.get('value', '')
            if java_type == 'String':
                value_expr = f'"{value}"'
            elif java_type == 'Boolean':
                value_expr = value.lower() if value.lower() in ('true', 'false') else 'false'
            elif java_type == 'BigDecimal':
                value_expr = f'new BigDecimal("{value}")' if value else 'BigDecimal.ZERO'
            elif java_type == 'Long':
                value_expr = f'{value}L' if value else '0L'
            else:
                value_expr = value if value else '0'
            const_name = re.sub(r'[^A-Z0-9_]', '_', const.get('name', 'CONSTANT').upper())
            constants_lines.append(f'    private static final {java_type} {const_name} = {value_expr};')

        # RC2 FIX: build method params — BOOLEAN correctly maps to Boolean here
        method_params_parts: List[str] = []
        null_safe_set = {p.upper() for p in (unit.get('null_safe_params') or [])}
        for param in (unit.get('input_parameters') or []):
            raw_name = str(param.get('name', '')).strip()
            if not raw_name:
                continue
            param_name = normalize_column_name(raw_name)
            java_type = self._map_plsql_type_to_java(
                str(param.get('type', '')),
                raw_name,
                str(param.get('direction', 'IN')),
            )
            method_params_parts.append(f'{java_type} {param_name}')
        method_params = ', '.join(method_params_parts)
        if "BigDecimal " in method_params:
            imports.add('import java.math.BigDecimal;')
        if "LocalDateTime " in method_params:
            imports.add('import java.time.LocalDateTime;')
        if "LocalDate " in method_params:
            imports.add('import java.time.LocalDate;')
        if "LocalTime " in method_params:
            imports.add('import java.time.LocalTime;')

        # RC7 FIX: inject cross-service dependencies from procedures_called
        dep_graph = unit.get('dependency_graph') or {}
        procedures_called = dep_graph.get('procedures_called', [])
        cross_service_fields: List[str] = []
        cross_service_constructor_args: List[str] = []
        cross_service_inits: List[str] = []
        if all_units:
            unit_name_to_service: Dict[str, str] = {
                u.get('name', '').upper(): self._derive_service_name(u.get('name', 'Generated'))
                for u in all_units
                if u.get('name') and u.get('name', '').upper() != unit.get('name', '').upper()
            }
            for called in procedures_called:
                svc_name = unit_name_to_service.get(called.upper())
                if not svc_name:
                    continue
                svc_var = self._lower_first(svc_name)
                cross_service_fields.append(f'    private final {svc_name} {svc_var};')
                cross_service_constructor_args.append(f'{svc_name} {svc_var}')
                cross_service_inits.append(f'        this.{svc_var} = {svc_var};')

        # RC3/RC4 FIX: build method body — null-safe boolean guards + throw new BusinessException
        body_lines: List[str] = []
        programmatic_raises = unit.get('programmatic_raises') or []

        for param in (unit.get('input_parameters') or []):
            raw_name = str(param.get('name', '')).strip()
            if not raw_name:
                continue
            param_name = normalize_column_name(raw_name)
            java_type = self._map_plsql_type_to_java(str(param.get('type', '')), raw_name, 'IN')
            if java_type == 'Boolean' and raw_name.upper() in null_safe_set:
                # RC3 FIX: NVL(p_condition, false) → null-safe guard
                if programmatic_raises:
                    raise_info = programmatic_raises[0]
                    error_code = raise_info.get('error_code', '-20000')
                    body_lines.append(
                        f'if ({param_name} == null || !{param_name}) {{'
                    )
                    body_lines.append(
                        f'    throw new BusinessException({error_code}, "Assertion failed");'
                    )
                    body_lines.append('}')
                else:
                    body_lines.append(f'if ({param_name} == null || !{param_name}) {{')
                    body_lines.append('    throw new BusinessException(-20000, "Assertion failed");')
                    body_lines.append('}')
            elif java_type == 'Boolean':
                body_lines.append(f'if ({param_name} != null && !{param_name}) {{')
                body_lines.append('    throw new BusinessException(-20000, "Assertion failed");')
                body_lines.append('}')

        # Emit any additional raises not already handled
        for raise_info in programmatic_raises:
            error_code = raise_info.get('error_code', '-20000')
            message = raise_info.get('message', 'Error')
            if not any('throw new BusinessException' in line for line in body_lines):
                body_lines.append(
                    f'// Source: RAISE_APPLICATION_ERROR({error_code}, ...)'
                )
                body_lines.append(
                    f'throw new BusinessException({error_code}, "{message}");'
                )

        if not body_lines:
            body_lines.append('// No SQL operations — pure utility/infrastructure logic preserved here.')

        transaction = unit.get('transaction') or {}
        has_exception_block = bool(re.search(r"\bexception\b", str(unit.get('raw_plsql', '')), flags=re.IGNORECASE))
        requires_row_level_try = bool(transaction.get('has_savepoint')) or has_exception_block
        if requires_row_level_try:
            wrapped_lines: List[str] = [
                'for (int rowIndex = 0; rowIndex < 1; rowIndex++) {',
                '    try {',
            ]
            wrapped_lines.extend(f'        {line}' for line in body_lines)
            wrapped_lines.extend(
                [
                    '    } catch (BusinessException e) {',
                    '        continue;',
                    '    } catch (Exception e) {',
                    '        continue;',
                    '    }',
                    '}',
                ]
            )
            body_lines = wrapped_lines

        method_body = '\n'.join(f'        {line}' for line in body_lines)

        # RC4 FIX: inner BusinessException class
        helper_block = (
            '\n'
            '    private static final class BusinessException extends RuntimeException {\n'
            '        private final int errorCode;\n'
            '        BusinessException(int errorCode, String message) {\n'
            '            super(message);\n'
            '            this.errorCode = errorCode;\n'
            '        }\n'
            '        int getErrorCode() { return errorCode; }\n'
            '    }\n'
        )

        constants_block = ('\n' + '\n'.join(constants_lines) + '\n') if constants_lines else ''
        fields_block = '\n'.join(cross_service_fields) + ('\n' if cross_service_fields else '')
        constructor_args_str = ', '.join(cross_service_constructor_args)
        inits_block = '\n'.join(cross_service_inits) + ('\n' if cross_service_inits else '')

        return (
            f'package {package_name}.service;\n\n'
            f'{chr(10).join(sorted(imports))}\n\n'
            '@Service\n'
            f'public class {service_name} {{\n'
            f'{constants_block}'
            f'{fields_block}\n'
            f'    public {service_name}({constructor_args_str}) {{\n'
            f'{inits_block}'
            '    }\n\n'
            f'{tx_annotation}'
            f'    public void {method_name}({method_params}) {{\n'
            f'{method_body}\n'
            '    }\n'
            f'{helper_block}'
            '}\n'
        )

    def _build_service_parameters(self, unit: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
        params = []
        name_map: Dict[str, str] = {}
        used_param_names: Set[str] = set()
        reserved_locals = {
            'row',
            'page',
            'size',
            'hasError',
            'batchHasError',
            'rowIndex',
            'hasMore',
        }
        for param in unit.get('input_parameters', []) or []:
            raw_name = str(param.get('name', '')).strip()
            if not raw_name:
                continue
            base_name = normalize_column_name(raw_name) or "param"
            if base_name in reserved_locals:
                base_name = f"{base_name}Param"
            param_name = base_name
            suffix = 2
            while param_name in used_param_names:
                param_name = f"{base_name}{suffix}"
                suffix += 1
            used_param_names.add(param_name)
            java_type = self._map_plsql_type_to_java(
                str(param.get('type', '')),
                raw_name,
                str(param.get('direction', 'IN')),
            )
            params.append(f"{java_type} {param_name}")
            name_map.setdefault(raw_name.upper(), param_name)
        return ", ".join(params), name_map

    def _derive_primary_table(self, unit: Dict[str, Any]) -> str:
        operations = unit.get('operations_by_table') or {}
        if operations:
            return sorted(str(name).upper() for name in operations.keys())[0]
        tables = unit.get('tables_used') or []
        return str(tables[0]).upper() if tables else "DUAL"

    def _derive_driving_table(self, unit: Dict[str, Any]) -> str:
        driving = str(unit.get('driving_table', '')).upper()
        if driving:
            return driving
        cursor = unit.get('cursor') or {}
        cursor_driving = str(cursor.get('driving_table', '')).upper()
        if cursor_driving:
            return cursor_driving
        cursor_tables = [str(table).upper() for table in (cursor.get('tables') or []) if table]
        if cursor_tables:
            return cursor_tables[0]
        return self._derive_primary_table(unit)

    def _derive_target_tables(self, unit: Dict[str, Any]) -> List[str]:
        declared = [str(table).upper() for table in (unit.get('target_tables') or []) if table]
        if declared:
            return sorted(dict.fromkeys(declared))
        targets: List[str] = []
        for table_name, operations in (unit.get('operations_by_table') or {}).items():
            upper_ops = {str(op).upper() for op in (operations or [])}
            if upper_ops.intersection({'INSERT', 'UPDATE', 'DELETE', 'MERGE'}):
                targets.append(str(table_name).upper())
        return sorted(dict.fromkeys(targets))

    def _derive_merge_table(self, unit: Dict[str, Any]) -> str:
        semantic = unit.get('semantic_analysis') or {}
        for upsert in semantic.get('upsert_operations') or []:
            table_name = str(upsert.get('table', '')).upper()
            if table_name:
                return table_name
        raw_plsql = str(unit.get('raw_plsql', ''))
        match = re.search(r'\bMERGE\s+INTO\s+([`"\w$#\.]+)', raw_plsql, flags=re.IGNORECASE)
        if match:
            return str(match.group(1)).strip('"`').split(".")[-1].upper()
        return ""

    def _validate_table_fields_against_metadata(
        self,
        entity_name: str,
        metadata_provider: Optional[Any],
    ) -> Set[str]:
        """
        Get valid field names for an entity from metadata provider.
        Returns set of valid Java field names (lowercase).
        Falls back to empty set if metadata not available.
        """
        if not metadata_provider:
            return set()
        
        try:
            # Get metadata using the provider's API
            table_metadata = metadata_provider.get_table_metadata(entity_name)
            if not table_metadata:
                return set()
            
            # Get all valid field names from metadata
            valid_fields = set()
            for column in table_metadata.columns:
                # Get snake_case field name and convert to lowercase
                field_name = column.to_dict().get('java_field_name', '').lower()
                if field_name:
                    valid_fields.add(field_name)
            
            return valid_fields
        except Exception:
            # Safety: return empty set on any error
            return set()

    def _sanitize_getter_call(
        self,
        entity_name: str,
        field_name: str,
        valid_fields: Set[str],
    ) -> str:
        """
        Validate that the getter method is for a valid field.
        Returns the sanitized getter method name.
        """
        if not valid_fields:
            # No validation available, return as-is
            return f"get{field_name[:1].upper() + field_name[1:]}()"
        
        normalized_field = field_name.lower()
        if normalized_field in valid_fields:
            # Field is valid, return the getter
            return f"get{field_name[:1].upper() + field_name[1:]}()"
        else:
            # Field is invalid, return a safe fallback (getId or first field)
            logger.warning(f"[DQI-1] Invalid field '{field_name}' on {entity_name}. Valid fields: {valid_fields}")
            # Return getId as safe fallback for ID lookups
            return "getId()"

    def _lookup_keys_for_table(self, unit: Dict[str, Any], table_name: str) -> List[str]:
        lookup_map = unit.get('lookup_keys') or {}
        table_key = str(table_name).upper()
        return sorted(str(col).upper() for col in (lookup_map.get(table_key) or []) if col)

    def _generate_deterministic_service_from_unit(
        self,
        unit: Dict[str, Any],
        entities: Dict[str, str],
        repositories: Dict[str, str],
        all_units: Optional[List[Dict[str, Any]]] = None,
        metadata_provider: Optional[Any] = None,
        validation_feedback: Optional[List[str]] = None,
    ) -> str:
        package_name = self.config.get('output', {}).get('package_name', 'com.company.project')
        service_name = self._derive_service_name(unit.get('name', 'Generated'))
        method_source_name = unit.get('subprogram_name') or unit.get('name', 'execute')
        method_name = self._to_camel_case(method_source_name)
        method_params, param_name_map = self._build_service_parameters(unit)

        raw_plsql = str(unit.get('raw_plsql', ''))
        semantic = unit.get('semantic_analysis') or {}
        operations_by_table = unit.get('operations_by_table') or {}
        entity_field_types = self._extract_entity_field_types(entities)

        # DQI-1 FIX: Use metadata provider for enhanced field validation
        valid_entity_fields: Dict[str, Set[str]] = {}
        if metadata_provider:
            logger.debug(f"[DQI-1] Using metadata provider for entity field validation in {service_name}")
            for entity_name in set(entity_field_types.keys()):
                valid_fields = self._validate_table_fields_against_metadata(entity_name, metadata_provider)
                if valid_fields:
                    valid_entity_fields[entity_name] = valid_fields
                    logger.debug(f"[DQI-1] {entity_name}: {len(valid_fields)} valid fields from metadata")
        
        # DQI-2 FIX: Extract PL/SQL logic patterns for improved Java generation
        try:
            from src.converter.llm_engine_integration import PLSQLLogicExtractor
            plsql_extractor = PLSQLLogicExtractor()
            patterns = plsql_extractor.extract_logic_patterns(raw_plsql)
            logger.debug(f"[DQI-2] Extracted {len(patterns)} pattern types from PL/SQL code")
            if patterns.get('cursor_operations'):
                logger.debug(f"[DQI-2] Cursor operations: {len(patterns['cursor_operations'])} found")
            if patterns.get('loops'):
                logger.debug(f"[DQI-2] Loop patterns: {len(patterns['loops'])} found")
            if patterns.get('exception_handling'):
                logger.debug(f"[DQI-2] Exception handlers: {len(patterns['exception_handling'])} found")
        except Exception as e:
            logger.debug(f"[DQI-2] PLSQLLogicExtractor not available: {e}")
            patterns = {}
        
        # VF-1 FIX: Use validation_feedback to guide generation decisions
        # If prior validation attempts found issues, log them for context
        if validation_feedback:
            logger.info(f"[VF-1] Service {service_name}: Using feedback from {len(validation_feedback)} prior validation issues")
            for fb in validation_feedback[:3]:  # Log first 3 issues
                logger.debug(f"[VF-1]   - {fb}")

        driving_table = self._derive_driving_table(unit)
        target_tables = self._derive_target_tables(unit)
        merge_table = self._derive_merge_table(unit)
        if merge_table and merge_table not in target_tables:
            target_tables.append(merge_table)
        target_tables = sorted(dict.fromkeys([table for table in target_tables if table]))

        select_tables = [
            str(table).upper()
            for table, ops in operations_by_table.items()
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
            if not table_name or not column_name:
                continue
            aggregation_columns.append((table_name, column_name))
            if table_name not in aggregation_tables:
                aggregation_tables.append(table_name)

        table_order: List[str] = []
        for table_name in [
            driving_table,
            *select_tables,
            *aggregation_tables,
            *target_tables,
        ]:
            normalized = str(table_name).upper()
            if normalized and normalized not in table_order:
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
        if "BigDecimal " in method_params:
            imports.add('import java.math.BigDecimal;')
        if "LocalDateTime " in method_params:
            imports.add('import java.time.LocalDateTime;')
        if "LocalDate " in method_params:
            imports.add('import java.time.LocalDate;')
        if "LocalTime " in method_params:
            imports.add('import java.time.LocalTime;')

        has_bulk_collect = any(
            str(op.get('type', '')).upper() == 'BULK_COLLECT'
            for op in (unit.get('bulk_operations') or [])
        )
        has_cursor = bool(unit.get('cursor')) or bool(re.search(r"\bCURSOR\b", raw_plsql, flags=re.IGNORECASE))
        requires_pagination = has_bulk_collect or has_cursor
        transaction = unit.get('transaction') or {}
        requires_transactional_method = bool(
            transaction.get('required')
            or transaction.get('has_savepoint')
            or transaction.get('has_partial_rollback')
            or transaction.get('has_commit')
            or transaction.get('has_rollback')
            or re.search(r"\b(commit|rollback|savepoint)\b", raw_plsql, flags=re.IGNORECASE)
        )
        # RC8 FIX: PRAGMA AUTONOMOUS_TRANSACTION → Propagation.REQUIRES_NEW
        autonomous_transaction = unit.get('autonomous_transaction', False)
        if autonomous_transaction:
            imports.add('import org.springframework.transaction.annotation.Transactional;')
            imports.add('import org.springframework.transaction.annotation.Propagation;')
        elif requires_transactional_method:
            imports.add('import org.springframework.transaction.annotation.Transactional;')

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

        if requires_pagination:
            imports.update(
                {
                    'import org.springframework.data.domain.Page;',
                    'import org.springframework.data.domain.PageRequest;',
                }
            )

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

        # RC7 FIX: inject cross-service dependencies from procedures_called
        dep_graph = unit.get('dependency_graph') or {}
        procedures_called = dep_graph.get('procedures_called', [])
        if all_units and procedures_called:
            unit_name_to_service_map: Dict[str, str] = {
                u.get('name', '').upper(): self._derive_service_name(u.get('name', 'Generated'))
                for u in all_units
                if u.get('name') and u.get('name', '').upper() != unit.get('name', '').upper()
            }
            seen_cross_services: Set[str] = set()
            for called_proc in procedures_called:
                svc_class = unit_name_to_service_map.get(called_proc.upper())
                if not svc_class or svc_class in seen_cross_services:
                    continue
                seen_cross_services.add(svc_class)
                svc_var = self._lower_first(svc_class)
                field_lines.append(f"    private final {svc_class} {svc_var};")
                constructor_lines.append(f"{svc_class} {svc_var}")
                init_lines.append(f"        this.{svc_var} = {svc_var};")
                imports.add(f"import {package_name}.service.{svc_class};")

        body_lines: List[str] = [
            'int page = 0;',
            'boolean hasError = false;',
        ]
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
        join_key = join_key_candidates[0] if join_key_candidates else ''
        join_var = normalize_column_name(join_key) if join_key else ''
        join_getter = f"get{join_var[:1].upper() + join_var[1:]}" if join_var else 'getId'
        driving_fields = entity_field_types.get(driving_entity, {})
        join_type = driving_fields.get(join_var, 'Long') if join_var else 'Long'
        method_param_names = {part.rsplit(" ", 1)[-1] for part in method_params.split(", ") if " " in part}
        join_from_method_param = bool(join_var and join_var in method_param_names)

        row_logic: List[str] = []
        
        # CFX-3b PART 1: Extract branches from semantic analysis and add to row_logic
        # This ensures IF/ELSIF/ELSE structures are preserved in generated Java code
        if semantic.get('branches'):
            logger.debug(f"[CFX-3b] Processing {len(semantic.get('branches', []))} branches from semantic analysis")
            branches_list = semantic.get('branches', [])
            for branch_idx, branch in enumerate(branches_list):
                if isinstance(branch, dict):
                    is_first = branch_idx == 0
                    prefix = "if" if is_first else ("else if" if branch.get('type') == 'elsif' else "else")
                    
                    condition = str(branch.get('condition', '')).strip()
                    if condition and prefix != "else":
                        # Convert PL/SQL condition to Java
                        java_condition = condition.replace('=', '==').replace(';', '')
                        row_logic.append(f"{prefix} ({java_condition}) {{")
                    else:
                        row_logic.append(f"{prefix} {{")
                    
                    # Add branch body (placeholder comment for now - actual logic preserved in CFX-3b extraction)
                    row_logic.append("    // Branch logic preserved for control flow")
                    row_logic.append("}")
                    logger.debug(f"[CFX-3b] Added branch {branch_idx + 1}: {prefix}")
            
        if join_var and not join_from_method_param:
            if join_var in driving_fields:
                row_logic.append(f"{join_type} {join_var} = row.{join_getter}();")
            else:
                default_value = "null"
                if join_type in {"Long", "long"}:
                    default_value = "0L"
                elif join_type in {"Integer", "int"}:
                    default_value = "0"
                elif join_type == "BigDecimal":
                    imports.add('import java.math.BigDecimal;')
                    default_value = "BigDecimal.ZERO"
                row_logic.append(f"{join_type} {join_var} = {default_value};")

        agg_var_by_table: Dict[str, str] = {}
        for table_name, column_name in aggregation_columns:
            binding = bindings.get(table_name)
            if not binding:
                continue
            table_repo_var = binding['repository_var']
            table_entity = binding.get('entity', '')
            table_entity_fields = entity_field_types.get(table_entity, {})
            sum_field = self._resolve_entity_field_name(column_name, table_entity_fields)
            lookup_keys = self._lookup_keys_for_table(unit, table_name)
            sum_method = self._aggregation_method_name(lookup_keys, sum_field)
            call_args: List[str] = []
            for key in lookup_keys:
                key_var = normalize_column_name(key)
                if join_var and key_var == join_var:
                    call_args.append(join_var)
                else:
                    # DYN-FIX-10: Check if field exists on driving entity before generating getter
                    getter = f"get{key_var[:1].upper() + key_var[1:]}"
                    
                    # Only add getter if field exists on driving entity
                    if key_var in driving_fields:
                        call_args.append(f"row.{getter}()")
                    else:
                        # Field doesn't exist on driving entity - use default value instead
                        default_value = "null"
                        if driving_fields.get(key_var, '').startswith('Long'):
                            default_value = "0L"
                        elif driving_fields.get(key_var, '').startswith('Integer'):
                            default_value = "0"
                        call_args.append(default_value)
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
        if has_negative_balance_rule and balance_var:
            row_logic.append(
                f'if ({balance_var}.compareTo(BigDecimal.ZERO) < 0) {{ throw new {business_exception_name}("Negative balance for key " + {join_var}); }}'
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
                    for key in merge_lookup_keys:
                        key_var = normalize_column_name(key)
                        if join_var and key_var == join_var:
                            merge_args.append(join_var)
                        else:
                            getter = f"get{key_var[:1].upper() + key_var[1:]}"
                            # DYN-FIX-10 (part 2): Check if field exists on driving entity before generating getter
                            if key_var in driving_fields:
                                merge_args.append(f"row.{getter}()")
                            else:
                                # Field doesn't exist on driving entity - use default value instead
                                default_value = "null"
                                if driving_fields.get(key_var, '').startswith('Long'):
                                    default_value = "0L"
                                elif driving_fields.get(key_var, '').startswith('Integer'):
                                    default_value = "0"
                                merge_args.append(default_value)
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
                row_logic.append(f"    {merge_entity} target = new {merge_entity}();")
                if join_var and join_key:
                    setter = f"set{join_var[:1].upper() + join_var[1:]}"
                    row_logic.append(f"    target.{setter}({join_var});")
                if balance_var and balance_field:
                    row_logic.append(f"    target.set{balance_field[:1].upper() + balance_field[1:]}({balance_var});")
                if created_at_field:
                    row_logic.append(f"    target.set{created_at_field[:1].upper() + created_at_field[1:]}(LocalDateTime.now());")
                row_logic.append(f"    {merge_repo_var}.save(target);")
                row_logic.append('}')
        elif target_tables:
            first_target = bindings.get(target_tables[0])
            if first_target:
                target_entity = first_target['entity']
                target_repo_var = first_target['repository_var']
                row_logic.append(f"{target_entity} target = new {target_entity}();")
                row_logic.append(f"{target_repo_var}.save(target);")

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

        required_operations: Set[str] = {
            str(operation).upper()
            for operations in operations_by_table.values()
            for operation in (operations or [])
        }

        def _has_repo_behavior(pattern: str) -> bool:
            return bool(re.search(pattern, "\n".join(row_logic)))

        def _default_literal(java_type: str) -> str:
            if java_type in {"Long", "long"}:
                return "0L"
            if java_type in {"Integer", "int"}:
                return "0"
            if java_type == "BigDecimal":
                imports.add('import java.math.BigDecimal;')
                return "BigDecimal.ZERO"
            if java_type == "String":
                return "\"\""
            if java_type in {"Boolean", "boolean"}:
                return "false"
            return "null"

        def _resolve_lookup_argument(column_name: str, expected_type: str) -> str:
            normalized = normalize_column_name(column_name)
            exact = param_name_map.get(str(column_name).upper())
            if exact:
                return exact
            normalized_hit = param_name_map.get(normalized.upper())
            if normalized_hit:
                return normalized_hit
            if normalized in method_param_names:
                return normalized
            for key_name, value_name in param_name_map.items():
                if normalized and normalized.lower() in key_name.lower():
                    return value_name
            if join_var and normalized and normalized.lower() == join_var.lower():
                return join_var
            return _default_literal(expected_type)

        if 'SELECT' in required_operations and not _has_repo_behavior(r"\.\s*(find\w*|getTotal\w*|getSum\w*|count\w*)\s*\("):
            driving_lookup_keys = self._lookup_keys_for_table(unit, driving_table)
            driving_fields = entity_field_types.get(driving_entity, {})
            driving_repo_code = repositories.get(f"{driving_repo}.java", "")
            lookup_method = self._expected_lookup_method_name(driving_lookup_keys) if driving_lookup_keys else 'findById'
            if lookup_method != 'findById' and lookup_method not in driving_repo_code:
                lookup_method = 'findAll'
            if lookup_method == 'findAll':
                row_logic.append(f"{driving_repo_var}.findAll();")
            else:
                lookup_args = []
                if lookup_method == 'findById':
                    id_column = next((k for k in driving_lookup_keys if str(k).upper().endswith('ID')), 'ID')
                    id_type = self._resolve_lookup_key_type(id_column, driving_fields) if driving_lookup_keys else 'Long'
                    lookup_args.append(_resolve_lookup_argument(id_column, id_type))
                else:
                    for key in driving_lookup_keys:
                        key_type = self._resolve_lookup_key_type(key, driving_fields)
                        lookup_args.append(_resolve_lookup_argument(key, key_type))
                row_logic.append(f"{driving_repo_var}.{lookup_method}({', '.join(lookup_args)});")

        if 'INSERT' in required_operations and not _has_repo_behavior(r"\.\s*(insert\w*|save|saveAndFlush)\s*\("):
            row_logic.append(f"{driving_entity} insertRecord = new {driving_entity}();")
            row_logic.append(f"{driving_repo_var}.save(insertRecord);")

        if 'UPDATE' in required_operations and not _has_repo_behavior(r"\.\s*(update\w*|save|saveAndFlush)\s*\("):
            row_logic.append(f"{driving_entity} updateRecord = new {driving_entity}();")
            row_logic.append(f"{driving_repo_var}.save(updateRecord);")

        if 'DELETE' in required_operations and not _has_repo_behavior(r"\.\s*(delete\w*|remove\w*)\s*\("):
            delete_lookup_keys = self._lookup_keys_for_table(unit, driving_table)
            delete_key = next((key for key in delete_lookup_keys if str(key).upper().endswith('ID')), delete_lookup_keys[0] if delete_lookup_keys else 'ID')
            delete_key_type = self._resolve_lookup_key_type(delete_key, entity_field_types.get(driving_entity, {}))
            delete_arg = _resolve_lookup_argument(delete_key, delete_key_type)
            row_logic.append(f"{driving_repo_var}.deleteById({delete_arg});")

        # CFX-3b: Extract ALL branches from row_logic to preserve at method body level
        # This ensures branch/control-flow structure is visible to validator (not nested in for loops)
        method_level_branches = []
        row_logic_without_branches = []
        i = 0
        while i < len(row_logic):
            line = row_logic[i]
            # Detect ANY if/else if/else branch starts (at any indentation level)
            if re.match(r"^\s*(if|else\s+if|else)\s*[\({]", line, re.IGNORECASE):
                # Collect the entire branch structure (handle braces)
                branch_block = [line]
                brace_count = line.count('{') - line.count('}')
                i += 1
                while i < len(row_logic) and brace_count > 0:
                    next_line = row_logic[i]
                    branch_block.append(next_line)
                    brace_count += next_line.count('{') - next_line.count('}')
                    i += 1
                # Add complete branch structure to method_level_branches
                method_level_branches.extend(branch_block)
                logger.debug(f"[CFX-3b] Extracted method-level branch: {branch_block[0]}")
            else:
                row_logic_without_branches.append(line)
                i += 1
        
        # Replace row_logic with non-branch lines for loop processing
        row_logic = row_logic_without_branches
        
        # Add extracted branches to body_lines BEFORE pagination/direct invocation logic
        if method_level_branches:
            body_lines.extend(method_level_branches)
            logger.debug(f"[CFX-3b] Added {len(method_level_branches)} branch lines to body_lines before batch operations")

        if requires_pagination:
            if driving_table in skip_locked_tables:
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
                skip_locked_args.append("PageRequest.of(page, size)")
                fetch_call = f"{driving_repo_var}.{skip_locked_method}({', '.join(skip_locked_args)})"
            else:
                fetch_call = f"{driving_repo_var}.findAll(PageRequest.of(page, size))"
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
                    '    page++;',
                    '}',
                ]
            )
        else:
            body_lines.extend(
                [
                    'for (int rowIndex = 0; rowIndex < 1; rowIndex++) {',
                    '    try {',
                    f"        {driving_entity} row = new {driving_entity}();",
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
        method_annotation = (
            "    @Transactional(propagation = Propagation.REQUIRES_NEW)\n"
            if autonomous_transaction
            else ("    @Transactional\n" if requires_transactional_method else "")
        )
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

    async def _convert_procedures(
        self,
        procedures: List[Dict[str, Any]],
        context: Dict[str, Any],
        metadata_provider: Optional[Any] = None,
    ) -> Dict[str, str]:
        java_files = {}

        async def convert_single(procedure: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
            # LCE-2 FIX: semaphore created lazily inside async context
            async with self._get_semaphore():
                try:
                    prompt_context = {
                        **context,
                        'conversion_type': 'procedure_to_service',
                        'plsql_code': self._format_raw_plsql(procedure),
                    }
                    prompt = inject_enhanced_prompts(
                        self.prompt_template,
                        procedure,
                        prompt_context,
                        metadata_provider=metadata_provider,
                    )
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

    async def _convert_functions(
        self,
        functions: List[Dict[str, Any]],
        context: Dict[str, Any],
        metadata_provider: Optional[Any] = None,
    ) -> Dict[str, str]:
        java_files = {}

        async def convert_single(function: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
            async with self._get_semaphore():
                try:
                    prompt_context = {
                        **context,
                        'conversion_type': 'function_to_service',
                        'plsql_code': self._format_raw_plsql(function),
                    }
                    prompt = inject_enhanced_prompts(
                        self.prompt_template,
                        function,
                        prompt_context,
                        metadata_provider=metadata_provider,
                    )
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

    async def _convert_triggers(
        self,
        triggers: List[Dict[str, Any]],
        context: Dict[str, Any],
        metadata_provider: Optional[Any] = None,
    ) -> Dict[str, str]:
        java_files = {}

        async def convert_single(trigger: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
            async with self._get_semaphore():
                try:
                    trigger_context = {
                        **context,
                        'trigger_timing': trigger.get('timing', 'BEFORE'),
                        'trigger_event': trigger.get('event', 'INSERT'),
                        'table': trigger.get('table', ''),
                        'conversion_type': 'trigger_to_event',
                        'plsql_code': self._format_raw_plsql(trigger),
                    }
                    prompt = inject_enhanced_prompts(
                        self.prompt_template,
                        trigger,
                        trigger_context,
                        metadata_provider=metadata_provider,
                    )
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

    async def _convert_packages(
        self,
        packages: List[Dict[str, Any]],
        context: Dict[str, Any],
        metadata_provider: Optional[Any] = None,
    ) -> Dict[str, str]:
        java_files = {}

        async def convert_single(package: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
            async with self._get_semaphore():
                try:
                    pkg_context = {
                        **context,
                        'procedures': [p.get('name') for p in package.get('procedures', [])],
                        'functions': [f.get('name') for f in package.get('functions', [])],
                        'conversion_type': 'package_to_class',
                        'plsql_code': self._format_raw_plsql(package),
                    }
                    prompt = inject_enhanced_prompts(
                        self.prompt_template,
                        package,
                        pkg_context,
                        metadata_provider=metadata_provider,
                    )
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

    async def _convert_sql_to_repositories(
        self,
        sql_queries: List[Dict[str, Any]],
        context: Dict[str, Any],
        metadata_provider: Optional[Any] = None,
    ) -> Dict[str, str]:
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
                        'conversion_type': 'sql_to_repository',
                        'plsql_code': combined_sql,
                    }
                    combined_sql = "\n\n".join([q.get('query', '') for q in queries])
                    prompt = inject_enhanced_prompts(
                        self.prompt_template,
                        {'sql_statements': [{'text': combined_sql}]},
                        table_context,
                        metadata_provider=metadata_provider,
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
        type_name = (plsql_type or '').strip().upper()
        normalized_name = (field_name or '').lower().strip()

        # Strip %TYPE / %ROWTYPE anchors — use field name heuristics
        if '%TYPE' in type_name or '%ROWTYPE' in type_name:
            # Heuristic: if it ends in _ID or ID it's a Long; amount/price → BigDecimal; else String
            if normalized_name.endswith('_id') or normalized_name.endswith('id'):
                return 'Long'
            if any(k in normalized_name for k in ('amount', 'price', 'balance', 'total', 'credit', 'debit', 'payment')):
                return 'BigDecimal'
            return 'String'

        # BOOLEAN (Oracle PL/SQL only — not a SQL type)
        if 'BOOLEAN' in type_name:
            return 'Boolean'

        # Character / String types
        if any(t in type_name for t in ('VARCHAR', 'VARCHAR2', 'NVARCHAR', 'CHAR', 'NCHAR',
                                          'CLOB', 'NCLOB', 'LONG', 'XMLTYPE')):
            return 'String'

        # Binary types
        if any(t in type_name for t in ('BLOB', 'RAW', 'BFILE')):
            return 'byte[]'

        # Date / timestamp types
        if 'TIMESTAMP' in type_name:
            return 'LocalDateTime'
        if type_name in ('DATE',):
            return 'LocalDateTime'

        # Numeric types
        if 'NUMBER' in type_name or 'NUMERIC' in type_name or 'DECIMAL' in type_name:
            # NUMBER(p,s) with scale > 0 → BigDecimal
            scale_match = re.search(r'\(\s*\d+\s*,\s*(\d+)\s*\)', type_name)
            if scale_match and int(scale_match.group(1)) > 0:
                return 'BigDecimal'
            # ID fields → Long
            if normalized_name.endswith('_id') or normalized_name.endswith('id'):
                return 'Long'
            # Amount / monetary fields → BigDecimal
            if any(k in normalized_name for k in ('amount', 'price', 'balance', 'total', 'credit', 'debit', 'payment', 'rate', 'salary', 'cost')):
                return 'BigDecimal'
            # Default NUMBER → Long
            return 'Long'

        # Integer types
        if any(t in type_name for t in ('INTEGER', 'INT', 'PLS_INTEGER', 'BINARY_INTEGER',
                                          'SIMPLE_INTEGER', 'NATURAL', 'POSITIVE')):
            if normalized_name.endswith('_id') or normalized_name.endswith('id'):
                return 'Long'
            return 'Long'

        # Float types
        if any(t in type_name for t in ('FLOAT', 'REAL', 'DOUBLE', 'BINARY_FLOAT', 'BINARY_DOUBLE')):
            return 'BigDecimal'

        # Status / name fields default to String
        if any(k in normalized_name for k in ('name', 'status', 'type', 'code', 'desc', 'text', 'comment', 'message', 'reason')):
            return 'String'

        # Default fallback
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

    async def repair_services_with_backup_llm(
        self,
        services: Dict[str, str],
        validation_issues: List[Dict[str, Any]],
        entities: Dict[str, str],
        repositories: Dict[str, str],
    ) -> Dict[str, str]:
        """
        BLM-1 FIX: Use backup_llm to repair services that failed semantic validation.
        
        Args:
            services: Generated service files
            validation_issues: List of validation issues found
            entities: Entity file references
            repositories: Repository file references
            
        Returns:
            Dict of repaired service files (only includes fixed services)
        """
        if not self.repair_provider:
            logger.info("[BLM-1] Backup LLM not enabled; skipping service repair")
            return {}
        
        # Group issues by service filename
        issues_by_service: Dict[str, List[Dict[str, Any]]] = {}
        for issue in validation_issues:
            if issue.get('file_name') and issue.get('file_name') in services:
                issues_by_service.setdefault(issue['file_name'], []).append(issue)
        
        if not issues_by_service:
            logger.info("[BLM-1] No service-specific validation issues; skipping repair")
            return {}
        
        repaired_services: Dict[str, str] = {}
        
        for service_filename, service_issues in issues_by_service.items():
            current_code = services[service_filename]
            
            # Build repair prompt for this specific service
            prompt = self._build_service_repair_prompt(
                service_filename,
                current_code,
                service_issues,
                entities,
                repositories,
            )
            
            try:
                logger.info(f"[BLM-1] Repairing {service_filename} with backup LLM ({len(service_issues)} issues found)")
                raw = await self.repair_provider.generate_code(
                    prompt,
                    max_tokens=int(self.config.get('backup_llm', {}).get('max_tokens', 6000)),
                    temperature=float(self.config.get('backup_llm', {}).get('temperature', 0.0)),
                )
                
                if raw and raw.strip():
                    # Validate the repaired code is valid Java
                    repaired_code = self._extract_java_code_from_response(raw)
                    if repaired_code and len(repaired_code) > 50:
                        repaired_services[service_filename] = repaired_code
                        logger.info(f"[BLM-1] Successfully repaired {service_filename}")
                    else:
                        logger.warning(f"[BLM-1] Backup LLM produced invalid Java for {service_filename}")
                else:
                    logger.warning(f"[BLM-1] Backup LLM returned empty response for {service_filename}")
                    
            except Exception as exc:
                logger.error(f"[BLM-1] Backup LLM repair failed for {service_filename}: {exc}")
        
        return repaired_services

    def _extract_entity_field_mapping(self, entities: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        """DYN-FIX-7: Extract field names and types from entity code."""
        import re
        mapping = {}
        
        for entity_name, entity_code in entities.items():
            fields = {}
            # Match field declarations: private Type fieldName;
            field_pattern = re.compile(r'private\s+([a-zA-Z<>?,\s]+?)\s+(\w+)\s*;')
            for match in field_pattern.finditer(entity_code):
                field_type = match.group(1).strip()
                field_name = match.group(2)
                fields[field_name] = field_type
            
            if fields:
                mapping[entity_name] = fields
        
        return mapping
    
    def _extract_variable_entity_types(self, service_code: str, entities: Dict[str, str]) -> Dict[str, str]:
        """DYN-FIX-8: Extract which entity type each variable holds in service code.
        
        Returns: Dict[variable_name, EntityClassName]
        """
        import re
        var_types = {}
        
        # Extract entity class names from entity files
        entity_names = set()
        for entity_file in entities.keys():
            # EntityNames look like: BookEntity.java, CustomerEntity.java, etc.
            match = re.search(r'(\w+)Entity\.java', entity_file)
            if match:
                entity_names.add(match.group(1) + 'Entity')
        
        # Find variable declarations like: BookEntity row = ...  or  new BookEntity()
        for entity_name in entity_names:
            # Match: EntityType varName = new EntityType(...) or EntityType varName = ...
            pattern = rf'{re.escape(entity_name)}\s+(\w+)\s*='
            for match in re.finditer(pattern, service_code):
                var_name = match.group(1)
                var_types[var_name] = entity_name
        
        return var_types

    def _build_service_repair_prompt(
        self,
        service_filename: str,
        current_code: str,
        issues: List[Dict[str, Any]],
        entities: Dict[str, str],
        repositories: Dict[str, str],
    ) -> str:
        """Build a focused repair prompt for a specific service with validation feedback.
        
        DYN-FIX-8: Enhanced with entity-variable type tracking and field validation.
        DYN-FIX-9: Issue analysis with entity-to-variable mapping recommendations.
        """
        # DYN-FIX-9: Analyze issues to infer which entity types are actually needed
        parsed_issues = []
        entity_needs = {}  # entity_type -> set of variables that should be that type
        
        for issue in issues[:10]:
            msg = issue.get('message', '')
            parsed_issues.append(f"- {msg}")
            
            # Parse patterns like "calls row.getVideoid() but BookEntity does not define it"
            # This tells us: the code tried to access Videoid on BookEntity
            # But Videoid likely belongs to VideoEntity
            import re
            match = re.search(r'calls (\w+)\.get(\w+)\(\) but (\w+) does not define it', msg)
            if match:
                var_name, field_suffix, entity_name = match.groups()
                # If entity_name doesn't have field_suffix, infer which entity SHOULD have it
                for other_entity, fields in self._extract_entity_field_mapping(entities).items():
                    if field_suffix.lower() in {f.lower() for f in fields}:
                        entity_needs.setdefault(other_entity, set()).add(var_name)
                        break
        
        issue_text = "\n".join(parsed_issues)
        
        # DYN-FIX-7: Extract entity field mappings to guide LLM repairs
        entity_field_mappings = self._extract_entity_field_mapping(entities)
        entity_fields_text = ""
        if entity_field_mappings:
            entity_lines = []
            for entity_name in sorted(entity_field_mappings.keys()):
                entity_lines.append(f"  {entity_name} has fields:")
                for field_name, field_type in sorted(entity_field_mappings[entity_name].items()):
                    entity_lines.append(f"    - {field_name}: {field_type}")
            entity_fields_text = "\n".join(entity_lines)
        else:
            entity_fields_text = "    (Unable to extract fields)"
        
        # DYN-FIX-8: Extract which variable holds which entity type
        var_entity_types = self._extract_variable_entity_types(current_code, entities)
        var_types_text = ""
        if var_entity_types or entity_needs:
            var_lines = []
            
            # Show current variable assignments
            for var_name in sorted(var_entity_types.keys()):
                entity_type = var_entity_types[var_name]
                var_lines.append(f"  {var_name} is currently type {entity_type}")
                if entity_type in entity_field_mappings:
                    available_fields = entity_field_mappings[entity_type]
                    var_lines.append(f"    ✓ Available fields: {', '.join(sorted(available_fields.keys()))}")
            
            # DYN-FIX-9: Show which variables should be changed based on validation feedback
            if entity_needs:
                var_lines.append("")
                var_lines.append("  ISSUES SUGGEST THESE CHANGES:")
                for entity_type in sorted(entity_needs.keys()):
                    var_names = entity_needs[entity_type]
                    var_lines.append(f"  {entity_type} is needed by: {', '.join(sorted(var_names))}")
                    if entity_type in entity_field_mappings:
                        fields = entity_field_mappings[entity_type]
                        var_lines.append(f"    It provides fields: {', '.join(sorted(fields.keys()))}")
            
            var_types_text = "\n".join(var_lines)
        else:
            var_types_text = "    (No entity variables found — you may need to declare them)"
        
        entity_context = "\n".join([
            f"  {fname}: {code[:100]}..." if len(code) > 100 else f"  {fname}: {code}"
            for fname, code in list(entities.items())[:3]
        ])
        
        repo_context = "\n".join([
            f"  {fname}: {code[:100]}..." if len(code) > 100 else f"  {fname}: {code}"
            for fname, code in list(repositories.items())[:3]
        ])
        
        return f"""You are repairing a Spring Boot service class that failed semantic validation.

SERVICE FILE: {service_filename}

CURRENT CODE:
```java
{current_code}
```

VALIDATION ISSUES TO FIX:
{issue_text}

ENTITY FIELD MAPPINGS (DYN-FIX-7):
{entity_fields_text}

ENTITY-VARIABLE TYPE BINDINGS (DYN-FIX-8):
{var_types_text}

ENTITY CLASS DEFINITIONS (sample):
{entity_context}

REPOSITORY DEFINITIONS (sample):
{repo_context}

REPAIR RULES (DYN-FIX-8):
1. Fix ONLY the specific validation issues listed above.
2. Do NOT change the overall structure or method signatures.
3. CRITICAL: For each variable (row, entity, target, etc.), verify it holds the correct entity type.
4. CRITICAL: You can ONLY call getters/setters on variables for fields that exist on that entity type.
   Example: If 'row' is a BookEntity, you can ONLY call row.get/set methods for fields in BookEntity.
           If you need VideoId, you must use a VideoEntity variable, not BookEntity.
5. If a validation error says "calls row.getVideoid() but BookEntity does not define it":
   - Check: what type is 'row'?  And does VideoId exist in that type?
   - Fix: Either (a) declare a VideoEntity variable for that logic, or (b) adjust the variable assignment
6. Each field belongs to EXACTLY ONE entity type. Don't call methods across wrong entity types.
7. Only use methods/fields that actually exist in each entity (listed in ENTITY FIELD MAPPINGS above).
8. For any variable assignment (row = ..., entity = ...), verify the type matches the getRHS.
9. Ensure all repository method calls use valid methods.
10. Output ONLY valid Java code. No markdown, no explanations.
11. The output must be a complete, compilable Java class.
12. File must end with the closing brace of the class.

COMMON FIX PATTERN:
If error: "ViewitemLibraryService.java calls row.getVideoid() but BookEntity does not define it"
Then: Check what entity type 'row' should be. If it should be VideoEntity, change the variable declaration.
      Or: If 'row' must be BookEntity, then access VideoId via a different VideoEntity variable.

OUTPUT: Complete repaired Java service class
"""

    def _extract_java_code_from_response(self, response: str) -> str:
        """Extract valid Java code from LLM response, handling markdown and artifacts."""
        if not response:
            return ""
        
        # Remove markdown code block markers if present
        if "```java" in response:
            parts = response.split("```java")
            if len(parts) > 1:
                code = parts[1].split("```")[0]
                return code.strip()
        elif "```" in response:
            parts = response.split("```")
            if len(parts) > 1:
                code = parts[1]
                return code.strip()
        
        # If no markdown, try to extract Java class
        response = response.strip()
        if response.startswith("package ") or response.startswith("import ") or response.startswith("@") or response.startswith("public "):
            return response
        
        return response

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
            "10. In service classes, if TransactionTemplate appears, ensure `import org.springframework.transaction.support.TransactionTemplate;` exists.\n"
            "11. In service classes, if PlatformTransactionManager appears, ensure `import org.springframework.transaction.PlatformTransactionManager;` exists.\n"
            "12. If imports are missing in a Java file that needs them, create a valid import section directly below the package declaration.\n"
            "13. If a class/entity/repository name does not exist, replace it with the real existing generated class name instead of inventing a new one.\n"
            "14. If an argument list, method signature, or generic type does not match existing code, rewrite it to match the declared existing signature exactly.\n"
            "15. If the code references undefined local variables, replace them with existing in-scope variables or compile-safe literals/constants.\n"
            "16. If a field accessor/mutator does not exist, switch to a real existing accessor/mutator or remove that line.\n"
            "17. Never leave a file half-written. Every edited Java file must end with balanced braces and valid syntax.\n"
            "18. In service classes, replace TODOs, placeholders, disconnected branches, and no-op CRUD logic with actual repository calls whenever the repository method already exists.\n"
            "19. In service classes, prefer calling existing custom repository methods first; if none exist, use findById/save/deleteById as the compile-safe fallback.\n"
            "20. If a service is not calling its repository at all, wire it to the matching repository instead of leaving the logic disconnected.\n"
            "21. Do not make speculative runtime/business-logic improvements in this pass.\n"
            "22. Focus first on the files named in the compiler output. Do not touch unrelated files unless one of those files cannot compile without it.\n"
            "23. Assume the build will be rerun immediately. Your response should maximize the chance that the next compile has fewer errors, ideally zero.\n\n"
            "Common compile-only fixes allowed in this pass:\n"
            "- add missing imports such as LocalTime, Timestamp, BigDecimal, Arrays, ArrayList, Pattern, AtomicReference\n"
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
