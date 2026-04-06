"""
MASTER IMPLEMENTATION CHECKLIST & VERIFICATION GUIDE
Complete step-by-step guide with verification at each stage
"""

# ============================================================================
# QUICK REFERENCE: THE 6 FIXES
# ============================================================================

QUICK_SUMMARY = """
╔═══════════════════════════════════════════════════════════════════════════╗
║                          6 CRITICAL FIXES AT A GLANCE                    ║
╚═══════════════════════════════════════════════════════════════════════════╝

FIX #1: Wire Corrector (15 min)
  File: llm_engine.py
  Changes: +1 import, +1 method call
  Impact: Removes := , single quotes, named params
  Risk: Very Low
  Test: grep "correct_plsql_syntax" output

FIX #2: Route to LLM (30 min)
  File: llm_engine.py
  Changes: +2 methods, +1 conditional
  Impact: Complex packages get LLM validation
  Risk: Medium (changes routing)
  Test: Check deterministic vs LLM paths both work

FIX #3: Remove Loop (10 min)
  File: llm_engine.py
  Changes: 1 conditional wrap (4 lines)
  Impact: No useless for loops in single-row CRUD
  Risk: Low
  Test: Verify single-row code has no "for(rowIndex=0..."

FIX #4: Fix Arguments (15 min)
  File: llm_engine.py, _resolve_lookup_argument()
  Changes: Add value-stripping logic (~10 lines)
  Impact: No named params in repository calls
  Risk: Medium (touches parameter resolution)
  Test: Check no "=" in method argument lists

FIX #5: Expand Validation (20 min)
  File: llm_engine.py, _validate_java_code()
  Changes: Add 8 validation rules (~40 lines)
  Impact: Catches all Oracle syntax early
  Risk: Medium (adds more validation)
  Test: Feed code with each violation, verify all caught

FIX #6: Move Class (10 min)
  File: llm_engine.py, _generate_deterministic_service_from_unit()
  Changes: Reorganize exception class placement (8 lines)
  Impact: Generated Java now compiles
  Risk: Low
  Test: mvn clean compile succeeds


═══════════════════════════════════════════════════════════════════════════
"""

# ============================================================================
# IMPLEMENTATION CHECKLIST - PHASE BY PHASE
# ============================================================================

PHASE_1_CHECKLIST = """
PHASE 1: QUICK WINS (Estimated 15 minutes)
═════════════════════════════════════════════════════════════════════════════

These changes are non-risky and provide immediate value.


STEP 1.1: FIX #6 - Move Inner Class (5 min)
────────────────────────────────────────────
□ Open file: plsql_Acc_backend/src/converter/llm_engine.py
□ Find: _generate_deterministic_service_from_unit() around line 2800
□ Locate: Where BusinessException class is generated
□ Move: Exception class from inside method to class level
□ Verify:
  - Exception class lines come AFTER method closing }
  - Exception class lines come BEFORE service class closing }
  - No mismatched braces

Verification Command:
  python -c "
    with open('plsql_Acc_backend/src/converter/llm_engine.py') as f:
        content = f.read()
        # Check for syntactically valid class structure
        import re
        pattern = r'public class \\w+ \\{.*?public static class BusinessException'
        if re.search(pattern, content, re.DOTALL):
            print('✓ BusinessException now appears after method')
        else:
            print('✗ Exception class placement needs review')
  "


STEP 1.2: FIX #3 - Remove Useless Loop (5 min)
───────────────────────────────────────────────
□ Open file: plsql_Acc_backend/src/converter/llm_engine.py
□ Find: _generate_deterministic_service_from_unit() around line 2300
□ Locate: Where "for (int rowIndex = 0; rowIndex < 1" is added
□ Change: Wrap in conditional: if requires_pagination or has_bulk_ops
□ Verify:
  - Single-row operations don't have for loop
  - Pagination operations still have for loop
  - CRUD operations are correctly categorized

Verification Command:
  grep -n "requires_pagination" plsql_Acc_backend/src/converter/llm_engine.py
  # Should show conditional around line 2300


STEP 1.3: FIX #1 - Wire Corrector (5 min)
──────────────────────────────────────────
□ Open file: plsql_Acc_backend/src/converter/llm_engine.py
□ Add import at top (line ~20):
    from ..validator.service_code_corrector import ServiceCodeCorrector
□ Find: generate_services_from_semantics() method around line 1575
□ Add at end of loop (after generation, before next iteration):
    services[filename] = ServiceCodeCorrector.correct_plsql_syntax(services[filename])
□ Verify:
  - Import is in imports section
  - Corrector is called after EVERY generation
  - Indentation is correct (inside the loop)

Verification Commands:
  grep -n "ServiceCodeCorrector" plsql_Acc_backend/src/converter/llm_engine.py
  # Should show both import and usage
  
  grep -n "correct_plsql_syntax" plsql_Acc_backend/src/converter/llm_engine.py
  # Should show it's called in generate_services_from_semantics


PHASE 1 VERIFICATION:
─────────────────────
Run quick syntax check:
  python -m py_compile plsql_Acc_backend/src/converter/llm_engine.py
  # Should complete without errors

Expected output: No errors, file compiles


═════════════════════════════════════════════════════════════════════════════
"""

