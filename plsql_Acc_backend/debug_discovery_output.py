#!/usr/bin/env python
"""Debug discovery output for test_fk.sql"""

from pathlib import Path
from src.parser.discovery_analyzer import build_discovery_model

sql_file = Path("demo/test_fk.sql")
sql_text = sql_file.read_text()

discovery = build_discovery_model(sql_text)

print("Column and FK Info for each table:")
print("=" * 80)

for table in discovery.get("schema", {}).get("tables", []):
    name = table.get("name")
    print("\nTable: {}".format(name))
    
    # Show columns
    cols = table.get("columns", [])
    print("  Columns:")
    for col in cols:
        print("    - {} : {}".format(col.get("name"), col.get("type")))
    
    # Show FKs
    fks = table.get("foreign_keys", [])
    if fks:
        print("  Foreign Keys:")
        for fk in fks:
            print("    - {} -> {}.{}".format(
                fk.get("source_column"),
                fk.get("target_table"),
                fk.get("target_column")
            ))
    else:
        print("  Foreign Keys: (none)")
