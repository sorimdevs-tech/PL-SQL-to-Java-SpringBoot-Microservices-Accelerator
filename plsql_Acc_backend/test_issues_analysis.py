#!/usr/bin/env python3
"""
Test script to identify and analyze the three remaining issues:
1. Malformed expressions with incomplete parentheses
2. Complex validation conditions with field access not camelCased
3. Parameter/return type inference for complex scenarios
"""

import sys
sys.path.insert(0, 'src')

from generator.plsql_to_java_converter import PLSQLtoJavaConverter
from generator.improved_plsql_extractor import ImprovedPLSQLExtractor, ExtractedLogic

print("=" * 80)
print("ISSUE 1: Malformed expressions with incomplete parentheses")
print("=" * 80)

# Test cases for incomplete/malformed parentheses
test_expressions_1 = [
    "NVL(NVL(p_status, 'ACTIVE'), 'DEFAULT')",  # Nested NVL
    "COALESCE(p_desc, invoice_pkg.get_desc(p_id, 'test'), 'default')",  # Nested with string
    "CASE WHEN p_status = 'A' THEN (p_amount * 1.1) ELSE (p_amount * 0.9) END",  # Nested parens in CASE
    "NVL(customer.cust_code, NVL(p_backup_code, 'N/A'))",  # Field access + nested
]

print("\nTesting expression translation:")
for expr in test_expressions_1:
    result = PLSQLtoJavaConverter._translate_plsql_expression(expr)
    balanced = PLSQLtoJavaConverter._is_balanced_parens(result)
    status = "OK" if balanced else "MALFORMED"
    print(f"\nInput:  {expr}")
    print(f"Output: {result}")
    print(f"Status: {status}")

print("\n" + "=" * 80)
print("ISSUE 2: Complex validation conditions with field access")
print("=" * 80)

# Test cases for field access in conditions
test_conditions = [
    "p_customer IS NOT NULL AND p_customer.customer_id > 0",
    "p_invoice.invoice_status = 'PENDING' OR p_invoice.amount IS NULL",
    "l_customer.cust_code IS NOT NULL AND l_customer.status = 'ACTIVE'",
    "customer.customer_id != null and customer.customer_status = 'APPROVED'",
]

print("\nTesting field access in conditions:")
for cond in test_conditions:
    result = PLSQLtoJavaConverter._translate_plsql_expression(cond)
    has_getter = "get" in result or "()" in result
    status = "OK - HAS GETTER" if has_getter else "MISSING GETTER"
    print(f"\nInput:  {cond}")
    print(f"Output: {result}")
    print(f"Status: {status}")

print("\n" + "=" * 80)
print("ISSUE 3: Parameter/return type inference for complex scenarios")
print("=" * 80)

# Test cases for type inference
test_params = [
    ('customers', 'List'),
    ('customer_ids', 'List'),
    ('page_size', 'Integer'),
    ('status_list', 'List'),
    ('optional_amount', 'Optional'),
    ('amount_map', 'Map'),
    ('active_customers', 'List'),
    ('is_active', 'boolean'),
    ('customer_id', 'Long'),
    ('invoice_amount', 'BigDecimal'),
    ('transaction_date', 'LocalDateTime'),
]

print("\nTesting parameter type inference:")
for param, expected in test_params:
    inferred = PLSQLtoJavaConverter._infer_parameter_type(param)
    match = expected in inferred
    status = "PASS" if match else "FAIL"
    print(f"\n{param:20s} Expected: {expected:15s}  Inferred: {inferred:25s}  [{status}]")