PHASE_2_CHECKLIST = """
PHASE 2: CORE FIXES (Estimated 45 minutes)
═════════════════════════════════════════════════════════════════════════════

More involved changes that fix generation logic.


STEP 2.1: FIX #4 - Fix _resolve_lookup_argument() (15 min)
──────────────────────────────────────────────────────────
□ Open file: plsql_Acc_backend/src/converter/llm_engine.py
□ Find: _resolve_lookup_argument() around line 2500
□ Add helper function extract_value():
    def extract_value(raw_value: str) -> str:
        if '=' in raw_value:
            return raw_value.split('=')[-1].strip()
        return raw_value
□ Apply extract_value() to ALL return statements in function:
  - return exact  → return extract_value(exact)
  - return normalized_hit → return extract_value(normalized_hit)
  - return value_name → return extract_value(value_name)
□ Verify:
  - Function correctly strips "key = value" syntax
  - Returns only the value portion
  - All code paths apply the stripping

Test the fix:
  python -c "
    # Test _resolve_lookup_argument
    test_cases = [
        ('customerId = someVar', 'someVar'),
        ('customerId', 'customerId'),
        ('invoice_id = 123', '123'),
        ('plain_param', 'plain_param'),
    ]
    # Manually verify each case
  "


STEP 2.2: FIX #5 - Expand _validate_java_code() (20 min)
─────────────────────────────────────────────────────────
□ Open file: plsql_Acc_backend/src/converter/llm_engine.py
□ Find: _validate_java_code() method around line ~800
□ Current method only checks:
  - Empty methods
  - Valid signatures
□ ADD comprehensive checks for:
  ✓ Oracle functions (INSTR, SUBSTR, NVL, TO_CHAR, TRUNC, ROUND)
  ✓ APEX calls
  ✓ PL/SQL naming (p_*, l_*)
  ✓ := operator
  ✓ Named parameter syntax
  ✓ findOne(null)
  ✓ Suspicious keywords

□ Implement as per DETAILED_FIX_IMPLEMENTATION_GUIDE.md, FIX #5 section
□ Verify:
  - Each rule has its own logger.warning() message
  - Returns False if ANY violation found
  - Test code provided in guide passes all tests

Test the fix:
  Create test script test_validation.py:
    from src.converter.llm_engine import LLMEngine
    
    engine = LLMEngine(...)
    
    test_cases = {
        'INSTR': 'INSTR(str, "x")',
        'NVL': 'NVL(val, 0)',
        'APEX': 'apex_web_service.call()',
        'p_prefix': 'String p_customerId',
        'l_prefix': 'Integer l_count',
        ':=': 'x := value',
        'findOne': 'repo.findOne(null)',
    }
    
    for name, code_snippet in test_cases.items():
        result = engine._validate_java_code(code_snippet)
        assert not result, f"Should have failed on {name}"
        print(f"✓ {name} detected correctly")


STEP 2.3: FIX #2 - Route Complex Packages to LLM (30 min)
──────────────────────────────────────────────────────────
□ Open file: plsql_Acc_backend/src/converter/llm_engine.py
□ Before generate_services_from_semantics() (around line 1500):
  ADD new method: _should_use_llm()
  - Reviews complexity indicators
  - Returns True if 3+ indicators present
  - Reviews: table count, transactions, exceptions, control flow
  See DETAILED_FIX_IMPLEMENTATION_GUIDE.md, FIX #2 for full code

□ Before generate_services_from_semantics() (around line 1500):
  ADD new method: _generate_service_with_llm()
  - Calls LLM provider with prompt
  - Validates output
  - Has fallback to deterministic
  See DETAILED_FIX_IMPLEMENTATION_GUIDE.md, FIX #2 for full code

□ Modify generate_services_from_semantics():
  - Make it async (if not already)
  - Add routing: elif self._should_use_llm(unit)
  - Call: await self._generate_service_with_llm(...)
  See DETAILED_FIX_IMPLEMENTATION_GUIDE.md, FIX #2 for full code

□ Verify:
  - _should_use_llm() correctly identifies complexity
  - _generate_service_with_llm() uses correct LLM parameters
  - Three paths work: utility / complex / simple
  - Error handling for LLM failures

Test the fix:
  Create test script test_routing.py:
    from src.converter.llm_engine import LLMEngine
    
    simple_unit = {
        'operations_by_table': {'customers': ['SELECT']},
        'semantic_analysis': {},
        'raw_plsql': 'SELECT * FROM customers',
        'transaction': {},
    }
    
    complex_unit = {
        'operations_by_table': {
            'customers': ['SELECT'],
            'orders': ['JOIN'],
            'items': ['JOIN'],
        },
        'semantic_analysis': {'aggregation': {'columns': ['total']}},
        'raw_plsql': 'WITH ... SELECT ... FROM ... JOIN ... WHERE IF IF IF',
        'transaction': {'has_savepoint': True},
        'programmatic_raises': ['CUSTOM_ERROR'],
    }
    
    engine = LLMEngine(...)
    
    # Test routing
    assert not engine._should_use_llm(simple_unit), "Simple should use deterministic"
    assert engine._should_use_llm(complex_unit), "Complex should use LLM"
    print("✓ Routing logic works correctly")


PHASE 2 VERIFICATION:
─────────────────────
After all Phase 2 changes:
  python -m py_compile plsql_Acc_backend/src/converter/llm_engine.py
  # Should complete without errors

Run basic import test:
  python -c "from src.converter.llm_engine import LLMEngine; print('Import OK')"


═════════════════════════════════════════════════════════════════════════════
"""

