#!/usr/bin/env python3
"""Test what the API actually returns for FKs."""

import sys
import json
sys.path.insert(0, 'plsql_Acc_backend/src')

from parser.discovery_analyzer import build_discovery_model

# Test SQL with multiple FKs
test_sql = """
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
    l_cust_id NUMBER;
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID, VAT_CODE, INVOICE_AMOUNT)
    VALUES (1, l_cust_id, 'VAT1', 100);
    
    UPDATE XY_INVOICE SET CUSTOMER_ID = 2, VAT_CODE = 'VAT2' WHERE INVOICE_ID = 1;
END;
/
"""

print("=" * 60)
print("TESTING API RESPONSE FORMAT FOR FKs")
print("=" * 60)

model = build_discovery_model(test_sql)

print("\n1. SCHEMA TABLES (as returned in model):")
print("-" * 60)
for table in model.get("schema", {}).get("tables", []):
    table_name = table.get("name")
    fks = table.get("foreign_keys", [])
    print(f"\n{table_name}:")
    print(f"  Columns: {[c.get('name') for c in table.get('columns', [])]}")
    print(f"  Foreign Keys ({len(fks)}):")
    for fk in fks:
        print(f"    {json.dumps(fk, indent=6)}")
    if not fks:
        print(f"    (none)")

print("\n2. SCHEMA RELATIONSHIPS (global):")
print("-" * 60)
relationships = model.get("schema", {}).get("relationships", [])
print(f"Total: {len(relationships)}")
for rel in relationships:
    print(f"  {json.dumps(rel, indent=4)}")

print("\n3. WHAT SHOULD FRONTEND RECEIVE:")
print("-" * 60)
print("For each table with FKs, the frontend should see in its properties:")
for table in model.get("schema", {}).get("tables", []):
    table_name = table.get("name")
    fks = table.get("foreign_keys", [])
    if fks:
        print(f"\n{table_name}.foreign_keys = [")
        for fk in fks:
            print(f"  {json.dumps(fk)},")
        print("]")

print("\n" + "=" * 60)
