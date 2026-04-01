#!/usr/bin/env python
"""Extract and display procedure code from the repo."""
import tempfile
import subprocess
from pathlib import Path

repo_url = "https://github.com/victorst79/PL-SQL-project"
with tempfile.TemporaryDirectory() as tmpdir:
    subprocess.run(["git", "clone", "--depth=1", repo_url, tmpdir], 
                  capture_output=True, timeout=30)
    sql_file = next(Path(tmpdir).rglob("*.sql"), None)
    if sql_file:
        sql = sql_file.read_text(encoding='utf-8', errors='ignore')
        
        # Find viewItem procedure
        import re
        proc_match = re.search(r'CREATE.*?PROCEDURE\s+viewItem.*?BEGIN(.*?)END\s+viewItem', 
                              sql, re.IGNORECASE | re.DOTALL)
        if proc_match:
            print("=== VIEWITEM PROCEDURE ===")
            print(proc_match.group(1)[:1500])
        
        # Find handleReturns procedure
        proc_match = re.search(r'CREATE.*?PROCEDURE\s+handleReturns.*?BEGIN(.*?)END\s+handleReturns', 
                              sql, re.IGNORECASE | re.DOTALL)
        if proc_match:
            print("\n\n=== HANDLERETURNS PROCEDURE ===")
            print(proc_match.group(1)[:1500])
        
        # Find table structures
        print("\n\n=== TABLE STRUCTURES ===")
        book_match = re.search(r'CREATE\s+TABLE\s+Book\s*\((.*?)\);', 
                              sql, re.IGNORECASE | re.DOTALL)
        if book_match:
            print("\nBOOK TABLE:")
            print(book_match.group(1)[:500])
        
        video_match = re.search(r'CREATE\s+TABLE\s+Video\s*\((.*?)\);', 
                               sql, re.IGNORECASE | re.DOTALL)
        if video_match:
            print("\nVIDEO TABLE:")
            print(video_match.group(1)[:500])
