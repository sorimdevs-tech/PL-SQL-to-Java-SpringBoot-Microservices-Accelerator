#!/usr/bin/env python
"""Debug FK generation to identify the exact issue."""

import json
import sys
sys.path.insert(0, "plsql_Acc_backend")

from src.parser.discovery_analyzer import infer_tables_from_dml

sql = """
CREATE OR REPLACE PROCEDURE process_invoice(
    p_customer_id IN NUMBER,
    p_invoice_id IN NUMBER
) AS
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID, INVOICE_AMOUNT) VALUES (p_invoice_id, p_customer_id, 100);
    UPDATE XY_CUSTOMER SET status = 'ACTIVE' WHERE customer_id = p_customer_id;
END;
"""

print("=== DEBUGGING DML FK INFERENCE ===\n")

result = infer_tables_from_dml(sql)

print(f"Tables found: {len(result)}\n")

for table in result:
    print(f"Table: {table['name']}")
    print(f"  Columns: {len(table.get('columns', []))}")
    for col in table.get('columns', []):
        print(f"    - {col['name']} ({col['type']})")
    
    print(f"  Foreign Keys: {len(table.get('foreign_keys', []))}")
    for fk in table.get('foreign_keys', []):
        print(f"    - {fk['source_column']} → {fk['target_table']}.{fk['target_column']}")
    print()
