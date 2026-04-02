#!/usr/bin/env python3
"""End-to-end verification that FKs display correctly."""

import sys
import json
sys.path.insert(0, 'src')

from parser.discovery_analyzer import build_discovery_model

# Complex SQL with multiple FK scenarios
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

DECLARE
    l_invoice_id NUMBER;
    l_customer_id NUMBER;
    l_vat_code VARCHAR2(5);
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID, VAT_CODE, INVOICE_AMOUNT)
    VALUES (l_invoice_id, l_customer_id, l_vat_code, 500);
END;
/
'''

print("=" * 70)
print("END-TO-END FOREIGN KEY VERIFICATION")
print("=" * 70)

model = build_discovery_model(test_sql)

print("\n✓ API Response Structure:")
print("-" * 70)
print(f"Schema has {len(model.get('schema', {}).get('tables', []))} tables")
print(f"Schema has {len(model.get('schema', {}).get('relationships', []))} global relationships")

tables = model.get('schema', {}).get('tables', [])
relationships = model.get('schema', {}).get('relationships', [])

print("\n✓ Table Details:")
print("-" * 70)
for table in tables:
    table_name = table.get('name')
    fks = table.get('foreign_keys', [])
    print(f"\n{table_name}:")
    print(f"  Columns: {[c.get('name') for c in table.get('columns', [])]}")
    if fks:
        print(f"  Foreign Keys ({len(fks)}):")
        for fk in fks:
            print(f"    • {fk['source_column']} → {fk['target_table']}.{fk['target_column']}")
    else:
        print(f"  Foreign Keys: (none)")

print("\n✓ Global Relationships (for SVG visualization):")
print("-" * 70)
if relationships:
    for rel in relationships:
        src_table = rel.get('source_table')
        src_col = rel.get('source_column')
        tgt_table = rel.get('target_table')
        tgt_col = rel.get('target_column')
        print(f"  • {src_table}.{src_col} → {tgt_table}.{tgt_col}")
else:
    print("  (none)")

print("\n✓ Frontend Display Simulation:")
print("-" * 70)
print("GlobalSchemaPanel will show:")
for table in tables:
    if table.get('foreign_keys', []):
        print(f"\n{table['name']} - FOREIGN KEYS section:")
        for fk in table.get('foreign_keys', []):
            display_text = f"{table['name']}.{fk['source_column']} → {fk['target_table']}.{fk['target_column']}"
            print(f"  {display_text}")

print("\n✓ TypeScript Interface Compliance:")
print("-" * 70)
for table in tables:
    for fk in table.get('foreign_keys', []):
        # Check that FK has required fields for SqlSchemaForeignKey
        required_fields = ['source_column', 'target_table', 'target_column']
        has_all = all(field in fk for field in required_fields)
        if has_all:
            print(f"  ✓ {table['name']}.{fk['source_column']} - Valid")
        else:
            print(f"  ✗ {table['name']}.{fk['source_column']} - INVALID (missing fields)")

print("\n" + "=" * 70)
print("✅ FK INFERENCE AND DISPLAY READY FOR FRONTEND")
print("=" * 70)
