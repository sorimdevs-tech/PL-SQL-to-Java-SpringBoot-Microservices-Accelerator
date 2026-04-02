#!/usr/bin/env python3
"""Check exact FK structure in table.foreign_keys."""

import sys
import json
sys.path.insert(0, 'src')

from parser.discovery_analyzer import _analyze_procedure_block, _extract_table_definitions, build_discovery_model, _prepare_sql_text, ObjectSlice

sql = '''
CREATE TABLE XY_CUSTOMER (
    CUSTOMER_ID NUMBER PRIMARY KEY
);

CREATE TABLE XY_INVOICE (
    INVOICE_ID NUMBER PRIMARY KEY,
    CUSTOMER_ID NUMBER
);

CREATE OR REPLACE PROCEDURE create_invoice(
    p_invoice_id IN NUMBER,
    p_customer_id IN NUMBER
) IS
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID)
    VALUES (p_invoice_id, p_customer_id);
END;
/
'''

cleaned = _prepare_sql_text(sql)
table_defs = _extract_table_definitions(cleaned)

print("Direct table_defs from _extract_table_definitions:")
for table in table_defs:
    print(f"\n{table['name']}.foreign_keys array:")
    print(json.dumps(table.get('foreign_keys', []), indent=2))

print("\n\n" + "="*80)
print("build_discovery_model response:")
print("="*80)

model = build_discovery_model(sql)
for table in model.get('schema', {}).get('tables', []):
    print(f"\n{table['name']}.foreign_keys array:")
    print(json.dumps(table.get('foreign_keys', []), indent=2))

print("\n\nFull table struct for XY_INVOICE:")
xy_inv = next((t for t in model.get('schema', {}).get('tables', []) if t['name'] == 'XY_INVOICE'), None)
if xy_inv:
    print(json.dumps(xy_inv, indent=2))
