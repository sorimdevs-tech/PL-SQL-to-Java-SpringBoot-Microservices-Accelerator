#!/usr/bin/env python3
"""Simulate exact frontend API call flow."""

import sys
import json
import tempfile
from pathlib import Path
sys.path.insert(0, 'src')

from parser.discovery_analyzer import build_discovery_model, analyze_sql_source

sql = '''
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

print("="*80)
print("SIMULATING EXACT FRONTEND API RESPONSE")
print("="*80)

# Step 1: Analyze
print("\nStep 1: analyzeUploadedSqlFile() called")
analyses = analyze_sql_source(sql)
discovery_model = build_discovery_model(sql)

# Step 2: Build response like API does
primary = analyses[0] if analyses else {}
response = {
    **primary,
    "objects": analyses,
    "discovery": discovery_model,
    "count": len(analyses),
    "source": "upload",
}

print(f"Response received with {len(analyses)} procedure(s)")

# Step 3: Frontend extracts globalSchema
print("\nStep 2: Frontend extracts data")
globalSchema = response.get("discovery", {}).get("schema")
print(f"analysis?.discovery?.schema: {type(globalSchema)}")

# Step 4: Frontend displays
print("\nStep 3: Frontend displays GlobalSchemaPanel")
if globalSchema:
    tables = globalSchema.get("tables", [])
    print(f"Tables available: {len(tables)}")
    
    for table in tables:
        print(f"\n{table['name']}:")
        if table.get('foreign_keys'):
            for fk in table['foreign_keys']:
                print(f"  ✓ {table['name']}.{fk['source_column']} → {fk['target_table']}.{fk['target_column']}")
        else:
            print(f"  (no FKs)")

print("\n✅ If this shows correct FKs, then:")
print("  1. Backend is correct")
print("  2. API response is correct")
print("  3. Frontend should display them")
print("\nIf you're NOT seeing them in the frontend:")
print("  → Browser cache? Try incognito mode or clear cache")
print("  → Is backend running? Check port 8001")
print("  → Upload fresh SQL file to trigger new API call")