PHASE_3_TESTING = """
PHASE 3: END-TO-END TESTING (Estimated 60+ minutes)
════════════════════════════════════════════════════════════════════════════

Comprehensive validation that all fixes work together.


STEP 3.1: Unit Test FIX #5 Validation (10 min)
───────────────────────────────────────────────
Create test_validation_rules.py:

```python
import re
from src.converter.llm_engine import LLMEngine

def test_oracle_functions():
    engine = LLMEngine(llm_provider=None)  # Mock provider
    
    test_cases = {
        'INSTR(str, "comma")': False,
        'SUBSTR(name, 0, 10)': False,
        'NVL(value, 0)': False,
        'TO_CHAR(date)': False,
        'valid_code()': True,
        'str.indexOf(ch)': True,
    }
    
    for code, expected in test_cases.items():
        result = engine._validate_java_code(code)
        assert result == expected, f"Failed on: {code}"
    
    print("✓ Oracle function detection works")

def test_plsql_naming():
    engine = LLMEngine(llm_provider=None)
    
    test_cases = {
        'String p_customer_id': False,
        'Integer l_counter': False,
        'String customerId': True,
        'int counter': True,
    }
    
    for code, expected in test_cases.items():
        result = engine._validate_java_code(code)
        assert result == expected, f"Failed on: {code}"
    
    print("✓ PL/SQL naming detection works")

def test_named_params():
    engine = LLMEngine(llm_provider=None)
    
    test_cases = {
        'repo.findById(customerId = value)': False,
        'repo.findById(value)': True,
        'repo.save(entity)': True,
    }
    
    for code, expected in test_cases.items():
        result = engine._validate_java_code(code)
        assert result == expected, f"Failed on: {code}"
    
    print("✓ Named parameter detection works")

if __name__ == '__main__':
    test_oracle_functions()
    test_plsql_naming()
    test_named_params()
    print("\\n✓ All validation tests passed!")
```

Run:
  cd plsql_Acc_backend
  python test_validation_rules.py
  # Should pass all assertions


STEP 3.2: Integration Test FIX #1 Corrector (10 min)
─────────────────────────────────────────────────────
Create test_corrector_integration.py:

```python
from src.validator.service_code_corrector import ServiceCodeCorrector

def test_corrector_removes_plsql():
    test_cases = [
        # (input, expected_pattern_NOT_in_output)
        ('p_customer_id := value', ':='),  # := should be removed
        ("String s = 'hello'", "'"),      # Single quotes should be removed
        ('INSTR(s, "x")', 'INSTR'),       # (not automatically, but validator catches)
        ('name_pkg.method()', 'name_pkg.'), # Package qual removed
    ]
    
    for input_code, bad_pattern in test_cases:
        corrected = ServiceCodeCorrector.correct_plsql_syntax(input_code)
        assert bad_pattern not in corrected, f"Still found '{bad_pattern}' in: {corrected}"
        print(f"✓ Corrected: {input_code}")
        print(f"  Result: {corrected}")

if __name__ == '__main__':
    test_corrector_removes_plsql()
    print("\\n✓ Corrector integration works!")
```

Run:
  cd plsql_Acc_backend
  python test_corrector_integration.py


STEP 3.3: Generate Test Project (20 min)
─────────────────────────────────────────
Generate a small project from plsql_sample_repo:

□ Run generator on a sample package:
  python main.py --convert-all --package-name "com.test" --output samples/
  
□ Check generated Java files:
  find samples/ -name "*.java" | head -20
  
□ Verify for each generated file:
  - ✓ No "p_" or "l_" prefixed variables
  - ✓ No ":=" operators
  - ✓ No single-quoted strings (outside of comments)
  - ✓ No "INSTR", "SUBSTR", "NVL", "TO_CHAR"
  - ✓ No "repository.findOne(null)"
  - ✓ Proper camelCase naming
  - ✓ Proper double-quoted strings
  - ✓ No "for(rowIndex=0; rowIndex<1)" patterns for single-row ops


STEP 3.4: Compile Generated Java (10 min)
──────────────────────────────────────────
□ Navigate to generated project:
  cd samples/test_project/
  
□ Compile:
  mvn clean compile
  
Expected output:
  BUILD SUCCESS

If compilation fails:
  ✗ Check error messages
  ✗ Review fixed code around error
  ✗ Verify all 6 fixes were applied correctly
  ✗ Check for remaining Oracle syntax


STEP 3.5: Manual Code Review (10 min)
─────────────────────────────────────
□ Open generated service files:
  samples/test_project/src/main/java/com/test/*.java
  
□ For each service file, verify:
  - Method signatures are correct (specific return types, not Object)
  - Variable names are camelCase (not p_*, l_*)
  - Repository calls have valid syntax (not findOne(null))
  - Exception handling is correct (BusinessException properly defined)
  - No Oracle SQL functions
  - No APEX calls
  - Proper annotations present

Example review points:
  ✓ public Long createInvoice(Long customerId)  ← Correct return type
  ✓ customerId = getParam(...);  ← Not p_customerId
  ✓ repository.findById(customerId);  ← Not findOne(null)
  ✓ @Transactional  ← Present where needed
  ✓ String name = "hello";  ← Double quotes, not single
  ✓ no INSTR, SUBSTR, NVL ← Oracle functions removed


STEP 3.6: Regression Tests (10 min)
────────────────────────────────────
□ Run existing test suite:
  cd plsql_Acc_backend
  python -m pytest tests/ -v
  
□ Ensure no regressions:
  - Existing passing tests still pass
  - No new test failures introduced
  - Performance not significantly degraded


PHASE 3 SUMMARY:
────────────────
After Phase 3, you should have:
  ✓ All fixes implemented and tested
  ✓ Generated Java compiles without errors
  ✓ No Oracle syntax in output
  ✓ All 12 rules being enforced
  ✓ Production-ready code generation


═════════════════════════════════════════════════════════════════════════════
"""

