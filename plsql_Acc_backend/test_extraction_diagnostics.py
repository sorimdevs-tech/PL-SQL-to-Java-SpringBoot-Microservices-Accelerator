#!/usr/bin/env python3
"""Diagnostic script to check what's being extracted from PL/SQL procedures."""

from src.generator.improved_plsql_extractor import ImprovedPLSQLExtractor
from src.generator.plsql_to_java_converter import PLSQLtoJavaConverter

# Test case 1: Simple validation that should NOT throw (IS NULL check)
test1_plsql = """
PROCEDURE test_validate (p_customer_id IN NUMBER) AS
BEGIN
  IF p_customer_id IS NULL THEN
    RAISE_APPLICATION_ERROR(-20001, 'Customer ID required');
  END IF;
END test_validate;
"""

# Test case 2: Validation with IS NOT NULL (inverted)  
test2_plsql = """
PROCEDURE test_validate2 (p_amount IN NUMBER) AS
BEGIN
  IF p_amount IS NOT NULL THEN
    RAISE_APPLICATION_ERROR(-20002, 'Amount should not be provided');
  END IF;
END test_validate2;
"""

# Test case 3: Derived from actual create_invoice logic
test3_plsql = """
PROCEDURE create_invoice (p_customer_id IN NUMBER, p_amount IN NUMBER) AS
BEGIN
  IF p_customer_id IS NULL THEN
    RAISE_APPLICATION_ERROR(-20001, 'Customer must be specified!');
  END IF;
  IF p_amount IS NULL THEN
    RAISE_APPLICATION_ERROR(-20002, 'Amount must be specified!');
  END IF;
  IF p_amount <= 0 THEN
    RAISE_APPLICATION_ERROR(-20003, 'Amount must be greater than zero!');
  END IF;
END create_invoice;
"""

print("=" * 70)
print("TEST 1: IS NULL check (should throw when null)")
print("=" * 70)
logic1 = ImprovedPLSQLExtractor.extract_all_logic(test1_plsql)
print(f"Extracted validations: {len(logic1.validations)}")
for v in logic1.validations:
    print(f"  Condition: {v['condition']}")
    print(f"  Error Code: {v['error_code']}")
    print(f"  Message: {v['message']}")
    
    # Translate it
    java_expr = PLSQLtoJavaConverter._translate_plsql_expression(v['condition'])
    print(f"  Java Translated: {java_expr}")
    print()

print("=" * 70)
print("TEST 3: Multiple validations from create_invoice")
print("=" * 70)
logic3 = ImprovedPLSQLExtractor.extract_all_logic(test3_plsql)
print(f"Extracted validations: {len(logic3.validations)}")
for i, v in enumerate(logic3.validations, 1):
    print(f"\nValidation {i}:")
    print(f"  Condition: {v['condition']}")
    print(f"  Error Code: {v['error_code']}")
    print(f"  Message: {v['message']}")
    
    java_expr = PLSQLtoJavaConverter._translate_plsql_expression(v['condition'])
    print(f"  Java Translated: {java_expr}")
    print(f"  Java Code Generated:")
    print(f"    if ({java_expr}) {{")
    print(f'      throw new BusinessException("-{v["error_code"]}", "{v["message"]}");')
    print(f"    }}")
