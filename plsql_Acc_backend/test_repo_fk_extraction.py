#!/usr/bin/env python
"""Test FK extraction with actual repository SQL."""
import sys
import tempfile
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser.discovery_analyzer import build_discovery_model

def clone_and_get_sql():
    """Clone the repo and get SQL content."""
    repo_url = "https://github.com/victorst79/PL-SQL-project"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"[INFO] Cloning repo into {tmpdir}...", file=__import__('sys').stderr)
        result = subprocess.run(
            ["git", "clone", "--depth=1", repo_url, tmpdir],
            capture_output=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"[ERROR] Git clone failed: {result.stderr.decode()}", file=sys.stderr)
            return None
        
        # Find SQL files
        repo_path = Path(tmpdir)
        sql_files = list(repo_path.rglob("*.sql"))
        
        if not sql_files:
            print(f"[ERROR] No SQL files found", file=sys.stderr)
            return None
        
        print(f"[INFO] Found {len(sql_files)} SQL file(s)", file=sys.stderr)
        
        # Concatenate all SQL files
        all_sql = []
        for sql_file in sql_files:
            try:
                content = sql_file.read_text(encoding='utf-8', errors='ignore')
                all_sql.append(f"-- File: {sql_file.name}\n{content}")
                print(f"[INFO] Read: {sql_file.name} ({len(content)} bytes)", file=sys.stderr)
            except Exception as e:
                print(f"[WARNING] Could not read {sql_file.name}: {e}", file=sys.stderr)
        
        return "\n\n".join(all_sql)

def test_fk_extraction():
    print("\n" + "="*80, file=sys.stderr)
    print("Testing FK Extraction from GitHub Repo", file=sys.stderr)
    print("="*80, file=sys.stderr)
    
    sql_content = clone_and_get_sql()
    if not sql_content:
        print("[FAILED] Could not get SQL content", file=sys.stderr)
        return False
    
    print(f"\n[INFO] Total SQL content: {len(sql_content)} bytes", file=sys.stderr)
    print(f"[INFO] First 500 chars:\n{sql_content[:500]}\n", file=sys.stderr)
    
    # Test FK extraction
    print("\n[ANALYZING]", file=sys.stderr)
    discovery_model = build_discovery_model(sql_content)
    
    schema = discovery_model.get("schema", {})
    tables = schema.get("tables", [])
    
    print(f"\n[RESULTS] Found {len(tables)} tables:", file=sys.stderr)
    total_fks = 0
    for table in tables:
        fks = table.get("foreign_keys", [])
        total_fks += len(fks)
        status = table.get("fk_extraction_status", "UNKNOWN")
        print(f"  {table.get('name'):15} | Cols: {len(table.get('columns', []))} | FKs: {len(fks)} | Status: {status}", file=sys.stderr)
        if fks:
            for fk in fks:
                print(f"    → {fk.get('source_column')} => {fk.get('target_table')}.{fk.get('target_column')} ({fk.get('fk_source')})", file=sys.stderr)
    
    print(f"\n[SUMMARY] Total FKs extracted: {total_fks}", file=sys.stderr)
    return total_fks > 0

if __name__ == "__main__":
    try:
        success = test_fk_extraction()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[EXCEPTION] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