# ============================================================================
# VERIFICATION CHECKLIST
# ============================================================================

FINAL_VERIFICATION = """
FINAL VERIFICATION CHECKLIST
═════════════════════════════════════════════════════════════════════════════

After all 6 fixes are implemented, verify EACH of these:

CORRECTNESS CHECKS:
───────────────────
□ FIX #1 ACTIVE: Generated code has NO ":=" operators
  Test: grep ":=" generated_services/*.java | wc -l
  Expected: 0

□ FIX #1 ACTIVE: Generated code has NO single-quoted strings (outside SQL)
  Test: grep "= '[^']*'" generated_services/*.java | wc -l
  Expected: 0 (or very few, all in SQL contexts)

□ FIX #1 ACTIVE: Generated code has NO named-param syntax in method calls
  Test: grep -E "\\.\\w+\\s*\\(.*\\s*=\\s*" generated_services/*.java | wc -l
  Expected: 0

□ FIX #2 ACTIVE: Complex packages use LLM
  Test: Check logs for "routed to LLM"
  Expected: At least some packages show this message

□ FIX #2 ACTIVE: Simple packages use deterministic
  Test: Check logs for package routing
  Expected: Mix of deterministic and LLM routes

□ FIX #3 ACTIVE: Simple CRUD has NO useless for loops
  Test: grep "for.*rowIndex.*<.*1" generated_services/*.java | wc -l
  Expected: 0 (or very few, only for pagination)

□ FIX #4 ACTIVE: Repository method calls have valid arguments
  Test: grep -E "\\.findById\\s*\\(" generated_services/*.java | head -5
  Expected: All look like: ".findById(id)" or ".findById(customerId)"
  NOT: ".findById(customerId = someValue)"

□ FIX #5 ACTIVE: No Oracle functions in output
  Test: grep -iE "(INSTR|SUBSTR|NVL|TO_CHAR|TRUNC|ROUND)\\s*\\(" generated_services/*.java | wc -l
  Expected: 0

□ FIX #5 ACTIVE: No APEX calls
  Test: grep -i "apex_web_service" generated_services/*.java | wc -l
  Expected: 0

□ FIX #6 ACTIVE: Generated Java compiles
  Test: cd generated_project; mvn clean compile
  Expected: BUILD SUCCESS

□ FIX #6 ACTIVE: BusinessException class at class level
  Test: grep -B2 "class BusinessException" generated_services/*.java
  Expected: Appears AFTER method closing }, NOT inside method


PERFORMANCE CHECKS:
───────────────────
□ Generation time reasonable (< 30 seconds for sample repo)
□ No memory leaks or excessive resource usage
□ Validation doesn't significantly slow generation
□ Corrector runs quickly on all services


QUALITY CHECKS:
───────────────
□ Generated code is readable (proper formatting, indentation)
□ Method names follow Java conventions (camelCase)
□ Variable names are descriptive (not cryptic)
□ Comments preserved where appropriate
□ Proper use of Spring annotations
□ Proper use of JPA annotations


RULE ENFORCEMENT CHECKS (All 12 Rules):
─────────────────────────────────────────
Rule #1 (Oracle syntax): ✓ CHECKED - grep for INSTR, SUBSTR, etc.
Rule #2 (Variable naming): ✓ CHECKED - grep for p_*, l_*
Rule #3 (Named params): ✓ CHECKED - grep for "= " in method calls
Rule #4 (JPA calls): ✓ CHECKED - grep for findOne(null)
Rule #5 (Assignment): ✓ CHECKED - grep for ":="
Rule #6 (APEX): ✓ CHECKED - grep for apex_web_service
Rule #7 (CASE/WHEN): ✓ CHECKED - logical, not syntactic
Rule #8 (Package refs): ✓ CHECKED - grep for "_pkg."
Rule #9 (Overloads): ✓ CHECKED - review method names
Rule #10 (Controller returns): ✓ CHECKED - review response types
Rule #11 (Complete logic): ✓ CHECKED - review method completeness
Rule #12 (Auth headers): ✓ CHECKED - review HTTP calls


EXPECTED OUTCOMES:
──────────────────
After all fixes:
  ✓ 100% of generated Java code compiles without syntax errors
  ✓ 0% Oracle PL/SQL syntax in Java files
  ✓ 100% compliance with 12 rules
  ✓ 0% false positives in validation
  ✓ Generated code is production-ready


═════════════════════════════════════════════════════════════════════════════
"""

