#!/usr/bin/env python3
"""Test improved extraction with error_assertions and function_calls"""
import sys
sys.path.insert(0, 'src')

from src.generator.improved_plsql_extractor import ImprovedPLSQLExtractor
from src.generator.plsql_to_java_converter import PLSQLtoJavaConverter

# Test PL/SQL from invoice_api_pkg.create_invoice
plsql = """
BEGIN
  -- 1) validate inputs
  appl_error_pkg.assert (p_customer_id is not null, 'Customer ID must be specified!');
  appl_error_pkg.assert (p_amount is not null, 'Amount must be specified!');
  appl_error_pkg.assert (p_amount > 0, 'Amount must be greater than zero!');
  
  l_customer := customer_pkg.get_customer (p_customer_id);
  
  appl_error_pkg.assert (l_customer.customer_id is not null, 'Customer not found!');
  
  -- 2) do calculations and derive values
  l_description := coalesce (p_description, invoice_pkg.get_default_invoice_description (invoice_pkg.c_type_standard), 'Untitled');
  
  if p_vat_code is not null then
    l_vat_amount := nvl (invoice_pkg.get_vat_amount (p_amount, p_vat_code), 0);
  else
    l_vat_amount := 0;
  end if;
  
  -- 3) perform main task
  l_returnvalue := invoice_pkg.new_invoice (
    p_customer_id => p_customer_id,
    p_amount => p_amount,
    p_vat_amount => l_vat_amount,
    p_invoice_description => p_description
  );
  
  appl_error_pkg.assert (l_returnvalue is not null, 'Failed to create invoice!');
  
  RETURN l_returnvalue;
END;
"""

print("=" * 60)
print("TESTING IMPROVED EXTRACTION")
print("=" * 60)

# Extract logic
logic = ImprovedPLSQLExtractor.extract_all_logic(plsql)

print("\n[EXTRACTION RESULTS]")
print(f"Error Assertions: {len(logic.error_assertions)}")
for ea in logic.error_assertions:
    print(f"  - {ea['condition']} => {ea['message']}")

print(f"\nFunction Calls: {len(logic.function_calls)}")
for fc in logic.function_calls[:3]:
    print(f"  - {fc['package']}.{fc['function']}({fc['params']})")

print(f"\nDerived Values: {len(logic.derived_values)}")
for dv in logic.derived_values[:3]:
    print(f"  - {dv['variable']} ({dv['type']})")

print(f"\nReturns: {logic.returns}")

# Generate Java method
print("\n" + "=" * 60)
print("GENERATED JAVA METHOD")
print("=" * 60)

java_method = PLSQLtoJavaConverter.generate_java_method(
    proc_name='create_invoice',
    logic=logic,
    entity_names={},
    package_name='com.example.demo'
)

print(java_method)
