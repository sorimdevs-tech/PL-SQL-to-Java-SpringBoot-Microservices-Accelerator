#!/usr/bin/env python
"""Download and inspect SQL from GitHub repo."""
import subprocess
import sys
from pathlib import Path
import tempfile

def download_repo():
    """Clone the repo and extract SQL."""
    repo_url = "https://github.com/victorst79/PL-SQL-project"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Cloning into {tmpdir}...")
        subprocess.run([
            "git", "clone", "--depth=1", repo_url, tmpdir
        ], capture_output=True, check=False)
        
        # Find SQL files
        repo_path = Path(tmpdir)
        sql_files = list(repo_path.rglob("*.sql"))
        
        if not sql_files:
            print("No SQL files found!")
            return None
        
        print(f"Found {len(sql_files)} SQL file(s)")
        
        # Read the first SQL file
        sql_file = sql_files[0]
        print(f"\nReading: {sql_file.name}")
        content = sql_file.read_text(encoding='utf-8', errors='ignore')
        
        return content

if __name__ == "__main__":
    sql_content = download_repo()
    if sql_content:
        print(f"\n=== SQL Content (first 2000 chars) ===\n{sql_content[:2000]}\n")
        
        # Look for CREATE TABLE statements
        import re
        creates = re.findall(r'CREATE\s+TABLE\s+(\w+)', sql_content, re.IGNORECASE)
        if creates:
            print(f"Tables found: {creates}\n")
        
        # Look for column patterns that might be FKs
        fk_patterns = re.findall(r'(\w+ID)\s+(?:NUMBER|VARCHAR|DATE)', sql_content, re.IGNORECASE)
        if fk_patterns:
            print(f"Potential FK columns (ending in ID): {fk_patterns}\n")
