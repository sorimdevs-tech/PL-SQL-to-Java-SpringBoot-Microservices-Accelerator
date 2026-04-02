#!/usr/bin/env python
"""Debug the _infer_implied_foreign_keys function to see what's happening."""

import sys
sys.path.insert(0, "plsql_Acc_backend")

from src.parser.discovery_analyzer import (
    _prepare_sql_text,
    _extract_operations_and_tables,
    _extract_table_columns,
    _extract_parameters,
    _extract_objects,
    _infer_implied_foreign_keys,
    _normalize_identifier,
    _split_top_level_csv,
)

sql = """
CREATE OR REPLACE PROCEDURE process_invoice(
    p_customer_id IN NUMBER,
    p_invoice_id IN NUMBER,
    p_vat_code IN VARCHAR2
) AS
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID, VAT_CODE) VALUES (p_invoice_id, p_customer_id, p_vat_code);
    UPDATE XY_CUSTOMER SET status = 'ACTIVE' WHERE customer_id = p_customer_id;
    UPDATE XY_VAT SET vat_rate = 0.15 WHERE vat_code = p_vat_code;
    UPDATE APPL_LOG SET log_status = 'DONE' WHERE log_status != 'DONE';
END;
"""

print("=== DEBUGGING _infer_implied_foreign_keys ===\n")

cleaned = _prepare_sql_text(sql)

# Extract objects
objects = _extract_objects(cleaned)
blocks = [item.block_text for item in objects] or [cleaned]

# Extract parameters
all_parameters = []
for obj in objects:
    from src.parser.discovery_analyzer import _extract_parameters
    params_extracted = _extract_parameters(obj.block_text)
    all_parameters.extend(params_extracted.get("all", []))

print(f"Parameters found: {len(all_parameters)}")
for p in all_parameters:
    print(f"  - {p['name']} ({p['direction']}, {p['type']})")

# Extract tables
inferred_tables_set = set()
inferred_columns = {}

for block_text in blocks:
    ops_tables = _extract_operations_and_tables(block_text)
    for table_name in ops_tables.get("tables", []):
        normalized = _normalize_identifier(table_name).upper()
        inferred_tables_set.add(normalized)
        inferred_columns.setdefault(normalized, set())

print(f"\nTables found: {list(inferred_tables_set)}")

# Extract columns for each table
for block_text in blocks:
    table_columns = _extract_table_columns(block_text, sorted(inferred_tables_set))
    for table_name, columns in table_columns.items():
        normalized_table = _normalize_identifier(table_name).upper()
        inferred_columns.setdefault(normalized_table, set()).update(
            _normalize_identifier(column).upper()
            for column in columns
            if column
        )

# Build inferred tables dict (like the real code does)
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

print("\nInferred tables dict:")
for table_name, table_data in inferred_tables_dict.items():
    print(f"  {table_name}:")
    print(f"    Columns: {[c['name'] for c in table_data['columns']]}")

# Now call _infer_implied_foreign_keys
implied_fks = _infer_implied_foreign_keys(cleaned, inferred_tables_dict, all_parameters)

print(f"\nImplied FKs generated: {len(implied_fks)}")
for fk in implied_fks:
    print(f"  - {fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']}")
    print(f"    Evidence: {fk.get('evidence', 'N/A')}")
