#!/usr/bin/env python3
"""Debug FK inference with detailed tracing."""

import sys
import json
sys.path.insert(0, 'src')

from parser.discovery_analyzer import (
    build_discovery_model, 
    _infer_implied_foreign_keys,
    _extract_table_definitions,
    _prepare_sql_text,
    _normalize_identifier
)

# Test SQL with parameter threading - DECLARE block version
test_sql = '''
CREATE TABLE XY_CUSTOMER (
    CUSTOMER_ID NUMBER PRIMARY KEY
);

CREATE TABLE XY_VAT (
    VAT_CODE VARCHAR2(5) PRIMARY KEY
);

CREATE TABLE XY_INVOICE (
    INVOICE_ID NUMBER PRIMARY KEY,
    CUSTOMER_ID NUMBER,
    VAT_CODE VARCHAR2(5),
    INVOICE_AMOUNT NUMBER
);

DECLARE
    p_invoice_id IN NUMBER;
    p_customer_id IN NUMBER;
    p_vat_code IN VARCHAR2;
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID, VAT_CODE, INVOICE_AMOUNT)
    VALUES (p_invoice_id, p_customer_id, p_vat_code, 100);
    
    UPDATE XY_INVOICE SET CUSTOMER_ID = p_customer_id, VAT_CODE = p_vat_code WHERE INVOICE_ID = p_invoice_id;
END;
/
'''

cleaned = _prepare_sql_text(test_sql)

# Test _extract_table_definitions
print("=" * 60)
print("1. DDL TABLE EXTRACTION")
print("=" * 60)
table_defs = _extract_table_definitions(cleaned)
print(f"Found {len(table_defs)} tables:")
for t in table_defs:
    print(f"  {t.get('name')}: {[c.get('name') for c in t.get('columns', [])]}")

# Test parameter extraction
print("\n" + "=" * 60)
print("2. PARAMETER EXTRACTION")
print("=" * 60)
import re
all_parameters = []
for match in re.finditer(
    r'\b(?:in|out|in\s+out)\s+(?:nocopy\s+)?(\w+)\s+(?:in\s+)?([A-Z0-9_#\$\.]+)',
    cleaned, re.IGNORECASE
):
    param_name = _normalize_identifier(match.group(1)).upper()
    data_type = _normalize_identifier(match.group(2)).upper()
    all_parameters.append({"name": param_name, "type": data_type})
    print(f"  {param_name}: {data_type}")

print(f"Total parameters: {len(all_parameters)}")

# Test FK inference
print("\n" + "=" * 60)
print("3. FK INFERENCE")
print("=" * 60)
inferred_tables_dict = {t["name"]: t for t in table_defs}
print(f"Inferred tables dict keys: {list(inferred_tables_dict.keys())}")

implied_fks = _infer_implied_foreign_keys(cleaned, inferred_tables_dict, all_parameters)
print(f"Inferred {len(implied_fks)} FKs:")
for fk in implied_fks:
    print(f"  {fk.get('from_table')}.{fk.get('from_column')} -> {fk.get('to_table')}.{fk.get('to_column')}")
    print(f"    Evidence: {fk.get('evidence')}")

# Test full model
print("\n" + "=" * 60)
print("4. FULL BUILD_DISCOVERY_MODEL")
print("=" * 60)
model = build_discovery_model(test_sql)
tables = model.get("schema", {}).get("tables", [])
print(f'Tables in model: {len(tables)}')
for t in tables:
    fks = t.get("foreign_keys", [])
    print(f'{t.get("name")} with {len(fks)} FKs:')
    for fk in fks:
        print(f'  {fk["source_column"]} -> {fk["target_table"]}.{fk["target_column"]}')
