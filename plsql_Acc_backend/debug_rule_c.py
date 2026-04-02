#!/usr/bin/env python3
"""Debug Rule C FK inference."""

import sys
import re
sys.path.insert(0, 'src')

from parser.discovery_analyzer import _infer_implied_foreign_keys, _prepare_sql_text

sql = '''
CREATE TABLE XY_CUSTOMER (
    CUSTOMER_ID NUMBER PRIMARY KEY
);

CREATE TABLE XY_INVOICE (
    INVOICE_ID NUMBER PRIMARY KEY,
    CUSTOMER_ID NUMBER
);

CREATE TABLE APPL_LOG (
    LOG_DATE DATE
);

DECLARE
    p_customer_id IN NUMBER;
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID)
    VALUES (1, p_customer_id);
END;
/
'''

cleaned = _prepare_sql_text(sql)

# Build inferred_tables dict
inferred_tables_dict = {
    "XY_CUSTOMER": {
        "name": "XY_CUSTOMER",
        "columns": [{"name": "CUSTOMER_ID", "type": "NUMBER"}]
    },
    "XY_INVOICE": {
        "name": "XY_INVOICE",
        "columns": [{"name": "INVOICE_ID", "type": "NUMBER"}, {"name": "CUSTOMER_ID", "type": "NUMBER"}]
    },
    "APPL_LOG": {
        "name": "APPL_LOG",
        "columns": [{"name": "LOG_DATE", "type": "DATE"}]
    }
}

print("="*80)
print("TESTING FK INFERENCE")
print("="*80)

print("\nInferred tables:")
for name, table in inferred_tables_dict.items():
    cols = [c["name"] for c in table["columns"]]
    print(f"  {name}: {cols}")

print("\nColumn to tables mapping (Rule C input):")
all_columns = {}
for table_name, table_info in inferred_tables_dict.items():
    for col_info in table_info.get("columns", []):
        col_name = col_info.get("name", "").upper()
        all_columns.setdefault(col_name, set()).add(table_name)

for col_name, tables in sorted(all_columns.items()):
    print(f"  {col_name}: {list(tables)}")

print("\nTesting Rule C logic:")
for col_name, tables_with_col in sorted(all_columns.items()):
    if col_name.endswith("_ID"):
        print(f"\n  {col_name}:")
        print(f"    Tables with this column: {list(tables_with_col)}")
        print(f"    Appears in {len(tables_with_col)} tables")
        if len(tables_with_col) >= 2:
            print(f"    ✓ Qualifies for Rule C (appears in 2+ tables)")
        else:
            print(f"    ✗ Does NOT qualify (appears in <2 tables)")

# Run actual FK inference
all_params = [{"name": "P_CUSTOMER_ID", "type": "NUMBER"}]
implied_fks = _infer_implied_foreign_keys(cleaned, inferred_tables_dict, all_params)

print("\n\nGenerated FKs:")
print(f"Total: {len(implied_fks)}")
for fk in implied_fks:
    print(f"  {fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']}")
    print(f"    Evidence: {fk.get('evidence')}")
    print(f"    Confidence: {fk.get('confidence')}")

print("\n\nSelf-referential FKs (should be 0):")
self_refs = [fk for fk in implied_fks if fk['from_table'] == fk['to_table']]
print(f"Count: {len(self_refs)}")
for fk in self_refs:
    print(f"  {fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']}")
