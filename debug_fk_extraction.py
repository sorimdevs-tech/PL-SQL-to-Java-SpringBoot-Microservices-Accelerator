#!/usr/bin/env python3
"""Debug: Check detailed FK extraction from git repo"""
import requests
import json
import sys

BASE_URL = "http://localhost:5000"

payload = {
    "repo_url": "https://github.com/victorst79/PL-SQL-project",
    "branch": "master"
}

response = requests.post(
    f"{BASE_URL}/api/discovery/analyze",
    json=payload,
    timeout=120
)

if response.status_code != 200:
    print(f"Error: {response.status_code}")
    sys.exit(1)

data = response.json()
discovery = data.get("discovery", {})
schema = discovery.get("schema", {})
tables = schema.get("tables", [])

print("="*70)
print("ALL TABLES AND THEIR FOREIGN KEYS")
print("="*70)

for table in tables:
    name = table.get('name')
    columns = [c.get('name') for c in table.get('columns', [])]
    fks = table.get('foreign_keys', [])
    fk_status = table.get('fk_extraction_status', 'unknown')
    
    print(f"\n{name}")
    print(f"  Status: {fk_status}")
    print(f"  Columns: {', '.join(columns)}")
    print(f"  FKs: {len(fks)}")
    
    if fks:
        for fk in fks:
            source = fk.get('source_column')
            target_table = fk.get('target_table')
            target_col = fk.get('target_column')
            method = fk.get('fk_type', 'unknown')
            print(f"    → {source} → {target_table}.{target_col} [{method}]")
    else:
        print(f"    (No FKs found)")

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
total_fks = sum(len(t.get('foreign_keys', [])) for t in tables)
print(f"Total tables: {len(tables)}")
print(f"Total FKs: {total_fks}")
