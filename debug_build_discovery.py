#!/usr/bin/env python
"""Check how build_discovery_model processes FKs."""

import json
import sys
sys.path.insert(0, "plsql_Acc_backend")

from src.parser.discovery_analyzer import build_discovery_model

sql = """
CREATE OR REPLACE PROCEDURE process_invoice(
    p_customer_id IN NUMBER,
    p_invoice_id IN NUMBER,
    p_vat_code IN VARCHAR2
) AS
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID, VAT_CODE) VALUES (p_invoice_id, p_customer_id, p_vat_code);
    UPDATE XY_CUSTOMER SET status = 'ACTIVE' WHERE customer_id = p_customer_id;
    UPDATE XY_VAT SET vat_rate = 0.15 WHERE vat_code = p_vat_code;
    UPDATE APPL_LOG SET log_status = 'DONE' WHERE log_status != 'DONE';
END;
"""

print("=== CHECKING build_discovery_model OUTPUT ===\n")

result = build_discovery_model(sql)
schema = result['schema']

print(f"Tables: {len(schema['tables'])}")
print(f"Relationships: {len(schema['relationships'])}\n")

for table in schema['tables']:
    print(f"Table: {table['name']}")
    print(f"  Source: {table.get('source', 'unknown')}")
    print(f"  Foreign Keys: {len(table.get('foreign_keys', []))}")
    for fk in table.get('foreign_keys', []):
        print(f"    - {fk['source_column']} → {fk['target_table']}.{fk['target_column']}")
    print()

print("Global Relationships:")
for rel in schema['relationships']:
    print(f"  {rel['source_table']}.{rel['source_column']} → {rel['target_table']}.{rel['target_column']}")
