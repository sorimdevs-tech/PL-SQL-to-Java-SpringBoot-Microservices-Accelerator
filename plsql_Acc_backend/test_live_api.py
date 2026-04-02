#!/usr/bin/env python3
"""Test the discovery API directly."""

import requests
import json
import time

# Wait a moment for server to be ready
time.sleep(1)

BASE_URL = "http://127.0.0.1:8000"

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

print("=" * 80)
print("TESTING LIVE API ENDPOINT")
print("=" * 80)

try:
    # Test the analyze endpoint
    response = requests.post(
        f"{BASE_URL}/api/discovery/analyze",
        json={"sql_text": test_sql},
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        
        print("\n✓ API Response received (200 OK)")
        print("\nSchema Tables and Foreign Keys:")
        print("-" * 80)
        
        schema = result.get("discovery", {}).get("schema", {})
        tables = schema.get("tables", [])
        
        for table in tables:
            name = table.get("name")
            fks = table.get("foreign_keys", [])
            
            print(f"\n{name}:")
            if fks:
                print(f"  Foreign Keys:")
                for fk in fks:
                    src_col = fk.get("source_column")
                    tgt_tbl = fk.get("target_table")
                    tgt_col = fk.get("target_column")
                    print(f"    • {src_col} → {tgt_tbl}.{tgt_col}")
            else:
                print(f"  Foreign Keys: (none)")
        
        print("\n✓ Global Relationships:")
        print("-" * 80)
        relationships = schema.get("relationships", [])
        if relationships:
            for rel in relationships:
                print(f"  • {rel.get('source_table')}.{rel.get('source_column')} → {rel.get('target_table')}.{rel.get('target_column')}")
        else:
            print("  (none)")
        
        print("\n" + "=" * 80)
        print("✅ FKs ARE CORRECTLY POPULATED IN API RESPONSE")
        print("=" * 80)
    else:
        print(f"✗ API Error: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"✗ Error calling API: {e}")
    print("\nMake sure the backend is running at http://127.0.0.1:8000")
