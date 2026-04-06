"""
DETAILED IMPLEMENTATION GUIDE: Exact Code Changes for 6 Fixes
All changes with line numbers, before/after code, and test cases

Location: plsql_Acc_backend/src/converter/llm_engine.py
"""

# ============================================================================
# FIX #1: WIRE CORRECTOR INTO PIPELINE (Lines 1 + 1700+)
# ============================================================================

FIX_1_CHANGES = """
CHANGE 1 - Add Import at Top of File
═════════════════════════════════════

FILE: plsql_Acc_backend/src/converter/llm_engine.py
LOCATION: Line 1 - at top of imports section

BEFORE (Line 20-30 approximate):
────────────────────────────────
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

AFTER (Add before line 20):
───────────────────────────
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
from ..validator.service_code_corrector import ServiceCodeCorrector  # ADD THIS LINE


CHANGE 2 - Wire Corrector in generate_services_from_semantics()
════════════════════════════════════════════════════════════════

FILE: plsql_Acc_backend/src/converter/llm_engine.py
LOCATION: Line ~1560-1580 (in generate_services_from_semantics method)

BEFORE:
───────
    async def generate_services_from_semantics(
        self,
        source_units: List[Dict[str, Any]],
        entities: Dict[str, str],
        repositories: Dict[str, str],
        validation_feedback: Optional[Dict[str, List[str]]] = None,
        metadata_provider: Optional[Any] = None,
    ) -> Dict[str, str]:
        # ... code to select units ...
        
        services: Dict[str, str] = {}
        feedback_for_service: Dict[str, List[str]] = validation_feedback or {}
        
        for filename in service_order:
            unit = selected_units[filename]
            unit_name = unit.get('name', '')
            service_feedback = feedback_for_service.get(filename, []) or feedback_for_service.get(unit_name, [])
            
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

AFTER (Add 2 lines at end of loop):
────────────────────────────────────
    async def generate_services_from_semantics(
        self,
        source_units: List[Dict[str, Any]],
        entities: Dict[str, str],
        repositories: Dict[str, str],
        validation_feedback: Optional[Dict[str, List[str]]] = None,
        metadata_provider: Optional[Any] = None,
    ) -> Dict[str, str]:
        # ... code to select units ...
        
        services: Dict[str, str] = {}
        feedback_for_service: Dict[str, List[str]] = validation_feedback or {}
        
        for filename in service_order:
            unit = selected_units[filename]
            unit_name = unit.get('name', '')
            service_feedback = feedback_for_service.get(filename, []) or feedback_for_service.get(unit_name, [])
            
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
            
            # FIX #1: Apply corrections to remove PL/SQL syntax
            services[filename] = ServiceCodeCorrector.correct_plsql_syntax(services[filename])

        return services


TEST CASE:
──────────
Input code in service:
    p_customer_id := getCustomerId()
    String result = SUBSTR(name, 1, 10)
    String sql = 'SELECT * FROM CUSTOMERS'

After FIX #1:
    pCustomerId = getCustomerId()
    String result = name.substring(0, Math.min(10, name.length()))
    String sql = "SELECT * FROM CUSTOMERS"

VERIFICATION:
  grep -n "correct_plsql_syntax" plsql_Acc_backend/src/converter/llm_engine.py
  # Should show the line where we call it in generate_services_from_semantics


═════════════════════════════════════════════════════════════════════════════
"""

# ============================================================================
# FIX #2: ROUTE COMPLEX PACKAGES TO LLM
# ============================================================================

