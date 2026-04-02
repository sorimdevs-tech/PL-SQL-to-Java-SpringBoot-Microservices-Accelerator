#!/usr/bin/env python3
"""Check full API response comprehensively."""

import sys
import json
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

CREATE OR REPLACE PROCEDURE create_invoice(
    p_invoice_id IN NUMBER,
    p_customer_id IN NUMBER,
    p_vat_code IN VARCHAR2,
    p_amount IN NUMBER
) IS
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

analyses = analyze_sql_source(sql)
discovery_model = build_discovery_model(sql)

print("="*80)
print("COMPREHENSIVE API RESPONSE CHECK")
print("="*80)

primary = analyses[0] if analyses else {}

response = {
    **primary,
    "objects": analyses,
    "discovery": discovery_model,
    "count": len(analyses),
    "source": "upload",
}

print("\n1. GLOBAL SCHEMA (discovery.schema):")
print("-"*80)
tables = response.get("discovery", {}).get("schema", {}).get("tables", [])
relationships = response.get("discovery", {}).get("schema", {}).get("relationships", [])

print(f"\nTables ({len(tables)}):")
for table in tables:
    fks = table.get("foreign_keys", [])
    print(f"  {table['name']}: {len(fks)} FKs")
    for fk in fks:
        print(f"    • {fk['source_column']} → {fk['target_table']}.{fk['target_column']}")

print(f"\nGlobal Relationships ({len(relationships)}):")
for rel in relationships:
    print(f"  • {rel['source_table']}.{rel['source_column']} → {rel['target_table']}.{rel['target_column']}")

print("\n2. PER-PROCEDURE TABLE DETAILS (primary.tableDetails):")
print("-"*80)
table_details = response.get("tableDetails", {"tables": [], "relationships": []})
proc_tables = table_details.get("tables", [])
proc_rels = table_details.get("relationships", [])

print(f"\nProcedure-related tables ({len(proc_tables)}):")
for table in proc_tables:
    fks = table.get("foreign_keys", [])
    print(f"  {table['name']}: {len(fks)} FKs")
    for fk in fks:
        print(f"    • {fk['source_column']} → {fk['target_table']}.{fk['target_column']}")

print(f"\nProcedure-related relationships ({len(proc_rels)}):")
for rel in proc_rels:
    print(f"  • {rel.get('source_table', rel.get('fromTable'))}.{rel.get('source_column', rel.get('fromColumn'))} → {rel.get('target_table', rel.get('toTable'))}.{rel.get('target_column', rel.get('toColumn'))}")

print("\n3. WHAT FRONTEND USES:")
print("-"*80)
print(f"GlobalSchemaPanel uses: analysis?.discovery?.schema")
print(f"  → Should show {len(tables)} tables with FKs from discovery.schema.tables")
print(f"\nProcedureBehaviorPanel uses: activeAnalysis.tableDetails")
print(f"  → Should show {len(proc_tables)} tables in procedures")

print("\n4. EXPECTED DISPLAY IN GLOBALSCHEMAAPANEL:")
print("-"*80)
xy_inv = next((t for t in tables if t['name'] == 'XY_INVOICE'), None)
if xy_inv:
    print(f"When user clicks XY_INVOICE:")
    for fk in xy_inv.get('foreign_keys', []):
        print(f"  {xy_inv['name']}.{fk['source_column']} → {fk['target_table']}.{fk['target_column']}")
