#!/usr/bin/env python3
"""Check actual API response format."""

import sys
import json
sys.path.insert(0, 'src')

from parser.discovery_analyzer import build_discovery_model

test_sql = '''
CREATE TABLE XY_CUSTOMER (
    CUSTOMER_ID NUMBER PRIMARY KEY,
    CUSTOMER_NAME VARCHAR2(100),
    LAST_ACTIVE_DATE DATE
);

CREATE TABLE XY_VAT (
    VAT_CODE VARCHAR2(5) PRIMARY KEY,
    VAT_RATE NUMBER
);

CREATE TABLE XY_INVOICE (
    INVOICE_ID NUMBER PRIMARY KEY,
    INVOICE_AMOUNT NUMBER,
    INVOICE_DESCRIPTION VARCHAR2(200),
    INVOICE_STATUS VARCHAR2(20),
    CUSTOMER_ID NUMBER,
    VAT_CODE VARCHAR2(5)
);

CREATE TABLE APPL_LOG (
    LOG_DATE DATE,
    LOG_STATUS VARCHAR2(50),
    LOG_TEXT VARCHAR2(1000)
);

DECLARE
    p_customer_id IN NUMBER;
    p_vat_code IN VARCHAR2;
    p_invoice_id IN NUMBER;
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID, VAT_CODE, INVOICE_AMOUNT)
    VALUES (p_invoice_id, p_customer_id, p_vat_code, 100);
END;
/
'''

model = build_discovery_model(test_sql)

print("CHECKING RAW API RESPONSE")
print("=" * 80)

# This is what gets returned to frontend
schema = model.get("schema", {})
tables = schema.get("tables", [])

print("\nTables and their foreign_keys arrays:")
for table in tables:
    print(f"\n{table.get('name')}:")
    fks = table.get('foreign_keys', [])
    print(f"  foreign_keys: {json.dumps(fks, indent=4)}")

print("\n\nFull schema structure being sent to frontend:")
print(json.dumps({"schema": schema}, indent=2))
