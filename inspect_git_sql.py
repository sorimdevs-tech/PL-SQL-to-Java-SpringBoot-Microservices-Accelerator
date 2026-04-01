#!/usr/bin/env python3
"""Inspect actual SQL files from the git repo"""
import requests
import tempfile
from pathlib import Path
import git
import re

try:
    import git
except ImportError:
    print("GitPython required")
    exit(1)

temp_root = Path(tempfile.gettempdir()) / "plsql_acc_tmp"
temp_root.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory(prefix="discovery_", dir=temp_root) as temp_dir:
    repo_dir = Path(temp_dir) / "repo"
    print(f"Cloning to: {repo_dir}")
    
    try:
        git.Repo.clone_from("https://github.com/victorst79/PL-SQL-project", str(repo_dir), depth=1, single_branch=True, branch="master")
        print("✓ Cloned successfully\n")
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
    
    # Find SQL files
    sql_files = list(repo_dir.rglob("*.sql"))
    print(f"Found {len(sql_files)} SQL files\n")
    
    for sql_file in sorted(sql_files):
        print(f"\n{'='*70}")
        print(f"FILE: {sql_file.name}")
        print(f"{'='*70}")
        
        content = sql_file.read_text(encoding='utf-8', errors='ignore')
        
        # Find CREATE TABLE statements
        create_table_pattern = r'CREATE\s+TABLE\s+(\w+)\s*\('
        tables = re.findall(create_table_pattern, content, re.IGNORECASE)
        
        if tables:
            print(f"Tables: {', '.join(tables)}\n")
            
            # Find FOREIGN KEY constraints
            fk_pattern = r'FOREIGN\s+KEY\s*\([^)]+\)\s*REFERENCES\s+(\w+)\s*\([^)]+\)|REFERENCES\s+(\w+)\s*\([^)]+\)'
            fks = re.findall(fk_pattern, content, re.IGNORECASE)
            
            if fks:
                print(f"Found {len(fks)} FK constraints:")
                for fk in fks:
                    target = fk[0] or fk[1]
                    print(f"  → REFERENCES {target}")
            else:
                print("No explicit FK constraints found")
            
            # Show first few lines
            print(f"\nFirst 1500 chars of content:")
            print("-" * 70)
            excerpt = content[:1500]
            lines = excerpt.split('\n')[:20]
            print('\n'.join(lines))
