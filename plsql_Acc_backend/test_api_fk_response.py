#!/usr/bin/env python
"""Test the API endpoint to verify FKs are returned."""
import tempfile
import subprocess
from pathlib import Path
import json
import time
from urllib.request import urlopen, Request
from urllib.parse import urlencode

def get_repo_sql_file():
    """Clone the repo and return path to SQL file."""
    repo_url = "https://github.com/victorst79/PL-SQL-project"
    
    tmpdir = tempfile.mkdtemp()
    subprocess.run(["git", "clone", "--depth=1", repo_url, tmpdir], 
                  capture_output=True, timeout=30)
    
    sql_file = next(Path(tmpdir).rglob("*.sql"), None)
    return str(sql_file) if sql_file else None

def test_api_upload():
    """Test the /api/discovery/upload and /api/discovery/analyze endpoints."""
    print("\n=== Testing FK Extraction via API ===")
    
    sql_file = get_repo_sql_file()
    if not sql_file:
        print("[ERROR] No SQL file found")
        return False
    
    print(f"[INFO] Using SQL file: {sql_file}")
    
    # Upload file
    print("\n[1] UPLOADING FILE...")
    try:
        with open(sql_file, 'rb') as f:
            files = {'source_file': f}
            upload_resp = requests.post("http://127.0.0.1:8000/api/discovery/upload", files=files, timeout=10)
        
        if upload_resp.status_code != 200:
            print(f"[ERROR] Upload failed: {upload_resp.status_code} {upload_resp.text}")
            return False
        
        upload_data = upload_resp.json()
        file_id = upload_data.get('file_id')
        print(f"[OK] File uploaded with ID: {file_id}")
    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")
        return False
    
    # Analyze
    print("\n[2] ANALYZING FILE...")
    try:
        analyze_resp = requests.post(
            "http://127.0.0.1:8000/api/discovery/analyze",
            json={"file_id": file_id},
            timeout=30
        )
        
        if analyze_resp.status_code != 200:
            print(f"[ERROR] Analysis failed: {analyze_resp.status_code}")
            print(f"Response: {analyze_resp.text}")
            return False
        
        analysis = analyze_resp.json()
        print("[OK] Analysis completed")
    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}")
        return False
    
    # Check FKs
    print("\n[3] CHECKING FK DATA IN RESPONSE...")
    schema = analysis.get('discovery', {}).get('schema', {})
    tables = schema.get('tables', [])
    
    print(f"[INFO] Found {len(tables)} tables in response")
    
    total_fks = 0
    for table in tables:
        fks = table.get('foreign_keys', [])
        total_fks += len(fks)
        status = table.get('fk_extraction_status', 'UNKNOWN')
        
        print(f"  {table.get('name'):15} → {len(fks)} FKs | Status: {status}")
        
        if fks:
            for fk in fks:
                print(f"      ✓ {fk.get('source_column')} → {fk.get('target_table')}.{fk.get('target_column')}")
    
    print(f"\n[SUMMARY] Total FKs in API response: {total_fks}")
    
    if total_fks > 0:
        print("\n✓ SUCCESS: FKs are being returned in the API response!")
        print("They should now display in the frontend schema explorer.")
        return True
    else:
        print("\n✗ WARNING: No FKs in the API response")
        print("FKs might not exist in this SQL or weren't extracted properly.")
        return False

if __name__ == "__main__":
    try:
        # Check if backend is running
        print("[INFO] Checking if backend is running on port 8000...")
        resp = requests.get("http://127.0.0.1:8000/health", timeout=5)
        if resp.status_code != 200:
            print("[ERROR] Backend is not responding to /health")
            exit(1)
        print("[OK] Backend is running")
        
        success = test_api_upload()
        exit(0 if success else 1)
    except requests.exceptions.ConnectionError:
        print("[ERROR] Could not connect to backend at http://127.0.0.1:8000")
        print("[INFO] Make sure the backend is running: python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000")
        exit(1)
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        exit(1)
