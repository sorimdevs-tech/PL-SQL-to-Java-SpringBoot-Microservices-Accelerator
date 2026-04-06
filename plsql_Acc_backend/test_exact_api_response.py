#!/usr/bin/env python3
"""Simulate exact frontend API call."""

import sys
import json
sys.path.insert(0, 'src')

from parser.discovery_analyzer import build_discovery_model, analyze_sql_source
from pathlib import Path

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
    p_customer_id IN NUMBER;
    p_vat_code IN VARCHAR2;
    p_invoice_id IN NUMBER;
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID, VAT_CODE, INVOICE_AMOUNT)
    VALUES (p_invoice_id, p_customer_id, p_vat_code, 100);
END;
/
'''

# This is what the API does
analyses = analyze_sql_source(sql)
discovery_model = build_discovery_model(sql)

print("="*80)
print("API RESPONSE STRUCTURE")
print("="*80)

# Build response like the API does
primary = analyses[0] if analyses else {
    "procedureName": "",
    "objectType": "",
    "parameters": {"in": [], "out": []},
    "tablesUsed": [],
    "operations": [],
    "operationsByTable": {},
    "localVariables": [],
    "exceptions": [],
    "businessRules": [],
    "dataFlow": [],
    "complexity": {},
    "dependencyGraph": {"tablesUsed": [], "proceduresCalled": []},
    "tableDetails": {"tables": [], "relationships": []},
    "conversionPreview": {"entities": [], "repositories": [], "services": [], "controllers": [], "dtos": []},
}

response = {
    **primary,
    "objects": analyses,
    "discovery": discovery_model,
    "count": len(analyses),
    "source": "upload",
}

print("\nFull response structure keys:")
print(list(response.keys()))

print("\n\nresponse.discovery.schema.tables structure:")
for table in response.get("discovery", {}).get("schema", {}).get("tables", []):
    print(f"\n{table['name']}:")
    print(f"  foreign_keys: {json.dumps(table.get('foreign_keys', []), indent=4)}")

print("\n\nresponse.discovery.schema.relationships:")
print(json.dumps(response.get("discovery", {}).get("schema", {}).get("relationships", []), indent=2))

print("\n\nWhat frontend accesses for GlobalSchemaPanel:")
print(f"analysis?.discovery?.schema  = {type(response.get('discovery', {}).get('schema'))}")
print(f"analysis?.discovery?.schema?.tables = {len(response.get('discovery', {}).get('schema', {}).get('tables', []))} tables")
print(f"analysis?.discovery?.schema?.relationships = {len(response.get('discovery', {}).get('schema', {}).get('relationships', []))} relationships")
