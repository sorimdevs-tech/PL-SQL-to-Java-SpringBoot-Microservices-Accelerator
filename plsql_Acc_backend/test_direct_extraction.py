#!/usr/bin/env python3
"""Test direct extraction to debug variable naming issues"""

import sys
sys.path.insert(0, 'src')

from generator.improved_plsql_extractor import ImprovedPLSQLExtractor
from generator.plsql_to_java_converter import PLSQLtoJavaConverter

# Sample PL/SQL procedure with assertions
test_proc = """
PROCEDURE create_invoice(p_customer_id NUMBER, p_amount DECIMAL, p_description VARCHAR2, p_vat_code VARCHAR2) IS
BEGIN
  appl_error_pkg.assert(p_customer_id IS NOT NULL, 'Customer ID must be specified!');
  appl_error_pkg.assert(p_amount IS NOT NULL, 'Amount must be specified!');
  appl_error_pkg.assert(p_amount > 0, 'Amount must be greater than zero!');
  
  INSERT INTO invoices (customer_id, amount, description) VALUES (p_customer_id, p_amount, p_description);
END;
"""

print("=" * 80)
print("TEST: Direct Extraction and Translation")
print("=" * 80)

print("\n1. Extracting logic from PL/SQL...")
logic = ImprovedPLSQLExtractor.extract_all_logic(test_proc)

print(f"\nError assertions found: {len(logic.error_assertions)}")
for i, assertion in enumerate(logic.error_assertions):
    print(f"  [{i}] Condition: {assertion['condition']}")
    print(f"      Message: {assertion['message']}")

print("\n2. Testing _translate_plsql_expression...")
test_conditions = [
    "p_customer_id IS NOT NULL",
    "p_amount > 0",
    "p_description IS NULL",
]

for cond in test_conditions:
    translated = PLSQLtoJavaConverter._translate_plsql_expression(cond)
    print(f"  '{cond}' => '{translated}'")

print("\n3. Testing _to_camel_case...")
test_names = [
    "_customer_id",
    "_amount",
    "_description",
    "customer_id",
    "_vat_code",
]

for name in test_names:
    camel = PLSQLtoJavaConverter._to_camel_case(name)
    print(f"  '{name}' => '{camel}'")

print("\n" + "=" * 80)
