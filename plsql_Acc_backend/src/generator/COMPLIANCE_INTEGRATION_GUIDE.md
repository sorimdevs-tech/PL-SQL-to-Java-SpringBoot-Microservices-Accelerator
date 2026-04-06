"""
JAVA GENERATION COMPLIANCE INTEGRATION GUIDE

This document shows how the 12-rule compliance enforcer is integrated into the
PL/SQL-to-Java generator pipeline to prevent errors before code is written.
"""

# ============================================================================
# INTEGRATION POINTS IN THE GENERATOR PIPELINE
# ============================================================================

# 1. IN plsql_to_java_converter.py
#    ✓ INTEGRATED: generate_java_method() now wraps all generated methods
#      with enforce_java_compliance() before returning
#
#    Location: Line ~1200 (after building final_code, before return)
#    What it does:
#      - Validates method against all 12 rules
#      - Logs violations with severity
#      - Returns corrected code
#      - Examples: Remove Oracle syntax, fix variable names, etc.

# EXAMPLE USAGE:
"""
from java_generation_compliance_enforcer import enforce_java_compliance

# During method generation:
corrected_code, is_compliant, violations = enforce_java_compliance(
    method_code=final_code,
    method_name="executePayment"
)

if not is_compliant:
    logger.warning(f"Method {method_name} has {len(violations)} violations")
    for v in violations:
        logger.warning(f"  → {v}")

# Use the corrected code in all output
return corrected_code
"""


# 2. IN spring_boot_generator.py - generate_services()
#    HOW TO INTEGRATE:
#
#    After each service class is built, before writing to file:
"""
from java_generation_compliance_enforcer import JavaComplianceEnforcer

# After service_code is generated:
class_result = JavaComplianceEnforcer.validate_class(
    service_code,
    class_name=service_name
)

if not class_result.is_compliant:
    logger.warning(f"\nCOMPLIANCE: Service '{service_name}' has violations:")
    for v in class_result.violations:
        logger.warning(f"  • {v}")
    logger.warning("Correcting code...\n")

# Always use corrected code
service_code = class_result.corrected_code
"""


# 3. IN spring_boot_generator.py - generate_controllers()
#    HOW TO INTEGRATE:
#
"""
# Before writing controller code to file:
controller_result = JavaComplianceEnforcer.validate_class(
    controller_code,
    class_name=controller_name
)

if not controller_result.is_compliant:
    logger.warning(f"\nCOMPLIANCE: Controller '{controller_name}' has violations:")
    for v in controller_result.violations:
        logger.warning(f"  • {v}")

controller_code = controller_result.corrected_code
"""


# ============================================================================
# THE 12 RULES BEING ENFORCED
# ============================================================================

RULES_ENFORCED = {
    "Rule 1": "Strip Oracle-specific syntax (named params, SQL functions, APEX, Logger)",
    "Rule 2": "Fix variable declaration issues (no duplicates, camelCase, initialized before use)",
    "Rule 3": "Proper class/annotation structure (fields inside class, no dangling methods)",
    "Rule 4": "Correct JPA repository calls (findById().orElse(), not find(null))",
    "Rule 5": "Return proper types (String not Object, DTO not Object)",
    "Rule 6": "Autonomous transactions with @Transactional(propagation = ...)",
    "Rule 7": "Include ALL PL/SQL steps (validation, logging, saves - never skip)",
    "Rule 8": "Replace apex_web_service with RestTemplate + proper headers",
    "Rule 9": "Replace string JSON parsing with Jackson ObjectMapper",
    "Rule 10": "Replace package globals with Spring @Value injection",
    "Rule 11": "Convert PL/SQL overloads to separate named Java methods",
    "Rule 12": "Controller methods return values, never void"
}


# ============================================================================
# WORKFLOW: HOW CODE FLOWS THROUGH COMPLIANCE
# ============================================================================

WORKFLOW = """
┌─────────────────────────────────────────────────────────┐
│  PL/SQL Code (procedure/function)                       │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Parser extracts:                                       │
│  - Procedure signature                                  │
│  - Parameters                                           │
│  - Logic patterns (SELECT, INSERT, UPDATE, DELETE)     │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  plsql_to_java_converter.py                             │
│  Translates logic → Java method skeleton                │
│  (May have Oracle syntax, naming issues)                │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  ✨ COMPLIANCE ENFORCER ✨                              │
│  Validates against 12 rules:                            │
│  - Strips Oracle syntax                                 │
│  - Fixes variable names                                 │
│  - Corrects repository calls                            │
│  - Ensures proper types                                 │
│  - Fixes all detected issues                            │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  Compliant Java Method                                  │
│  (Ready to include in service class)                    │
└─────────────────────────────────────────────────────────┘
"""


# ============================================================================
# SAMPLE: BEFORE AND AFTER COMPLIANCE
# ============================================================================

BEFORE = """
// BAD - Oracle syntax, wrong names, no validation
public Object getCustomerInfo(p_customer_id) {
    var result = null;
    result = repository.findOne(customer_id = p_customer_id);
    return result;
}
"""

AFTER = """
// GOOD - Compliant with all rules
public XyCustomerEntity getCustomerInfo(Long customerId) {
    var result = repository.findById(customerId).orElse(null);
    return result;
}
"""

VIOLATIONS_DETECTED = [
    "Rule #1: Named parameter syntax found 'customer_id =' - use positional args",
    "Rule #2: Variable 'result' declared before initialized",
    "Rule #4: repository.findOne(customer_id = ...) - use findById() instead",
    "Rule #5: Returning Object instead of XyCustomerEntity"
]


# ============================================================================
# LOGGING OUTPUT EXAMPLE
# ============================================================================

