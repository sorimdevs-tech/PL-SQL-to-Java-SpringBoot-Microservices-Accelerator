#!/usr/bin/env python3
"""Simulate actual API response to frontend."""

import sys
import json
sys.path.insert(0, 'src')

from parser.discovery_analyzer import build_discovery_model

# Real SQL from screenshots
test_sql = '''
CREATE TABLE APPL_LOG (
    LOG_DATE DATE,
    LOG_STATUS VARCHAR2(50),
    LOG_TEXT VARCHAR2(1000)
);

CREATE TABLE XY_CUSTOMER (
    CUSTOMER_ID NUMBER PRIMARY KEY,
    CUSTOMER_NAME VARCHAR2(100),
    LAST_ACTIVE_DATE DATE
);

CREATE TABLE XY_INVOICE (
    INVOICE_ID NUMBER PRIMARY KEY,
    INVOICE_AMOUNT NUMBER,
    INVOICE_DESCRIPTION VARCHAR2(200),
    INVOICE_STATUS VARCHAR2(20),
    CUSTOMER_ID NUMBER,
    VAT_CODE VARCHAR2(5)
);

CREATE TABLE XY_VAT (
    VAT_CODE VARCHAR2(5) PRIMARY KEY,
    VAT_RATE NUMBER
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

print("=" * 80)
print("ACTUAL API RESPONSE (schema.tables)")
print("=" * 80)

for table in model.get('schema', {}).get('tables', []):
    name = table.get('name')
    print(f"\n{name}:")
    print(f"  foreign_keys: {json.dumps(table.get('foreign_keys', []), indent=4)}")

print("\n" + "=" * 80)
print("WHAT FRONTEND WILL DISPLAY PER TABLE:")
print("=" * 80)

for table in model.get('schema', {}).get('tables', []):
    name = table.get('name')
    fks = table.get('foreign_keys', [])
    print(f"\nWhen user clicks on {name}:")
    if fks:
        for fk in fks:
            # This is what the frontend code does (from step-panels.tsx line 514)
            display = f"{name}.{fk['source_column']} -> {fk['target_table']}.{fk['target_column']}"
            print(f"  Shows: {display}")
    else:
        print(f"  Shows: No foreign keys detected")
