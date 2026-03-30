#!/usr/bin/env python3
"""Debug script to capture what generate_java_method actually produces"""

import sys
import json
sys.path.insert(0, 'src')

from generator.improved_plsql_extractor import ImprovedPLSQLExtractor
from generator.plsql_to_java_converter import PLSQLtoJavaConverter

# Real PL/SQL from the mortenbra repo (simplified)
test_proc_body = """
PROCEDURE create_invoice(p_customer_id NUMBER, p_amount DECIMAL, p_description VARCHAR2, p_vat_code VARCHAR2) IS
  l_customer  customer_pkg.customer_type;
  l_description VARCHAR2(500);
  l_vat_amount DECIMAL;
  l_returnvalue NUMBER;
BEGIN
  appl_error_pkg.assert(p_customer_id IS NOT NULL, 'Customer ID must be specified!');
  appl_error_pkg.assert(p_amount IS NOT NULL, 'Amount must be specified!');
  appl_error_pkg.assert(p_amount > 0, 'Amount must be greater than zero!');  
  
  l_customer := customer_pkg.get_customer(p_customer_id);
  appl_error_pkg.assert(l_customer IS NOT NULL, 'Customer not found!');
  appl_error_pkg.assert(l_customer.customer_status = customer_pkg.c_status_active, 'Customer not active!');
  
  l_description := COALESCE(p_description, invoice_pkg.get_default_invoice_description(invoice_pkg.c_type_standard), 'Untitled');
  l_vat_amount := NVL(invoice_pkg.get_vat_amount(p_amount, p_vat_code), 0);
  
  l_returnvalue := invoice_pkg.new_invoice(
    p_customer_id => p_customer_id,
    p_amount => p_amount,
    p_vat_amount => l_vat_amount,
    p_description => l_description
  );
  
  appl_error_pkg.assert(l_returnvalue IS NOT NULL, 'Failed to create invoice!');
  
  appl_log_pkg.log('Creating new invoice for customer ' || p_customer_id);
END;
"""

print("=" * 100)
print("EXTRACTING AND GENERATING METHOD")
print("=" * 100)

# Extract logic
logic = ImprovedPLSQLExtractor.extract_all_logic(test_proc_body)

print("\nExtracted Logic:")
print(f"  Error assertions: {len(logic.error_assertions)}")
for i, ea in enumerate(logic.error_assertions):
    print(f"    [{i}] {ea}")
print(f"  Function calls: {len(logic.function_calls)}")
for i, fc in enumerate(logic.function_calls):
    print(f"    [{i}] {fc}")
print(f"  Derived values: {len(logic.derived_values)}")
for i, dv in enumerate(logic.derived_values):
    print(f"    [{i}] {dv}")
print(f"  Logging calls: {len(logic.logging_calls)}")
for i, lc in enumerate(logic.logging_calls):
    print(f"    [{i}] {lc}")

# Generate method
print("\nGenerating Java method...")
method = PLSQLtoJavaConverter.generate_java_method(
    proc_name="create_invoice",
    logic=logic,
    entity_names={'invoice': 'invoiceTable', 'customer': 'customerTable'},
    package_name="com.example.service"
)

print("\nGenerated Method:")
print("=" * 100)
print(method)
print("=" * 100)
