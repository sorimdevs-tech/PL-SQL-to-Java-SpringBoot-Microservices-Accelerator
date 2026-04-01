#!/usr/bin/env python3
"""
STRICT PL/SQL ANALYZER - Dynamic Repository Analysis

Applies 7 STRICT ANALYSIS RULES with zero hallucination:
1. SCOPE: OBJECT or REPO
2. SCHEMA RULE: Only if CREATE TABLE/ALTER TABLE present
3. TABLE USAGE: From DML only
4. EXCEPTION DETECTION: raise_application_error, RAISE, WHEN...THEN
5. CURSOR DETECTION: Explicit CURSOR, FOR...IN, OPEN/FETCH/CLOSE
6. RETRY LOGIC: LOOP, GOTO, exception patterns
7. ERROR HANDLING: Full details or empty (never N/A)

Usage:
  python strict_plsql_analyzer.py <repo_path> [--object <object_name>]
"""

import sys
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Any, Set, Optional, Tuple


class StrictPLSQLAnalyzer:
    """STRICT PL/SQL analyzer with zero hallucination."""
    
    def __init__(self, repo_path: str, scope: str = "REPO"):
        self.repo_path = Path(repo_path)
        self.scope = scope
        self.sql_files = []
        self.analysis = {
            "analysis_scope": scope,
            "analysis_date": "2026-03-31",
            "schema": {"status": "NOT_FOUND", "tables": []},
            "external_tables": [],
            "procedures": []
        }
    
    def collect_sql_files(self) -> List[Path]:
        """Collect all .sql, .pkb, .pks files from repo."""
        patterns = ["*.sql", "*.pkb", "*.pks", "*.pkg"]
        sql_files = []
        for pattern in patterns:
            sql_files.extend(self.repo_path.glob(f"**/{pattern}"))
        self.sql_files = sorted(sql_files)
        return self.sql_files
    
    def read_file(self, filepath: Path) -> str:
        """Read file with error handling."""
        try:
            return filepath.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            print(f"  ⚠ Error reading {filepath}: {e}", file=sys.stderr)
            return ""
    
    def extract_objects(self, text: str) -> List[Dict[str, str]]:
        """Extract all CREATE PROCEDURE/FUNCTION/PACKAGE objects."""
        objects = []
        
        # Pattern for procedures, functions, and packages
        pattern = re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:EDITIONABLE\s+|NONEDITIONABLE\s+)?"
            r"(PROCEDURE|FUNCTION|PACKAGE(?:\s+BODY)?)\s+([`\"\w$#\.]+)",
            re.IGNORECASE | re.MULTILINE
        )
        
        for match in pattern.finditer(text):
            obj_type = match.group(1).upper()
            obj_name = match.group(2).strip('"`')
            start_pos = match.start()
            
            # Find the end of the object (END <name>;)
            end_pattern = re.compile(
                rf"\bEND\s+{re.escape(obj_name)}\s*;",
                re.IGNORECASE
            )
            end_match = end_pattern.search(text, start_pos)
            end_pos = end_match.end() if end_match else len(text)
            
            obj_text = text[start_pos:end_pos]
            
            objects.append({
                "type": obj_type,
                "name": obj_name,
                "text": obj_text,
                "file": str(self.repo_path)
            })
        
        return objects
    
    def detect_exceptions(self, text: str) -> List[Dict[str, Any]]:
        """MANDATORY: Detect exceptions with ZERO hallucination."""
        exceptions = []
        
        # Pattern 1: raise_application_error(code, message)
        rae_pattern = re.compile(
            r"raise_application_error\s*\(\s*(-?\d+)\s*,\s*([^)]+)\)",
            re.IGNORECASE
        )
        for match in rae_pattern.finditer(text):
            exceptions.append({
                "type": "APPLICATION_ERROR",
                "mechanism": "raise_application_error",
                "error_code": match.group(1),
                "message_expression": match.group(2).strip(),
                "severity": "CUSTOM"
            })
        
        # Pattern 2: RAISE exception_name
        raise_pattern = re.compile(
            r"\bRAISE\s+([A-Za-z_][\w$#]*)\b",
            re.IGNORECASE
        )
        for match in raise_pattern.finditer(text):
            exc_name = match.group(1)
            # Skip if it's part of raise_application_error
            if "raise_application_error" not in text[max(0, match.start()-50):match.start()]:
                exceptions.append({
                    "type": "NAMED_EXCEPTION",
                    "mechanism": "RAISE",
                    "exception_name": exc_name,
                    "severity": "SYSTEM"
                })
        
        # Pattern 3: WHEN exception THEN
        when_pattern = re.compile(
            r"\bWHEN\s+([A-Za-z_][\w$#]*(?:\s+OR\s+[A-Za-z_][\w$#]*)*)\s+THEN",
            re.IGNORECASE
        )
        for match in when_pattern.finditer(text):
            exc_names = match.group(1).split("OR")
            for exc_name in exc_names:
                exceptions.append({
                    "type": "EXCEPTION_HANDLER",
                    "mechanism": "WHEN...THEN",
                    "exception_name": exc_name.strip(),
                    "severity": "CAUGHT"
                })
        
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for exc in exceptions:
            key = (exc.get("type"), exc.get("exception_name", exc.get("error_code", "")))
            if key not in seen:
                seen.add(key)
                unique.append(exc)
        
        return unique
    
    def detect_cursors(self, text: str) -> int:
        """STRICT: Count cursors only if explicit CURSOR, FOR...IN, OPEN/FETCH/CLOSE."""
        cursor_count = 0
        
        # Pattern 1: CURSOR keyword declaration
        cursor_pattern = re.compile(r"\bCURSOR\s+\w+\s+IS", re.IGNORECASE)
        cursor_count += len(cursor_pattern.findall(text))
        
        # Pattern 2: FOR record IN (SELECT ...)
        for_in_pattern = re.compile(r"\bFOR\s+\w+\s+IN\s*\(?\s*SELECT", re.IGNORECASE)
        for_in_count = len(for_in_pattern.findall(text))
        
        # Pattern 3: OPEN/FETCH/CLOSE operations
        open_pattern = re.compile(r"\bOPEN\s+\w+", re.IGNORECASE)
        fetch_pattern = re.compile(r"\bFETCH\s+\w+", re.IGNORECASE)
        close_pattern = re.compile(r"\bCLOSE\s+\w+", re.IGNORECASE)
        
        explicit_ops = (len(open_pattern.findall(text)) + 
                       len(fetch_pattern.findall(text)) + 
                       len(close_pattern.findall(text)))
        
        # Count: explicit CURSOR declarations + FOR...IN + any explicit ops
        if cursor_count > 0 or for_in_count > 0 or explicit_ops > 0:
            cursor_count = max(cursor_count, 1) + for_in_count
        
        return cursor_count
    
    def detect_retry_logic(self, text: str) -> int:
        """STRICT: Count retry only if LOOP, GOTO, or exception retry pattern."""
        retry_count = 0
        
        # Pattern 1: LOOP with EXIT condition and label (retry loop)
        loop_pattern = re.compile(
            r"<<\s*(\w+)\s*>>\s*LOOP.*?EXIT.*?\bEND\s+LOOP",
            re.IGNORECASE | re.DOTALL
        )
        retry_loop_count = len(loop_pattern.findall(text))
        
        # Pattern 2: GOTO retry label
        goto_pattern = re.compile(r"\bGOTO\s+\w+.*?<<\w+>>\s*", re.IGNORECASE | re.DOTALL)
        goto_count = len(goto_pattern.findall(text))
        
        # Pattern 3: Exception handling with re-raise or loop continuation
        exception_retry = re.compile(
            r"WHEN\s+\w+\s+THEN.*?\b(LOOP|GOTO|retry|re_?try)\b",
            re.IGNORECASE | re.DOTALL
        )
        exc_retry_count = len(exception_retry.findall(text))
        
        # Only count if explicit retry patterns found
        retry_count = max(retry_loop_count, goto_count)
        if exc_retry_count > 0:
            retry_count = max(retry_count, 1)
        
        return retry_count
    
    def extract_tables_used(self, text: str) -> Tuple[List[str], Set[str]]:
        """Extract tables from DML (SELECT, INSERT, UPDATE, DELETE)."""
        tables = set()
        operations = set()
        
        # SELECT FROM table
        select_pattern = re.compile(r"\bFROM\s+([A-Za-z_][\w$#]*)", re.IGNORECASE)
        for match in select_pattern.finditer(text):
            table = match.group(1).upper()
            if table not in {"DUAL", "TABLE", "USER_TABLES"}:
                tables.add(table)
                operations.add("SELECT")
        
        # INSERT INTO table
        insert_pattern = re.compile(r"\bINSERT\s+INTO\s+([A-Za-z_][\w$#]*)", re.IGNORECASE)
        for match in insert_pattern.finditer(text):
            table = match.group(1).upper()
            tables.add(table)
            operations.add("INSERT")
        
        # UPDATE table
        update_pattern = re.compile(r"(?<!\bFOR\s)\bUPDATE\s+([A-Za-z_][\w$#]*)", re.IGNORECASE)
        for match in update_pattern.finditer(text):
            table = match.group(1).upper()
            tables.add(table)
            operations.add("UPDATE")
        
        # DELETE FROM table
        delete_pattern = re.compile(r"\bDELETE\s+FROM\s+([A-Za-z_][\w$#]*)", re.IGNORECASE)
        for match in delete_pattern.finditer(text):
            table = match.group(1).upper()
            tables.add(table)
            operations.add("DELETE")
        
        return sorted(tables), operations
    
    def extract_parameters(self, text: str) -> List[Dict[str, Any]]:
        """Extract procedure/function parameters."""
        params = []
        
        # Match parameter definitions
        param_pattern = re.compile(
            r"([A-Za-z_][\w$#]*)\s+(?:(IN|OUT|IN\s+OUT)\s+)?([A-Za-z_][\w$#]*(?:\s*\([^)]*\))?)",
            re.IGNORECASE
        )
        
        # Find parameter section (between function/procedure name and IS/AS)
        func_start = re.search(r"\b(?:FUNCTION|PROCEDURE)\s+\w+\s*\(", text, re.IGNORECASE)
        if func_start:
            paren_start = func_start.end() - 1
            paren_count = 1
            paren_end = paren_start + 1
            while paren_end < len(text) and paren_count > 0:
                if text[paren_end] == '(':
                    paren_count += 1
                elif text[paren_end] == ')':
                    paren_count -= 1
                paren_end += 1
            
            param_text = text[paren_start+1:paren_end-1]
            for part in re.split(r',(?![^()]*\))', param_text):
                match = re.search(
                    r"^\s*(\w+)\s+(?:(IN|OUT|IN\s+OUT)\s+)?(.+?)(?:\s*:=.*)?$",
                    part,
                    re.IGNORECASE
                )
                if match:
                    params.append({
                        "name": match.group(1),
                        "direction": (match.group(2) or "IN").upper(),
                        "datatype": match.group(3).strip()
                    })
        
        return params
    
    def extract_business_logic(self, text: str) -> List[str]:
        """Extract business logic statements (EXACT preservation, no changes)."""
        logic = []
        
        # Extract the body (after IS/AS, before END)
        body_match = re.search(r"\b(?:IS|AS)\s+(.*?)\bEND\b", text, re.IGNORECASE | re.DOTALL)
        if body_match:
            body = body_match.group(1)
            
            # Simple statement extraction (preserve exact code)
            statements = re.split(r';\s*', body)
            for stmt in statements:
                stmt = stmt.strip()
                if stmt and not stmt.upper().startswith("DECLARE"):
                    logic.append(stmt)
        
        return logic[:10]  # Limit to first 10 for brevity
    
    def build_error_handling(self, exceptions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Build error_handling object (never N/A, filled or empty)."""
        if not exceptions:
            return None
        
        # Categorize exceptions
        app_errors = [e for e in exceptions if e["type"] == "APPLICATION_ERROR"]
        named_raises = [e for e in exceptions if e["type"] == "NAMED_EXCEPTION"]
        handlers = [e for e in exceptions if e["type"] == "EXCEPTION_HANDLER"]
        
        return {
            "type": exceptions[0]["severity"] if exceptions else "UNKNOWN",
            "mechanism": exceptions[0]["mechanism"] if exceptions else "UNKNOWN",
            "behavior": {
                "application_errors": len(app_errors),
                "named_exceptions": len(named_raises),
                "exception_handlers": len(handlers),
                "total_exceptions": len(exceptions)
            },
            "details": exceptions[:5]  # Include first 5 exception details
        }
    
    def analyze_object(self, obj: Dict[str, str]) -> Dict[str, Any]:
        """Analyze single PL/SQL object per STRICT RULES."""
        text = obj["text"]
        
        # MANDATORY: Detect exceptions
        exceptions = self.detect_exceptions(text)
        
        # Extract components
        parameters = self.extract_parameters(text)
        tables_used, operations = self.extract_tables_used(text)
        cursors = self.detect_cursors(text)
        retry = self.detect_retry_logic(text)
        business_logic = self.extract_business_logic(text)
        error_handling = self.build_error_handling(exceptions)
        
        # Build CRUD operations
        crud = sorted(operations) if operations else []
        
        return {
            "name": obj["name"],
            "type": obj["type"],
            "parameters": parameters,
            "tables_used": tables_used,
            "crud": crud,
            "business_logic": business_logic[:5],  # First 5 statements
            "exceptions": exceptions,
            "error_handling": error_handling,
            "cursor_count": cursors,
            "retry_count": retry,
            "file": obj["file"]
        }
    
    def detect_schema_ddl(self, text: str) -> Tuple[str, List[Dict[str, str]]]:
        """STRICT: Schema EXISTS only if CREATE TABLE/ALTER TABLE present."""
        tables = []
        
        # CREATE TABLE
        create_table = re.compile(
            r"CREATE\s+TABLE\s+([A-Za-z_][\w$#]*)\s*\(",
            re.IGNORECASE
        )
        for match in create_table.finditer(text):
            tables.append({
                "name": match.group(1).upper(),
                "type": "CREATE TABLE",
                "source": "DDL"
            })
        
        # ALTER TABLE
        alter_table = re.compile(
            r"ALTER\s+TABLE\s+([A-Za-z_][\w$#]*)",
            re.IGNORECASE
        )
        for match in alter_table.finditer(text):
            table_name = match.group(1).upper()
            if not any(t["name"] == table_name for t in tables):
                tables.append({
                    "name": table_name,
                    "type": "ALTER TABLE",
                    "source": "DDL"
                })
        
        status = "DEFINED" if tables else "NOT_FOUND"
        return status, tables
    
    def analyze(self) -> Dict[str, Any]:
        """Main analysis entry point."""
        print("[STRICT PL/SQL ANALYZER] Starting analysis...", file=sys.stderr)
        print(f"  Scope: {self.scope}", file=sys.stderr)
        
        # Collect files
        files = self.collect_sql_files()
        print(f"  Found {len(files)} SQL files", file=sys.stderr)
        
        if not files:
            print("  ⚠ No SQL files found", file=sys.stderr)
            return self.analysis
        
        # Analyze schema DDL first
        all_text = ""
        for filepath in files:
            all_text += self.read_file(filepath) + "\n"
        
        schema_status, schema_tables = self.detect_schema_ddl(all_text)
        self.analysis["schema"] = {
            "status": schema_status,
            "tables": schema_tables
        }
        
        # Analyze each object
        procedures = []
        for filepath in files:
            content = self.read_file(filepath)
            objects = self.extract_objects(content)
            
            for obj in objects:
                print(f"  • Analyzing {obj['type']:12} {obj['name']:30} from {filepath.name}", file=sys.stderr)
                analysis = self.analyze_object(obj)
                procedures.append(analysis)
        
        self.analysis["procedures"] = procedures
        print(f"  Analyzed {len(procedures)} procedures/functions/packages", file=sys.stderr)
        
        return self.analysis


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python strict_plsql_analyzer.py <repo_path> [--object <name>]")
        sys.exit(1)
    
    repo_path = sys.argv[1]
    scope = "OBJECT" if "--object" in sys.argv else "REPO"
    
    if not Path(repo_path).exists():
        print(f"Error: Repository not found at {repo_path}", file=sys.stderr)
        sys.exit(1)
    
    analyzer = StrictPLSQLAnalyzer(repo_path, scope=scope)
    analysis = analyzer.analyze()
    
    # Output JSON
    print(json.dumps(analysis, indent=2))
    
    # Summary
    print(f"\n[SUMMARY]", file=sys.stderr)
    print(f"  Analysis Scope: {analysis['analysis_scope']}", file=sys.stderr)
    print(f"  Schema Status: {analysis['schema']['status']}", file=sys.stderr)
    print(f"  DDL Tables: {len(analysis['schema']['tables'])}", file=sys.stderr)
    print(f"  Procedures Analyzed: {len(analysis['procedures'])}", file=sys.stderr)
    
    exceptions_total = sum(len(p.get("exceptions", [])) for p in analysis["procedures"])
    print(f"  Total Exceptions Detected: {exceptions_total}", file=sys.stderr)
    
    cursors_total = sum(p.get("cursor_count", 0) for p in analysis["procedures"])
    print(f"  Total Cursors: {cursors_total}", file=sys.stderr)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
