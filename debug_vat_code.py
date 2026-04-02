#!/usr/bin/env python
"""Debug why VAT_CODE FK is not being inferred."""

import sys
sys.path.insert(0, "plsql_Acc_backend")

from src.parser.discovery_analyzer import (
    _prepare_sql_text,
    _extract_operations_and_tables,
    _extract_table_columns,
    _extract_parameters,
    _extract_objects,
    _normalize_identifier,
    _split_top_level_csv,
    re, PARAM_PATTERN,
)

sql = """
CREATE OR REPLACE PROCEDURE process_invoice(
    p_vat_code IN VARCHAR2
) AS
BEGIN
    INSERT INTO XY_INVOICE (VAT_CODE) VALUES (p_vat_code);
    UPDATE XY_VAT SET vat_rate = 0.15 WHERE vat_code = p_vat_code;
END;
"""

print("=== DEBUGGING VAT_CODE FK INFERENCE ===\n")

cleaned = _prepare_sql_text(sql)

# Extract objects and parameters
objects = _extract_objects(cleaned)
blocks = [item.block_text for item in objects] or [cleaned]

all_parameters = []
for obj in objects:
    from src.parser.discovery_analyzer import _extract_parameters
    params_extracted = _extract_parameters(obj.block_text)
    all_parameters.extend(params_extracted.get("all", []))

print(f"Parameters: {[p['name'] for p in all_parameters]}")

# Extract tables
inferred_tables_set = set()
inferred_columns = {}

for block_text in blocks:
    ops_tables = _extract_operations_and_tables(block_text)
    for table_name in ops_tables.get("tables", []):
        normalized = _normalize_identifier(table_name).upper()
        inferred_tables_set.add(normalized)

print(f"Tables: {sorted(inferred_tables_set)}")

# Extract columns
for block_text in blocks:
    table_columns = _extract_table_columns(block_text, sorted(inferred_tables_set))
    for table_name, columns in table_columns.items():
        normalized_table = _normalize_identifier(table_name).upper()
        inferred_columns.setdefault(normalized_table, set()).update(
            _normalize_identifier(column).upper()
            for column in columns
            if column
        )

inferred_tables_dict = {
    table_name: {
        "name": table_name,
        "columns": [
            {"name": col_name, "type": "UNKNOWN"}
            for col_name in sorted(inferred_columns.get(table_name, set()))
        ],
        "foreign_keys": [],
    }
    for table_name in sorted(inferred_tables_set)
}

print("\nTable columns:")
for table_name, table_data in inferred_tables_dict.items():
    print(f"  {table_name}: {[c['name'] for c in table_data['columns']]}")

# Now manually walk through the INSERT pattern matching
print("\n=== MANUALLY TRACING INSERT PATTERN ===\n")

param_name = "P_VAT_CODE"
insert_pattern = rf"insert\s+into\s+([`\"\w$#\.]+)\s*\(([^)]+)\)\s*values\s*\(([^)]*{param_name}[^)]*)\)"

print(f"Looking for pattern with param: {param_name}")
for block_text in blocks:
    for match in re.finditer(insert_pattern, block_text, re.IGNORECASE | re.DOTALL):
        print(f"\nFound INSERT match:")
        table_name = _normalize_identifier(match.group(1)).upper()
        col_list_text = match.group(2)
        values_text = match.group(3)
        
        print(f"  Table: {table_name}")
        print(f"  Col list: {col_list_text}")
        print(f"  Values: {values_text}")
        
        insert_cols = [_normalize_identifier(c).upper() for c in _split_top_level_csv(col_list_text)]
        insert_vals = [v.strip().upper() for v in _split_top_level_csv(values_text)]
        
        print(f"  Parsed cols: {insert_cols}")
        print(f"  Parsed vals: {insert_vals}")
        
        for col, val in zip(insert_cols, insert_vals):
            if param_name in val:
                print(f"\n  Found param in column: {col} = {val}")
                col_base = col.replace("_ID", "").replace("_", "")
                print(f"  Col base: {col_base}")
                
                print(f"\n  Checking potential targets:")
                for potential_target in inferred_tables_dict:
                    print(f"    - {potential_target}")
                    
                    if table_name == potential_target:
                        print(f"      SKIP: Same as source table")
                        continue
                    
                    col_match = col_base.lower() in potential_target.lower()
                    special_match = col == "VAT_CODE" and "VAT" in potential_target
                    
                    print(f"      Column match: {col_match} ('{col_base}' in '{potential_target}')")
                    print(f"      Special match: {special_match}")
                    
                    if col_match or special_match:
                        target_cols = {c.get("name", "").upper() for c in inferred_tables_dict[potential_target].get("columns", [])}
                        print(f"      Target cols: {target_cols}")
                        if col in target_cols:
                            print(f"      ✓ MATCH! Would create FK: {table_name}.{col} -> {potential_target}.{col}")
                        else:
                            print(f"      ✗ Column {col} not in target")
