#!/usr/bin/env python
"""Analyze actual SQL schema and what columns procedures are accessing."""
import tempfile
import subprocess
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).parent / "src"))
from parser.discovery_analyzer import build_discovery_model

def get_repo_sql():
    """Clone and get SQL."""
    repo_url = "https://github.com/victorst79/PL-SQL-project"
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "clone", "--depth=1", repo_url, tmpdir], 
                      capture_output=True, timeout=30)
        sql_file = next(Path(tmpdir).rglob("*.sql"), None)
        if sql_file:
            return sql_file.read_text(encoding='utf-8', errors='ignore')
    return ""

sql = get_repo_sql()
if not sql:
    print("ERROR: Could not get SQL")
    sys.exit(1)

print("="*80)
print("SCHEMA ANALYSIS")
print("="*80)

discovery_model = build_discovery_model(sql)
schema = discovery_model.get("schema", {})
tables = schema.get("tables", [])

# Build table info
table_columns = {}
for table in tables:
    cols = {c['name']: c['type'] for c in table.get('columns', [])}
    table_columns[table.get('name')] = cols
    print(f"\nTABLE: {table.get('name')}")
    print(f"  Columns ({len(cols)}):")
    for col_name, col_type in sorted(cols.items()):
        print(f"    • {col_name:20} {col_type}")

# Now analyze procedures to see what columns they reference
print("\n" + "="*80)
print("PROCEDURE ANALYSIS - Column References")
print("="*80)

# Find all procedure bodies
proc_pattern = r'CREATE(?:\s+OR\s+REPLACE)?\s+PROCEDURE\s+(\w+).*?(?:BEGIN|AS)(.*?)(?:END\s+\w*;|/)'
procedures = re.findall(proc_pattern, sql, re.IGNORECASE | re.DOTALL)

for proc_name, proc_body in procedures[:3]:  # Just show first 3
    print(f"\nPROCEDURE: {proc_name}")
    
    # Find SELECT statements
    selects = re.findall(r'SELECT\s+(.*?)\s+FROM\s+(\w+)', proc_body, re.IGNORECASE | re.DOTALL)
    for select_cols, from_table in selects[:2]:
        cols = re.findall(r'([a-zA-Z_]\w*)', select_cols)
        print(f"  SELECT {', '.join(cols[:5])}... FROM {from_table}")
        
        # Check if columns exist in that table
        if from_table in table_columns:
            table_cols = table_columns[from_table]
            for col in cols[:5]:
                exists = "✓" if col.upper() in table_cols else "✗ MISSING"
                print(f"    {exists} {col}")

print("\n" + "="*80)
print("ISSUES FOUND")
print("="*80)

# Look for column references that don't exist
for proc_name, proc_body in procedures[:5]:
    # Find all column getters
    getters = re.findall(r'row\.get(\w+)\(\)', proc_body, re.IGNORECASE)
    for getter in set(getters):
        print(f"\n{proc_name} calls: row.get{getter}()")
        
        # Try to match to a table/column
        for table_name, cols in table_columns.items():
            col_key = getter.upper()
            if col_key in cols:
                print(f"  ✓ Found in {table_name}.{col_key}")
                break
        else:
            print(f"  ✗ NOT FOUND IN ANY TABLE")
