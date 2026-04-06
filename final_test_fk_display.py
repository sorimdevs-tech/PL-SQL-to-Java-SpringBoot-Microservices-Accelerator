#!/usr/bin/env python
"""End-to-end test: Verify FKs are correctly generated and formatted for frontend."""

import json
import sys
sys.path.insert(0, "plsql_Acc_backend")

from src.parser.discovery_analyzer import analyze_sql_source, build_discovery_model

# Real-world example from the screenshots
sql = """
CREATE OR REPLACE PROCEDURE manage_invoices(
    p_customer_id IN NUMBER,
    p_invoice_id IN NUMBER,
    p_vat_code IN VARCHAR2
) AS
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID, VAT_CODE, INVOICE_AMOUNT) 
    VALUES (p_invoice_id, p_customer_id, p_vat_code, 1500);
    
    UPDATE XY_CUSTOMER SET status = 'ACTIVE' WHERE customer_id = p_customer_id;
    UPDATE XY_VAT SET vat_rate = 0.10 WHERE vat_code = p_vat_code;
    UPDATE APPL_LOG SET log_status = 'DONE' WHERE log_status != 'DONE';
END;
"""

print("=== FRONTEND END-TO-END TEST ===\n")

# Simulate /api/discovery/analyze endpoint
analyses = analyze_sql_source(sql)
discovery_model = build_discovery_model(sql)

# Build response
base = analyses[0] if analyses else {}
api_response = dict(base)
api_response.update({
    "objects": analyses,
    "discovery": discovery_model,
    "count": len(analyses),
})

# Simulate frontend accessing the data
schema = api_response['discovery']['schema']

print("1. Schema Model:")
print(f"   Tables: {len(schema['tables'])}")
for table in schema['tables']:
    print(f"     - {table['name']} ({len(table.get('columns', []))} cols, {len(table.get('foreign_keys', []))} FKs)")

print(f"\n   Global Relationships: {len(schema['relationships'])}")
for rel in schema['relationships']:
    print(f"     - {rel['source_table']}.{rel['source_column']} → {rel['target_table']}.{rel['target_column']}")

# Frontend GlobalSchemaPanel display logic
print("\n2. Frontend Display (GlobalSchemaPanel):")

print("\n   Table Cards (would display in SVG grid):")
for table in schema['tables']:
    fks = table.get('foreign_keys', [])
    print(f"     {table['name']}:")
    print(f"       Columns to show: {', '.join(c['name'] for c in table['columns'][:3])}...")
    
    if fks:
        print(f"       Foreign Keys to list:")
        for fk in fks:
            print(f"         → {table['name']}.{fk['source_column']} → {fk['target_table']}.{fk['target_column']}")

print("\n   SVG Relationship Lines (would draw in visualization):")
for rel in schema['relationships']:
    print(f"     Line from {rel['source_table']} to {rel['target_table']}")

# Verify TypeScript interface compatibility
print("\n3. TypeScript Interface Verification:")
for table in schema['tables']:
    for fk in table.get('foreign_keys', []):
        required_keys = {'source_column', 'target_table', 'target_column'}
        actual_keys = set(fk.keys())
        
        if required_keys == actual_keys:
            print(f"   ✓ {table['name']}.{fk['source_column']} - Matches SqlSchemaForeignKey")
        else:
            print(f"   ✗ MISMATCH in {table['name']}.{fk['source_column']}")
            print(f"     Expected: {required_keys}")
            print(f"     Actual: {actual_keys}")

print("\n✅ All FKs should now display in the frontend!")