LOG_EXAMPLE = """
================================================================================
JAVA GENERATION COMPLIANCE ENFORCER - VALIDATION REPORT
================================================================================

Validating method: execute_payment

✗ CODE HAS 5 COMPLIANCE VIOLATIONS:

1. Rule #1 VIOLATION: Named parameter syntax found '(url = ' - use positional 
   arguments or method overloading instead

2. Rule #1 VIOLATION: Oracle SQL function 'substr()' found - should be 
   translated to Java equivalent

3. Rule #4 VIOLATION: repository.delete(id) - should be repository.deleteById(id) 
   for single ID deletion

4. Rule #8 VIOLATION: apex_web_service.make_rest_request found - replace with 
   RestTemplate or WebClient

5. Rule #9 VIOLATION: JSON parsing with string manipulation detected - use 
   Jackson ObjectMapper instead

================================================================================

Correcting code using preferred Java patterns...
Method is now compliant and ready for use.
"""


# ============================================================================
# KEY FUNCTIONS
# ============================================================================

KEY_FUNCTIONS = """
1. enforce_java_compliance(method_code: str, method_name: str)
   ├─ Validates method against all 12 rules
   ├─ Returns: (corrected_code, is_compliant, violations_list)
   └─ Called automatically from generate_java_method()

2. JavaComplianceEnforcer.validate_class(class_code: str, class_name: str)
   ├─ Validates entire class (all methods + structure)
   ├─ Returns: ComplianceResult(is_compliant, violations, corrected_code)
   └─ Use in spring_boot_generator.py before writing classes

3. ComplianceReportGenerator.generate_report(result: ComplianceResult)
   ├─ Generates human-readable compliance report
   ├─ Lists all violations with explanations
   └─ Use for logging and debugging

4. Specific rule checkers (internal):
   ├─ _check_oracle_syntax()
   ├─ _check_variable_declarations()
   ├─ _check_jpa_repository()
   ├─ _check_return_types()
   ├─ _check_autonomous_transactions()
   ├─ _check_all_steps_included()
   ├─ _check_http_client()
   ├─ _check_json_handling()
   ├─ _check_package_globals()
   └─ _check_controller_returns()
"""


# ============================================================================
# EXPECTED VIOLATIONS THAT WILL BE CAUGHT & FIXED
# ============================================================================

CATCHES = """
✓ Oracle named parameters:     repository.delete(customer_id = x) → repository.deleteById(x)
✓ Oracle SQL functions:        substr(...) → .substring(...)
                               nvl(...) → ternary operator
                               instr(...) → .indexOf(...)
✓ Oracle APEX:                 apex_web_service → removed, use RestTemplate
✓ Oracle Logger:               logger.append_param → log.debug
✓ Duplicate var declarations:  var x = ...; var x = ... → detected & flagged
✓ Wrong variable names:        p_customer_id → customerId
✓ Uninitialized references:    if (x == null) before var x = ...
✓ Wrong return types:          return Object → return SpecificType
✓ Missing @Transactional:      autonomous transaction logic without annotation
✓ Unsafe substrings:           .substring(0, 255) → guarded with Math.min()
✓ JSON string parsing:         substr + indexOf chains → ObjectMapper
✓ Hardcoded config:            "https://api.paypal.com" → @Value injection
✓ Empty controller returns:    void methods → return computed results
"""


# ============================================================================
# INTEGRATION CHECKLIST
# ============================================================================

INTEGRATION_CHECKLIST = """
☐ 1. Compliance enforcer created: java_generation_compliance_enforcer.py
☐ 2. Import added to plsql_to_java_converter.py
☐ 3. compliance check wrapped around generate_java_method() return
☐ 4. Import added to spring_boot_generator.py
☐ 5. compliance check added to generate_services() before file write
☐ 6. compliance check added to generate_controllers() before file write
☐ 7. Test with real PL/SQL procedures to verify all 12 rules work
☐ 8. Review logs for any missed violations
☐ 9. Iterate if new violation patterns found
☐ 10. Document any custom rules or exceptions
"""


# ============================================================================
# HOW TO USE THIS IN YOUR GENERATOR CALLS
# ============================================================================

USAGE_EXAMPLE = """
# In your main generation code:

from src.generator.java_generation_compliance_enforcer import (
    enforce_java_compliance,
    JavaComplianceEnforcer
)

# For methods:
corrected_method, is_compliant, violations = enforce_java_compliance(
    method_code,
    method_name="myMethod"
)

# For classes (services, controllers):
class_result = JavaComplianceEnforcer.validate_class(
    class_code,
    class_name="MyService"
)

if not class_result.is_compliant:
    print("Violations found:")
    for v in class_result.violations:
        print(f"  - {v}")
    
    # Use corrected code
    class_code = class_result.corrected_code
    
# Write class_code to file
"""


# ============================================================================
# TESTING
# ============================================================================

TEST_PLAN = """
To test the compliance enforcer:

1. Test each rule independently:
   example_code = "public Object foo(p_id) { ... }"  # Rule 1, 2, 5
   result = JavaComplianceEnforcer.validate_method(example_code)
   assert not result.is_compliant
   assert len(result.violations) > 0

2. Test real service/controller output:
   Run generator on sample PL/SQL → check logs for violations
   
3. Verify fixes are correct:
   Before: result = repository.find(customer_id = x)
   After:  result = repository.findById(x).orElse(null)

4. Test class-level validation:
   class_code = full_service_class
   result = JavaComplianceEnforcer.validate_class(class_code)
   
5. Integration test:
   End-to-end PL/SQL → Java with compliance checking
"""

print(__doc__)