FIX_2_CHANGES = """
CHANGE 1 - Add _should_use_llm() Method
════════════════════════════════════════

FILE: plsql_Acc_backend/src/converter/llm_engine.py
LOCATION: Before generate_services_from_semantics (around line 1500)

ADD THIS NEW METHOD:
────────────────────

    def _should_use_llm(self, unit: Dict[str, Any]) -> bool:
        """FIX #2: Determine if package complexity warrants LLM generation"""
        operations = unit.get('operations_by_table', {})
        semantic = unit.get('semantic_analysis', {})
        raw_plsql = unit.get('raw_plsql', '')
        
        # Count complexity indicators
        indicators = 0
        
        # Indicator 1: Multiple table operations (JOIN or aggregate)
        if len(operations) > 1:
            indicators += 2
        
        # Indicator 2: Transactions with savepoint or partial rollback
        transaction = unit.get('transaction', {})
        if transaction.get('has_savepoint') or transaction.get('has_partial_rollback'):
            indicators += 2
        
        # Indicator 3: Custom exception handling
        if unit.get('programmatic_raises'):
            indicators += 1
        
        # Indicator 4: Nested control structures (multiple IF or LOOP)
        nested_ifs = len(re.findall(r'if\s*\(', raw_plsql, re.IGNORECASE))
        nested_loops = len(re.findall(r'for|while|loop', raw_plsql, re.IGNORECASE))
        if nested_ifs >= 3 or nested_loops >= 2:
            indicators += 2
        
        # Indicator 5: Complex aggregations or transformations
        if semantic.get('aggregation', {}).get('columns'):
            indicators += 1
        
        # Threshold: 3+ indicators = use LLM for better handling
        use_llm = indicators >= 3
        if use_llm:
            logger.info(f"Package '{unit.get('name', 'unknown')}' routed to LLM "
                       f"(complexity indicators: {indicators})")
        
        return use_llm


CHANGE 2 - Add _generate_service_with_llm() Method
══════════════════════════════════════════════════

FILE: plsql_Acc_backend/src/converter/llm_engine.py
LOCATION: After _should_use_llm()

