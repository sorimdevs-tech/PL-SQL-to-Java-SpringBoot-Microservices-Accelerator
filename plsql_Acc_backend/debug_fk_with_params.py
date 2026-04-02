#!/usr/bin/env python3
"""Debug FK inference with parameters."""

import sys
sys.path.insert(0, 'src')

from parser.discovery_analyzer import build_discovery_model

# Test SQL with parameter threading
test_sql = '''
CREATE OR REPLACE PROCEDURE create_invoice(
    p_invoice_id IN NUMBER,
    p_customer_id IN NUMBER,
    p_vat_code IN VARCHAR2
) IS
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID, VAT_CODE, INVOICE_AMOUNT)
    VALUES (p_invoice_id, p_customer_id, p_vat_code, 100);
END;
/

CREATE TABLE XY_CUSTOMER (
    CUSTOMER_ID NUMBER PRIMARY KEY
);

CREATE TABLE XY_VAT (
    VAT_CODE VARCHAR2(5) PRIMARY KEY
);

CREATE TABLE XY_INVOICE (
    INVOICE_ID NUMBER PRIMARY KEY,
    CUSTOMER_ID NUMBER,
    VAT_CODE VARCHAR2(5),
    INVOICE_AMOUNT NUMBER
);
'''

model = build_discovery_model(test_sql)
tables = model.get("schema", {}).get("tables", [])
print(f'Tables in schema: {len(tables)}')
for t in tables:
    fks = t.get("foreign_keys", [])
    print(f'{t.get("name")} with {len(fks)} FKs:')
    for fk in fks:
        print(f'  {fk["source_column"]} -> {fk["target_table"]}.{fk["target_column"]}')
