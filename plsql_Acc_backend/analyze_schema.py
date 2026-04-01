#!/usr/bin/env python
"""Analyze the actual SQL schema to find FK patterns."""
import tempfile
import subprocess
from pathlib import Path

def get_repo_sql():
    """Clone the repo and get SQL."""
    repo_url = "https://github.com/victorst79/PL-SQL-project"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "clone", "--depth=1", repo_url, tmpdir], 
                      capture_output=True, timeout=30)
        
        sql_file = next(Path(tmpdir).rglob("*.sql"), None)
        if sql_file:
            return sql_file.read_text(encoding='utf-8', errors='ignore')
    return ""

def analyze_schema():
    """Analyze the schema to find FK opportunities."""
    sql = get_repo_sql()
    if not sql:
        print("Could not get SQL")
        return
    
    # Extract table definitions
    import re
    
    # Find all CREATE TABLE statements  
    create_tables = re.findall(
        r'CREATE\s+TABLE\s+(\w+)\s*\((.*?)\);',
        sql,
        re.IGNORECASE | re.DOTALL
    )
    
    print("=== SCHEMA ANALYSIS ===\n")
    for table_name, body in create_tables:
        print(f"Table: {table_name}")
        
        # Find all columns
        col_pattern = r'(\w+)\s+(\w+(?:\s*\([^)]*\))?)'
        columns = re.findall(col_pattern, body)
        
        for col_name, col_type in columns:
            # Skip constraints
            if col_name.upper() in {'CONSTRAINT', 'PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK'}:
                continue
            
            line = f"  {col_name:20} {col_type}"
            
            # Highlight potential FK columns (ending in ID, NAME, etc.)
            if col_name.upper().endswith(('ID', 'NAME', 'NUMBER')):
                line += " ← POTENTIAL FK"
            
            print(line)
        
        print()

if __name__ == "__main__":
    analyze_schema()
