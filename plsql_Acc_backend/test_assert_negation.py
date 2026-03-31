#!/usr/bin/env python3
"""
Test to verify that assert() calls from PL/SQL are correctly negated in Java.

The PL/SQL assert() procedure does:
    IF NOT NVL(condition, false) THEN RAISE_APPLICATION_ERROR(...) END IF;

Therefore in Java:
    - PL/SQL: assert(p_amount > 0, 'must be positive')
    - PL/SQL intent: throw if amount <= 0
    - Java: if (!(amount > 0)) { throw ... }  or  if (amount <= 0) { throw ... }
"""

import sys
import os

# Add the backend path
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_path)

from src.parser.plsql_parser import PLSQLParser
from src.generator.plsql_to_java_converter import PLSQLtoJavaConverter

def test_assert_negation():
    """Test that assert conditions are properly negated"""
    
    print("=" * 70)
    print("TESTING ASSERT() NEGATION WITH PROPER SEMANTICS")
    print("=" * 70)
    print()
    
    # Create a mock logic object with error assertions
    from src.generator.improved_plsql_extractor import ExtractedLogic
    
    logic = ExtractedLogic()
    logic.error_assertions = [
        {
            "condition": "p_amount > 0",
            "message": "Amount must be greater than zero"
        },
        {
            "condition": "p_amount < 1000000",
            "message": "Amount cannot exceed 1000000"
        }
    ]
    
    # Generate Java code
    method_code = PLSQLtoJavaConverter.generate_java_method(
        proc_name="validate_amount",
        logic=logic,
        entity_names={},
        package_name="com.example.demo"
    )
    
    print("Generated Java Method:")
    print("-" * 70)
    print(method_code)
    print("-" * 70)
    print()
    
    # Verify assertions
    checks = [
        {
            "name": "First assertion negation",
            "should_contain": "if (!(amount > 0))",
            "reason": "assert(p_amount > 0) should throw if amount <= 0"
        },
        {
            "name": "Second assertion negation",
            "should_contain": "if (!(amount < 1000000))",
            "reason": "assert(p_amount < 1000000) should throw if amount >= 1000000"
        },
        {
            "name": "Exception thrown",
            "should_contain": "throw new BusinessException",
            "reason": "Should throw BusinessException on validation failure"
        }
    ]
    
    print("VALIDATION CHECKS:")
    print("-" * 70)
    all_passed = True
    for check in checks:
        if check["should_contain"] in method_code:
            print(f"✓ PASS: {check['name']}")
            print(f"  Reason: {check['reason']}")
        else:
            print(f"✗ FAIL: {check['name']}")
            print(f"  Reason: {check['reason']}")
            print(f"  Expected: {check['should_contain']}")
            all_passed = False
        print()
    
    if all_passed:
        print("=" * 70)
        print("ALL TESTS PASSED! Assert negation is working correctly.")
        print("=" * 70)
        return True
    else:
        print("=" * 70)
        print("SOME TESTS FAILED! Fix the assertion logic.")
        print("=" * 70)
        return False

def test_nullable_field_assertion():
    """Test assertion on nullable fields"""
    
    print("\n" * 2)
    print("=" * 70)
    print("TESTING NULLABLE FIELD ASSERTION")
    print("=" * 70)
    print()
    
    from src.generator.improved_plsql_extractor import ExtractedLogic
    
    logic = ExtractedLogic()
    logic.error_assertions = [
        {
            "condition": "p_customer_id IS NOT NULL",
            "message": "Customer ID must be specified"
        }
    ]
    
    method_code = PLSQLtoJavaConverter.generate_java_method(
        proc_name="validate_id",
        logic=logic,
        entity_names={},
        package_name="com.example.demo"
    )
    
    print("Generated Java Method:")
    print("-" * 70)
    print(method_code)
    print("-" * 70)
    print()
    
    # The key check: IS NOT NULL becomes "!= null", then gets negated to "== null"
    if "if (!(customerId != null))" in method_code or "if (customerId == null)" in method_code:
        print("✓ PASS: Nullable assertion correctly negated")
        print("  Expected logic: throw if customerId IS NULL")
        print("  Generated: if (customerId == null) or if (!(customerId != null))")
        return True
    else:
        print("✗ FAIL: Nullable assertion not properly negated")
        print(f"  Method code: {method_code}")
        return False

if __name__ == "__main__":
    try:
        test1_passed = test_assert_negation()
        test2_passed = test_nullable_field_assertion()
        
        if test1_passed and test2_passed:
            print("\n" + "=" * 70)
            print("ALL TESTS PASSED! Assert negation is working correctly.")
            print("=" * 70)
            sys.exit(0)
        else:
            print("\n" + "=" * 70)
            print("SOME TESTS FAILED!")
            print("=" * 70)
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
