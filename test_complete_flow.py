#!/usr/bin/env python3
"""Test complete flow: upload file -> analyze -> verify FKs"""
import requests
import json
import sys
from pathlib import Path

# Test URL
BASE_URL = "http://localhost:5000"

# Check if the SQL demo file exists
demo_file = Path("plsql_Acc_backend/demo/complex.sql")
if not demo_file.exists():
    print(f"[ERROR] Demo file not found: {demo_file}")
    sys.exit(1)

print("\n" + "="*60)
print("TEST 1: Upload SQL file")
print("="*60)

# Step 1: Upload file
with open(demo_file, 'rb') as f:
    data = {
        'source_file': (demo_file.name, f, 'application/octet-stream')
    }
    response = requests.post(
        f"{BASE_URL}/api/discovery/upload",
        files=data
    )

if response.status_code != 200:
    print(f"[ERROR] Upload failed: {response.status_code}")
    print(response.text)
    sys.exit(1)

upload_data = response.json()
file_id = upload_data['file_id']
print(f"[OK] File uploaded: {file_id}")

print("\n" + "="*60)
print("TEST 2: Analyze uploaded file")
print("="*60)

# Step 2: Analyze file
analyze_request = {
    "file_id": file_id
}

response = requests.post(
    f"{BASE_URL}/api/discovery/analyze",
    json=analyze_request,
    timeout=30
)

if response.status_code != 200:
    print(f"[ERROR] Analysis failed: {response.status_code}")
    print(response.text[:500])
    sys.exit(1)

analysis_result = response.json()

if "discovery" not in analysis_result:
    print("[ERROR] No discovery field in response!")
    print(f"Response keys: {list(analysis_result.keys())}")
    sys.exit(1)

discovery = analysis_result["discovery"]
schema = discovery.get("schema", {})
tables = schema.get("tables", [])

print(f"[OK] Analysis complete: {len(tables)} tables found")

# Analyze FKs
fk_summary = {}
total_fks = 0
for table in tables:
    fks = table.get("foreign_keys", [])
    total_fks += len(fks)
    if fks:
        fk_summary[table["name"]] = []
        for fk in fks:
            fk_summary[table["name"]].append({
                "source": fk.get("source_column"),
                "target_table": fk.get("target_table"),
                "target_column": fk.get("target_column")
            })

print(f"\n[RESULTS]")
print(f"Total tables: {len(tables)}")
print(f"Total FKs: {total_fks}")

if fk_summary:
    print("\n[FK DETAIL]")
    for table_name, fks in sorted(fk_summary.items()):
        print(f"  {table_name}:")
        for fk in fks:
            print(f"    → {fk['source']} -> {fk['target_table']}.{fk['target_column']}")
else:
    print("\n[WARNING] No FKs found")

print("\n" + "="*60)
print("✓ Test complete")
print("="*60)

# Print response structure for debugging
print(f"\nResponse discovery keys: {list(discovery.keys())}")
print(f"Schema keys: {list(schema.keys())}")
if tables:
    print(f"First table keys: {list(tables[0].keys())}")
