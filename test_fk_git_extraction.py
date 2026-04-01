#!/usr/bin/env python3
"""Test FK extraction from git repo via API"""
import requests
import json
import sys

# Test the /api/discovery/analyze endpoint with git repo
repo_url = "https://github.com/victorst79/PL-SQL-project"

payload = {
    "repo_url": repo_url,
    "branch": "master"
}

print(f"\n[TEST] Analyzing git repo: {repo_url}")
print(f"[TEST] Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(
        "http://localhost:5000/api/discovery/analyze",
        json=payload,
        timeout=120  # 2 minutes
    )
    
    print(f"\n[RESPONSE] Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        # Check if discovery field exists
        if "discovery" in data:
            discovery = data["discovery"]
            schema = discovery.get("schema", {})
            tables = schema.get("tables", [])
            
            print(f"\n[RESULTS]")
            print(f"  Tables: {len(tables)}")
            
            total_fks = 0
            for table in tables:
                fks = table.get("foreign_keys", [])
                total_fks += len(fks)
                if fks:
                    print(f"\n  ✓ {table.get('name')}: {len(fks)} FKs")
                    for fk in fks:
                        print(f"    → {fk.get('source_column')} -> {fk.get('target_table')}.{fk.get('target_column')}")
            
            print(f"\n  Total FKs in response: {total_fks}")
            
            if total_fks > 0:
                print("\n[SUCCESS] FKs extracted from git repo!")
            else:
                print("\n[WARNING] No FKs found - check backend debug logs")
        else:
            print("[ERROR] No 'discovery' field in response")
            print(f"Response keys: {list(data.keys())}")
    else:
        print(f"[ERROR] Response {response.status_code}")
        print(response.text[:500])
        
except requests.exceptions.ConnectionError as e:
    print(f"[ERROR] Could not connect to backend: {e}")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")
    sys.exit(1)
