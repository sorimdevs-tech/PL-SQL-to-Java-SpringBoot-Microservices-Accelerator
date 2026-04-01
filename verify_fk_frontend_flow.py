#!/usr/bin/env python3
"""
Frontend-like test: Verify FK extraction works as the frontend would call it.
This simulates the exact API calls the frontend makes during Stage 2 Discovery.
"""
import requests
import json
import sys
from pathlib import Path

BASE_URL = "http://localhost:5000"
FRONTEND_API_URL = "http://localhost:5173/api"  # Note: frontend would proxy through its own API

def test_git_repo_discovery():
    """Test: Frontend analyzing a git repository"""
    print("\n" + "="*70)
    print("TEST: Frontend Git Repository Analysis")
    print("="*70)
    
    payload = {
        "repo_url": "https://github.com/victorst79/PL-SQL-project",
        "branch": "master"
    }
    
    print(f"API Call: POST /api/discovery/analyze")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/discovery/analyze",
            json=payload,
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"\n❌ FAILED: HTTP {response.status_code}")
            print(response.text[:500])
            return False
        
        data = response.json()
        discovery = data.get("discovery", {})
        schema = discovery.get("schema", {})
        tables = schema.get("tables", [])
        
        # Verify foreign_keys field exists in response
        if not tables:
            print(f"⚠️  WARNING: No tables found in response")
            return False
        
        # Check if any table has foreign_keys field
        fk_count = 0
        for table in tables:
            if "foreign_keys" not in table:
                print(f"❌ MISSING: Table '{table.get('name')}' missing 'foreign_keys' field")
                return False
            fks = table.get("foreign_keys", [])
            fk_count += len(fks)
        
        print(f"\n✅ SUCCESS")
        print(f"  Tables: {len(tables)}")
        print(f"  Total FKs: {fk_count}")
        
        # Show FK details
        for table in tables:
            fks = table.get("foreign_keys", [])
            if fks:
                print(f"\n  Table: {table.get('name')}")
                for fk in fks:
                    print(f"    ✓ {fk.get('source_column')} → {fk.get('target_table')}.{fk.get('target_column')}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        return False

def test_uploaded_file_discovery():
    """Test: Frontend uploading and analyzing a SQL file"""
    print("\n" + "="*70)
    print("TEST: Frontend File Upload & Analysis")
    print("="*70)
    
    demo_file = Path("plsql_Acc_backend/demo/complex.sql")
    if not demo_file.exists():
        print(f"❌ Test file not found: {demo_file}")
        return False
    
    # Step 1: Upload
    print(f"\nStep 1: Upload file")
    try:
        with open(demo_file, 'rb') as f:
            data = {'source_file': (demo_file.name, f, 'application/octet-stream')}
            response = requests.post(
                f"{BASE_URL}/api/discovery/upload",
                files=data
            )
        
        if response.status_code != 200:
            print(f"  ❌ Upload failed: {response.status_code}")
            return False
        
        upload_data = response.json()
        file_id = upload_data.get('file_id')
        print(f"  ✓ File uploaded: {file_id[:12]}...")
        
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False
    
    # Step 2: Analyze
    print(f"\nStep 2: Analyze uploaded file")
    try:
        response = requests.post(
            f"{BASE_URL}/api/discovery/analyze",
            json={"file_id": file_id},
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"  ❌ Analysis failed: {response.status_code}")
            return False
        
        data = response.json()
        discovery = data.get("discovery", {})
        schema = discovery.get("schema", {})
        tables = schema.get("tables", [])
        
        # Count FKs
        fk_count = sum(len(t.get("foreign_keys", [])) for t in tables)
        
        print(f"  ✓ Analysis complete")
        print(f"    Tables: {len(tables)}")
        print(f"    FKs: {fk_count}")
        
        # Show FK details
        for table in tables:
            fks = table.get("foreign_keys", [])
            if fks:
                print(f"\n    Table: {table.get('name')}")
                for fk in fks:
                    print(f"      ✓ {fk.get('source_column')} → {fk.get('target_table')}.{fk.get('target_column')}")
        
        print(f"\n✅ SUCCESS")
        return True
        
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False

def test_schema_response_structure():
    """Test: Verify API response includes all required FK fields"""
    print("\n" + "="*70)
    print("TEST: API Response Structure Validation")
    print("="*70)
    
    demo_file = Path("plsql_Acc_backend/demo/complex.sql")
    
    try:
        # Upload and analyze
        with open(demo_file, 'rb') as f:
            data = {'source_file': (demo_file.name, f, 'application/octet-stream')}
            response = requests.post(f"{BASE_URL}/api/discovery/upload", files=data)
        
        file_id = response.json()['file_id']
        
        response = requests.post(
            f"{BASE_URL}/api/discovery/analyze",
            json={"file_id": file_id},
            timeout=30
        )
        
        data = response.json()
        discovery = data.get("discovery", {})
        schema = discovery.get("schema", {})
        tables = schema.get("tables", [])
        
        print("\nValidating response structure...")
        
        # Check response root keys
        required_root_keys = ["discovery"]
        for key in required_root_keys:
            if key not in data:
                print(f"  ❌ Missing root key: {key}")
                return False
            print(f"  ✓ Root key '{key}' present")
        
        # Check discovery keys
        required_discovery_keys = ["schema", "procedures"]
        for key in required_discovery_keys:
            if key not in discovery:
                print(f"  ❌ Missing discovery key: {key}")
                return False
            print(f"  ✓ Discovery key '{key}' present")
        
        # Check schema keys
        required_schema_keys = ["tables", "relationships"]
        for key in required_schema_keys:
            if key not in schema:
                print(f"  ❌ Missing schema key: {key}")
                return False
            print(f"  ✓ Schema key '{key}' present")
        
        # Check table structure
        if tables:
            table = tables[0]
            required_table_keys = ["name", "columns", "primary_keys", "foreign_keys"]
            for key in required_table_keys:
                if key not in table:
                    print(f"  ❌ Missing table key: {key}")
                    return False
                print(f"  ✓ Table key '{key}' present")
            
            # Check FK structure
            fks = table.get("foreign_keys", [])
            if fks:
                fk = fks[0]
                required_fk_keys = ["source_column", "target_table", "target_column"]
                for key in required_fk_keys:
                    if key not in fk:
                        print(f"  ❌ Missing FK key: {key}")
                        return False
                    print(f"  ✓ FK key '{key}' present")
        
        print(f"\n✅ SUCCESS: Response structure is valid")
        return True
        
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    results = []
    
    results.append(("Git Repo Discovery", test_git_repo_discovery()))
    results.append(("File Upload & Analysis", test_uploaded_file_discovery()))
    results.append(("Response Structure", test_schema_response_structure()))
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + ("="*70))
    if all_passed:
        print("🎉 ALL TESTS PASSED - FK Extraction is working correctly!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)
