#!/usr/bin/env python
"""Analyze SQL from the GitHub repository to check for FKs."""
import json
import sys
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser.discovery_analyzer import build_discovery_model

def download_github_sql(repo_url: str, branch: str = "main") -> str:
    """Download SQL files from GitHub repo."""
    # Convert GitHub URL to raw content URL
    if "github.com" in repo_url:
        parts = repo_url.replace("https://github.com/", "").replace(".git", "").split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
            # Try to find SQL files in the repo
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents"
            try:
                with urlopen(api_url) as response:
                    files = json.loads(response.read())
                    sql_content = []
                    for file in files:
                        if file.get("name", "").endswith((".sql", ".plsql")):
                            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file['name']}"
                            try:
                                with urlopen(raw_url) as sql_response:
                                    sql_content.append(sql_response.read().decode("utf-8"))
                            except:
                                pass
                    return "\n\n".join(sql_content)
            except Exception as e:
                print(f"Error fetching from GitHub: {e}")
    return ""

def analyze_repo_sql():
    repo_url = "https://github.com/victorst79/PL-SQL-project"
    
    print("=" * 80)
    print(f"Analyzing SQL from: {repo_url}")
    print("=" * 80)
    
    sql_text = download_github_sql(repo_url)
    if not sql_text:
        print("ERROR: Could not download SQL from repository")
        print("\nTrying alternative approach - looking for common table patterns...")
        return False
    
    print(f"\nDownloaded SQL length: {len(sql_text)} chars")
    print(f"First 500 chars:\n{sql_text[:500]}\n")
    
    # Build discovery model
    discovery_model = build_discovery_model(sql_text)
    schema = discovery_model.get("schema", {})
    tables = schema.get("tables", [])
    
    print(f"Discovered {len(tables)} tables:")
    fk_count = 0
    for table in tables:
        fks = table.get("foreign_keys", [])
        fk_count += len(fks)
        print(f"  {table.get('name')}: {len(fks)} FKs, status={table.get('fk_extraction_status')}")
        if fks:
            for fk in fks:
                print(f"    → {fk.get('source_column')} -> {fk.get('target_table')}.{fk.get('target_column')} ({fk.get('fk_source')})")
    
    print(f"\nTotal FKs found: {fk_count}")
    
    if fk_count == 0:
        print("\n⚠ WARNING: No foreign keys found in the repository")
        print("\nTablenames found:", [t.get("name") for t in tables])
        print("\nThis could mean:")
        print("  1. The SQL doesn't define FOREIGN KEY constraints")
        print("  2. Naming patterns don't match (e.g., no table references in patterns)")
        print("  3. The SQL uses inline REFERENCES but they're not being extracted")
    
    return fk_count > 0

if __name__ == "__main__":
    try:
        success = analyze_repo_sql()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