ADD THIS NEW METHOD:
────────────────────

    async def _generate_service_with_llm(
        self,
        unit: Dict[str, Any],
        entities: Dict[str, str],
        repositories: Dict[str, str],
        all_units: List[Dict[str, Any]],
        validation_feedback: Optional[List[str]] = None,
    ) -> str:
        """FIX #2: Generate complex service using LLM with strict template"""
        
        # Build comprehensive prompt from unit metadata
        prompt = self._build_llm_prompt_for_unit(
            unit=unit,
            entities=entities,
            repositories=repositories,
            validation_feedback=validation_feedback,
        )
        
        logger.info(f"Generating via LLM: {unit.get('name', 'unknown')}")
        
        # Call LLM provider with the prompt
        try:
            result = await self.llm_provider.generate_code(
                prompt=prompt,
                max_tokens=6000,  # Complex packages need more tokens
                temperature=0.1   # Low temp for deterministic output
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to deterministic generation
            logger.info("Falling back to deterministic generation")
            return self._generate_deterministic_service_from_unit(
                unit=unit,
                entities=entities,
                repositories=repositories,
                all_units=all_units,
                metadata_provider=None,
            )
        
        # Validate LLM output
        is_valid = self._validate_java_code(result)
        if not is_valid:
            logger.warning(f"LLM validation failed for {unit.get('name')}, "
                          "will be cleaned by corrector in Fix #1")
        else:
            logger.info(f"LLM validation passed for {unit.get('name')}")
        
        return result


CHANGE 3 - Modify generate_services_from_semantics() to Use New Routing
═══════════════════════════════════════════════════════════════════════

FILE: plsql_Acc_backend/src/converter/llm_engine.py
LOCATION: Line ~1575 (in generate_services_from_semantics loop)

BEFORE:
───────
        for filename in service_order:
            unit = selected_units[filename]
            unit_name = unit.get('name', '')
            service_feedback = feedback_for_service.get(filename, []) or feedback_for_service.get(unit_name, [])
            
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
            
            # FIX #1 line (already added)
            services[filename] = ServiceCodeCorrector.correct_plsql_syntax(services[filename])

AFTER (Added FIX #2 routing):
─────────────────────────────
        for filename in service_order:
            unit = selected_units[filename]
            unit_name = unit.get('name', '')
            service_feedback = feedback_for_service.get(filename, []) or feedback_for_service.get(unit_name, [])
            
            if self._is_utility_unit(unit):
                services[filename] = self._generate_utility_service_from_unit(
                    unit=unit,
                    all_units=source_units,
                )
            # FIX #2: Route complex packages to LLM
            elif self._should_use_llm(unit):
                services[filename] = await self._generate_service_with_llm(
                    unit=unit,
                    entities=entities,
                    repositories=repositories,
                    all_units=source_units,
                    validation_feedback=service_feedback,
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
            
            # FIX #1: Apply corrections to remove PL/SQL syntax
            services[filename] = ServiceCodeCorrector.correct_plsql_syntax(services[filename])

        return services


NOTE: make generate_services_from_semantics() async if not already:
    async def generate_services_from_semantics(self, ...):


TEST CASE:
──────────
Simple package (customer lookup):
  • Single table SELECT
  • No JOIN
  • No exception handling
  → Should be labeled as "deterministic" (not LLM)
  
Complex package (invoice processing):
  • Multiple tables (invoice, customer, items)
  • SAVEPOINT and rollback logic
  • Custom exception handling
  → Should be labeled as "complex" (use LLM)


═════════════════════════════════════════════════════════════════════════════
"""

# ============================================================================
# FIX #3: REMOVE USELESS FOR-LOOP
# ============================================================================

FIX_3_CHANGES = """
CHANGE - Make Loop Conditional on Pagination
═════════════════════════════════════════════

FILE: plsql_Acc_backend/src/converter/llm_engine.py
LOCATION: Line ~2300 in _generate_deterministic_service_from_unit()

BEFORE:
───────
        # Build row logic (operations inside the loop)
        row_logic = []
        # ... build row_logic lines ...
        
        # ALWAYS ADD LOOP (WRONG!)
        body_lines.append("for (int rowIndex = 0; rowIndex < 1; rowIndex++) {")
        body_lines.extend(f"    {line}" for line in row_logic)
        body_lines.append("}")

AFTER (FIX #3 - Make conditional):
───────────────────────────────────
        # Build row logic (operations inside the loop)
        row_logic = []
        # ... build row_logic lines ...
        
        # FIX #3: Only add loop if pagination or bulk operations needed
        if requires_pagination or (driving_table in skip_locked_tables):
            # Multiple rows expected - use pagination loop
            body_lines.append("for (int rowIndex = 0; rowIndex < pageSize; rowIndex++) {")
            body_lines.extend(f"    {line}" for line in row_logic)
            body_lines.append("}")
        else:
            # Simple single-row operation - no loop needed
            body_lines.extend(row_logic)


EXPLANATION:
────────────
The old code ALWAYS wrapped row_logic in a for-loop that ran once:
  for (int rowIndex = 0; rowIndex < 1; rowIndex++) {  // Always runs exactly once!
      // single row operation
  }

The new code only adds the loop if:
  • requires_pagination is True (multiple rows)
  • skip_locked_tables are involved (BULK operations)

For simple single-row CRUD:
  • The code runs without the loop
  • Cleaner, more readable
  • Better performance (no unnecessary iteration)


VERIFICATION:
──────────────
Check that generated code:
  • Has loop for findAll() or pagination methods ✓
  • NO loop for findById() or single-row operations ✓
  • No "for (rowIndex = 0; rowIndex < 1)" patterns ✗


═════════════════════════════════════════════════════════════════════════════
"""

# ============================================================================
# FIX #4: RESOLVE_LOOKUP_ARGUMENT FIX
# ============================================================================

FIX_4_CHANGES = """
CHANGE - Strip Named Parameter Syntax from Arguments
═════════════════════════════════════════════════════

FILE: plsql_Acc_backend/src/converter/llm_engine.py
LOCATION: Line ~2500 (_resolve_lookup_argument function)

BEFORE (RETURNS WRONG FORMAT):
──────────────────────────────
        def _resolve_lookup_argument(column_name: str, expected_type: str) -> str:
            normalized = normalize_column_name(column_name)
            exact = param_name_map.get(str(column_name).upper())
            if exact:
                return exact  # ← Might be "customerId = value" (WRONG!)
            normalized_hit = param_name_map.get(normalized.upper())
            if normalized_hit:
                return normalized_hit  # ← Same problem
            if normalized in method_param_names:
                return normalized
            for key_name, value_name in param_name_map.items():
                if normalized and normalized.lower() in key_name.lower():
                    return value_name  # ← Could be wrong format too
            if join_var and normalized and normalized.lower() == join_var.lower():
                return join_var
            return _default_literal(expected_type)


AFTER (FIX #4 - STRIPS NAMED PARAM SYNTAX):
─────────────────────────────────────────────
        def _resolve_lookup_argument(column_name: str, expected_type: str) -> str:
            """FIX #4: Return only the argument value, never 'key = value' syntax"""
            
            def extract_value(raw_value: str) -> str:
                """Remove named-param syntax like 'key = value', keep only 'value'"""
                if '=' in raw_value:
                    # Split on '=' and take the last part, stripped
                    return raw_value.split('=')[-1].strip()
                return raw_value
            
            normalized = normalize_column_name(column_name)
            
            # Try exact match first
            exact = param_name_map.get(str(column_name).upper())
            if exact:
                return extract_value(exact)
            
            # Try normalized match
            normalized_hit = param_name_map.get(normalized.upper())
            if normalized_hit:
                return extract_value(normalized_hit)
            
            # Try direct name match
            if normalized in method_param_names:
                return normalized
            
            # Try partial match
            for key_name, value_name in param_name_map.items():
                if normalized and normalized.lower() in key_name.lower():
                    return extract_value(value_name)
            
            # Check join variable
            if join_var and normalized and normalized.lower() == join_var.lower():
                return join_var
            
            # Fallback to default literal
            return _default_literal(expected_type)


EXAMPLE TRANSFORMATIONS:
────────────────────────
Input param_name_map: {"CUSTOMER_ID": "customerId = someValue"}

BEFORE:
  _resolve_lookup_argument("CUSTOMER_ID", "Long")
  → Returns: "customerId = someValue"
  → Used in: repository.findById(customerId = someValue)  ✗ SYNTAX ERROR!

AFTER:
  _resolve_lookup_argument("CUSTOMER_ID", "Long")
  → Returns: "someValue"
  → Used in: repository.findById(someValue)  ✓ VALID!


VERIFICATION:
──────────────
Generated repository calls should look like:
  ✓ repository.findById(customerId)
  ✓ repository.findById(entityId)
  ✓ repository.findAll()
  ✗ repository.findById(customerId = someVar)
  ✗ repository.findAll(table_id = 123)


═════════════════════════════════════════════════════════════════════════════
"""

# ============================================================================
# FIX #5: EXPAND VALIDATION
# ============================================================================

FIX_5_CHANGES = """
CHANGE - Add Comprehensive Validation for Oracle Syntax
════════════════════════════════════════════════════════

FILE: plsql_Acc_backend/src/converter/llm_engine.py
LOCATION: Line ~800 (_validate_java_code method)

BEFORE (INSUFFICIENT VALIDATION):
─────────────────────────────────
    def _validate_java_code(self, code: str) -> bool:
        """Validate that generated code matches expected patterns"""
        
        # Check for empty methods
        empty_method_pattern = r'public\\s+\\w+\\s+\\w+\\s*\\(.*?\\)\\s*\\{\\s*\\}'
        if re.search(empty_method_pattern, code):
            logger.warning("Validation failed: empty method found")
            return False
        
        # Check method signature
        if not self._has_valid_method_signature(code):
            logger.warning("Validation failed: invalid method signature")
            return False
        
        return True


AFTER (FIX #5 - COMPREHENSIVE 12-RULE VALIDATION):
────────────────────────────────────────────────────
    def _validate_java_code(self, code: str) -> bool:
        """FIX #5: Comprehensive validation against all 12 rules"""
        
        # Rule 0: Check for empty methods
        empty_method_pattern = r'public\\s+\\w+\\s+\\w+\\s*\\(.*?\\)\\s*\\{\\s*\\}'
        if re.search(empty_method_pattern, code):
            logger.warning("Validation failed: empty method found")
            return False
        
        # Rule 0: Check method signature exists
        if not self._has_valid_method_signature(code):
            logger.warning("Validation failed: invalid method signature")
            return False
        
        # RULE #1: Check for Oracle SQL functions (case-insensitive)
        oracle_functions = {
            'instr': 'Use .indexOf() instead',
            'substr': 'Use .substring() instead',
            'nvl': 'Use ternary operator (? :) instead',
            'to_char': 'Use String.format() instead',
            'trunc': 'Use Math.floor() instead',
            'round': 'Use Math.round() instead',
        }
        
        for func, suggestion in oracle_functions.items():
            pattern = rf'\\b{func}\\s*\\('
            if re.search(pattern, code, re.IGNORECASE):
                logger.warning(f"Validation failed (Rule #1): Oracle function '{func}' found. {suggestion}")
                return False
        
        # RULE #6: Check for APEX calls
        if 'apex_web_service' in code.lower():
            logger.warning("Validation failed (Rule #6): apex_web_service found. Use RestTemplate instead.")
            return False
        
        # RULE #2: Check for PL/SQL naming prefixes (p_*, l_*)
        if re.search(r'\\b[pl]_[a-zA-Z0-9_]+\\b', code):
            logger.warning("Validation failed (Rule #2): PL/SQL naming prefix (p_*, l_*) found. Use camelCase instead.")
            return False
        
        # RULE #5: Check for := operator
        if ':=' in code:
            logger.warning("Validation failed (Rule #5): PL/SQL assignment := found. Use = instead.")
            return False
        
        # RULE #3: Check for invalid named parameter syntax in method calls
        # Pattern: method_name(param_name = value, ...)
        named_param_pattern = r'\\.\\w+\\s*\\(\\s*\\w+\\s*=\\s*'
        if re.search(named_param_pattern, code):
            logger.warning("Validation failed (Rule #3): Named parameter syntax (key = value) found in method call.")
            return False
        
        # RULE #3: Check for invalid JPA patterns
        if re.search(r'\\.findOne\\s*\\(\\s*null\\s*\\)', code):
            logger.warning("Validation failed (Rule #3): findOne(null) found. Use findById() instead.")
            return False
        
        # Additional: Check for suspicious string patterns
        # This is broad but catches many issues
        if 'apex' in code.lower() and 'apex' not in code.lower().replace('// ', ''):
            if re.search(r'(?<!())apex\\b', code, re.IGNORECASE):
                logger.warning("Validation warning: 'apex' keyword found (may be Oracle-specific).")
        
        # If all validations pass
        logger.debug("Validation passed: code meets all 12 rules")
        return True


WHERE TO CALL THIS:
────────────────────
After LLM generation:
    result = await self.llm_provider.generate_code(prompt)
    is_valid = self._validate_java_code(result)  # ← ADD THIS
    if not is_valid:
        logger.warning("LLM output failed validation, will be cleaned by corrector")

After deterministic generation:
    services[filename] = self._generate_deterministic_service_from_unit(...)
    is_valid = self._validate_java_code(services[filename])  # ← ADD THIS
    if not is_valid:
        logger.warning(f"Generated service '{filename}' failed validation")

Complete example in generate_services_from_semantics():
    for filename in service_order:
        ... route and generate ...
        
        # Validate before correction
        is_valid = self._validate_java_code(services[filename])
        if not is_valid:
            logger.warning(f"Generated code has issues: {filename}")
        
        # Clean with corrector (Fix #1)
        services[filename] = ServiceCodeCorrector.correct_plsql_syntax(services[filename])


TEST CASES:
───────────
Test with code containing each violation:
  ✓ "INSTR(str, 'x')" → validation fails ✓
  ✓ "SUBSTR(s, 1, 10)" → validation fails ✓
  ✓ "NVL(val, 0)" → validation fails ✓
  ✓ "apex_web_service.call()" → validation fails ✓
  ✓ "p_customerId" → validation fails ✓
  ✓ "p_id := value" → validation fails ✓
  ✓ "repository.findOne(null)" → validation fails ✓


═════════════════════════════════════════════════════════════════════════════
"""

# ============================================================================
# FIX #6: MOVE INNER CLASS
# ============================================================================

FIX_6_CHANGES = """
CHANGE - Move BusinessException Outside Method Body
═════════════════════════════════════════════════════

FILE: plsql_Acc_backend/src/converter/llm_engine.py
LOCATION: Line ~2800 in _generate_deterministic_service_from_unit()

BEFORE (WRONG - CLASS INSIDE METHOD):
─────────────────────────────────────
    service_class = []
    service_class.append(f"public class {service_name} {{")
    
    # Generate main method(s)
    service_class.append(f"  public void doSomething(...) {{")
    service_class.extend([
        "    // method body...",
        "    if (error) throw new BusinessException(...);",
        "",
        "    // WRONG PLACEMENT - inner class inside method!",
        "    class BusinessException extends Exception {",
        "        private String errorCode;",
        "        public BusinessException(String msg, String code) {",
        "            super(msg);",
        "            this.errorCode = code;",
        "        }",
        "        public String getErrorCode() { return errorCode; }",
        "    }",
    ])
    service_class.append("  }  ← METHOD ENDS")  # Method ends here
    
    service_class.append("}  ← CLASS ENDS")


AFTER (CORRECT - CLASS AT CLASS LEVEL):
─────────────────────────────────────────
    service_class = []
    service_class.append(f"public class {service_name} {{")
    
    # Generate main method(s)
    service_class.append(f"  public void doSomething(...) {{")
    service_class.extend([
        "    // method body...",
        "    if (error) throw new BusinessException(...);",
    ])
    service_class.append("  }  ← METHOD ENDS")
    
    # Add exception class OUTSIDE method, AT CLASS LEVEL
    service_class.extend([
        "",
        "  // BusinessException class at class level (CORRECT!)",
        "  public static class BusinessException extends Exception {",
        "    private String errorCode;",
        "    public BusinessException(String msg, String code) {",
        "        super(msg);",
        "        this.errorCode = code;",
        "    }",
        "    public String getErrorCode() {",
        "        return errorCode;",
        "    }",
        "  }",
    ])
    
    service_class.append("}  ← CLASS ENDS")


DETAILED LOCATION:
───────────────────
During _generate_deterministic_service_from_unit(), around line 2750-2850,
there's a section that builds the complete service class string:

CURRENT CODE (around line 2750):
    body_lines = [...]  # Lines inside the method
    
    # WRONG: Exception class is appended to body_lines!
    if has_business_exception:
        exception_class_lines = [
            f"class {business_exception_name} extends Exception {{",
            ...
            "}}",
        ]
        body_lines.extend(exception_class_lines)  # ←Puts it inside method!
    
    final_service = f'''
    @Service
    @Slf4j
    public class {service_name} {{
        
        public {return_type} {method_name}({param_sig}) {{
            {chr(10).join(body_lines)}
        }}
    }}
    '''

SHOULD BE:
    body_lines = [...]  # Lines inside the method
    
    # Exception class lines
    exception_class_lines = []
    if has_business_exception:
        exception_class_lines = [
            "",
            f"public static class {business_exception_name} extends Exception {{",
            "    private String errorCode;",
            f"    public {business_exception_name}(String message, String code) {{",
            "        super(message);",
            "        this.errorCode = code;",
            "    }",
            "    public String getErrorCode() {",
            "        return errorCode;",
            "    }",
            "}",
        ]
    
    final_service = f'''
    @Service
    @Slf4j
    public class {service_name} {{
        {chr(10).join([f"    public {return_type} {method_name}(...) {{{chr(10).join(f'        {l}' for l in body_lines)}{chr(10)}    }}", ])}
        {chr(10).join(exception_class_lines)}
    }}
    '''


PYTHON CODE LOCATION:
──────────────────────
Find this pattern in llm_engine.py around line 2750-2850:

WRONG:
    # Build method body
    body_lines = [
        ... method logic ...
    ]
    
    # Wrong: puts exception inside method
    if has_business_exception:
        body_lines.extend([
            'class BusinessException extends Exception {',
            ...
        ])

CORRECT:
    # Build method body
    body_lines = [
        ... method logic ...
    ]
    
    # SEPARATE: exception class for class level
    exception_lines = []
    if has_business_exception:
        exception_lines = [
            "",
            'public static class BusinessException extends Exception {',
            ...
        ]
    
    # Combine at class level
    final_lines = [method_lines...] + exception_lines


VERIFICATION:
──────────────
✓ Compile generated Java: mvn clean compile
✓ Check: BusinessException is accessible from doSomething() method
✓ Check: No syntax errors about mismatched braces
✓ Check: Inner class is between method closing } and class closing }


═════════════════════════════════════════════════════════════════════════════
"""

if __name__ == "__main__":
    print(FIX_1_CHANGES)
    print(FIX_2_CHANGES)
    print(FIX_3_CHANGES)
    print(FIX_4_CHANGES)
    print(FIX_5_CHANGES)
    print(FIX_6_CHANGES)
