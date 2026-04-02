#!/usr/bin/env python3
"""Test the actual POST /api/discovery/analyze endpoint response."""

import requests
import json
import sys
sys.path.insert(0, 'src')

# Create a test file to upload
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
    p_invoice_id IN NUMBER;
    p_customer_id IN NUMBER;
    p_vat_code IN VARCHAR2;
    p_amount IN NUMBER;
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID, VAT_CODE, INVOICE_AMOUNT)
    VALUES (p_invoice_id, p_customer_id, p_vat_code, p_amount);
    
    UPDATE XY_INVOICE SET 
        CUSTOMER_ID = p_customer_id,
        VAT_CODE = p_vat_code
    WHERE INVOICE_ID = p_invoice_id;
END;
/
'''

print("=" * 80)
print("TESTING ACTUAL API ENDPOINT")
print("=" * 80)

try:
    # First test: call analyze with direct sql_text
    print("\nTest 1: Direct /api/discovery/analyze call")
    response = requests.post(
        "http://127.0.0.1:8000/api/discovery/analyze",
        json={"sql_text": test_sql},
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"✓ API returned 200 OK")
        print(f"\nResponse structure:")
        print(f"  Keys: {list(data.keys())}")
        
        # Check discovery.schema
        discovery = data.get("discovery", {})
        schema = discovery.get("schema", {})
        tables = schema.get("tables", [])
        relationships = schema.get("relationships", [])
        
        print(f"\n✓ discovery.schema structure:")
        print(f"  Tables: {len(tables)}")
        print(f"  Relationships: {len(relationships)}")
        
        print(f"\n✓ Foreign Keys in each table:")
        for table in tables:
            fks = table.get("foreign_keys", [])
            print(f"\n  {table['name']}:")
            if fks:
                for fk in fks:
                    print(f"    • {fk['source_column']} → {fk['target_table']}.{fk['target_column']}")
            else:
                print(f"    • (none)")
        
        print(f"\n✓ Global Relationships:")
        for rel in relationships:
            print(f"  • {rel['source_table']}.{rel['source_column']} → {rel['target_table']}.{rel['target_column']}")
        
        # Check specific table
        xy_inv = next((t for t in tables if t['name'] == 'XY_INVOICE'), None)
        if xy_inv and xy_inv.get('foreign_keys'):
            print(f"\n✅ SUCCESS: XY_INVOICE has {len(xy_inv['foreign_keys'])} FKs")
            print("Frontend GlobalSchemaPanel should display these FKs")
        else:
            print(f"\n❌ PROBLEM: XY_INVOICE missing expected FKs")
            
    else:
        print(f"✗ API returned {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"✗ Error: {e}")
    print("Make sure backend is running on http://127.0.0.1:8000")
