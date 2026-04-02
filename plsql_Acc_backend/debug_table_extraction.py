#!/usr/bin/env python3
"""Debug table extraction."""

import sys
sys.path.insert(0, 'src')

from parser.discovery_analyzer import infer_tables_from_dml, _extract_table_definitions

test_sql = '''
CREATE TABLE XY_CUSTOMER (
    CUSTOMER_ID NUMBER PRIMARY KEY
);

CREATE TABLE XY_INVOICE (
    INVOICE_ID NUMBER PRIMARY KEY,
    CUSTOMER_ID NUMBER
);

DECLARE
    p_cust_id NUMBER;
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID) VALUES (1, p_cust_id);
END;
/
'''

ddl_tables = _extract_table_definitions(test_sql)
print(f'DDL tables found: {len(ddl_tables)}')
for t in ddl_tables:
    print(f'  {t.get("name")}')

infer_tables = infer_tables_from_dml(test_sql)
print(f'Inferred tables found: {len(infer_tables)}')
for t in infer_tables:
    print(f'  {t.get("name")} with {len(t.get("foreign_keys", []))} FKs')

print("\nbuild_discovery_model behavior:")
from parser.discovery_analyzer import build_discovery_model

model = build_discovery_model(test_sql)
tables = model.get("schema", {}).get("tables", [])
print(f'Tables in schema: {len(tables)}')
for t in tables:
    print(f'  {t.get("name")} with {len(t.get("foreign_keys", []))} FKs')