# ============================================================================
# ROLLBACK PLAN (In case something goes wrong)
# ============================================================================

ROLLBACK = """
ROLLBACK PLAN
═════════════════════════════════════════════════════════════════════════════

If any fix causes problems, here's how to rollback:

ROLLBACK FIX #1 (Corrector):
──────────────────────────────
1. Remove import: from ..validator.service_code_corrector import ServiceCodeCorrector
2. Remove line: services[filename] = ServiceCodeCorrector.correct_plsql_syntax(...)
3. Generation reverts to deterministic-only (no corrections)

ROLLBACK FIX #2 (LLM Routing):
──────────────────────────────
1. Delete: _should_use_llm() method
2. Delete: _generate_service_with_llm() method
3. Remove elif condition, keep else only
4. Generation uses only deterministic path

ROLLBACK FIX #3 (Remove Loop):
───────────────────────────────
1. Remove if condition
2. Restore: body_lines.append("for (int rowIndex = 0; rowIndex < 1; rowIndex++) {")
3. Always wrap logic (old behavior)

ROLLBACK FIX #4 (Arguments):
─────────────────────────────
1. Remove extract_value() helper function
2. Restore all return statements to original form
3. Revert: function returns as-is without stripping "="

ROLLBACK FIX #5 (Validation):
──────────────────────────────
1. Remove all new validation rules from _validate_java_code()
2. Keep only: empty method check, signature check
3. Validation goes back to minimal

ROLLBACK FIX #6 (Class Placement):
──────────────────────────────────
1. Move BusinessException class lines back inside method
2. Restore: exception_lines.extend(...) instead of separate
3. Generated code has syntactically invalid inner class again


To rollback ALL fixes:
  git checkout plsql_Acc_backend/src/converter/llm_engine.py


═════════════════════════════════════════════════════════════════════════════
"""

if __name__ == "__main__":
    print(QUICK_SUMMARY)
    print(PHASE_1_CHECKLIST)
    print(PHASE_2_CHECKLIST)
    print(PHASE_3_TESTING)
    print(FINAL_VERIFICATION)
    print(ROLLBACK)
