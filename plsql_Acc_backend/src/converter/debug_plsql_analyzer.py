"""
DEBUG MODE PL/SQL ANALYZER
Exposes EXACT detection details - no summarization, no hiding
"""

import json
import re
from typing import Dict, List, Any, Tuple
from pathlib import Path


class DebugPLSqlAnalyzer:
    """DEBUG analyzer - exposes all detection steps"""
    
    def __init__(self):
        self.raw_findings = {}
    
    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze single file with full debug output"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return self.analyze_content(content, file_path)
    
    def analyze_content(self, content: str, source: str = "input") -> Dict[str, Any]:
        """STEP 1-5: Full debug analysis"""
        
        # STEP 1: RAW DETECTION
        raw = self._raw_detection(content)
        
        # STEP 2: RAW FLAGS (NO LOGIC)
        flags = self._compute_flags(raw)
        
        # STEP 3: COUNTS (STRICT)
        computed = self._compute_counts(flags)
        
        # STEP 4: Exception output
        exceptions = self._build_exceptions(flags, raw)
        
        # Reasoning notes
        notes = self._generate_notes(flags, computed)
        
        # STEP 5: OUTPUT EVERYTHING
        return {
            "source": source,
            "raw_detection": raw,
            "flags": flags,
            "computed": computed,
            "exceptions": exceptions,
            "notes": notes
        }
    
    def analyze_repository(self, repo_path: str) -> Dict[str, Any]:
        """Analyze repository with comprehensive debug output"""
        repo_dir = Path(repo_path)
        
        # Find all files
        pks_files = sorted(repo_dir.glob("**/*.pks"))
        pkb_files = sorted(repo_dir.glob("**/*.pkb"))
        
        all_files = pks_files + pkb_files
        results = {}
        
        for file_path in all_files:
            file_name = file_path.name
            results[file_name] = self.analyze_file(str(file_path))
        
        return {
            "source": f"repository: {repo_path}",
            "total_files": len(results),
            "files": results
        }
    
    def _raw_detection(self, content: str) -> Dict[str, Any]:
        """STEP 1: Extract EXACTLY what's in code"""
        
        # DML Statements
        select_matches = list(re.finditer(r'\bSELECT\b.*?\bFROM\b\s+(\w+)', content, re.IGNORECASE | re.DOTALL))
        insert_matches = list(re.finditer(r'INSERT\s+INTO\s+(\w+)', content, re.IGNORECASE))
        update_matches = list(re.finditer(r'UPDATE\s+(\w+)', content, re.IGNORECASE))
        delete_matches = list(re.finditer(r'DELETE\s+FROM\s+(\w+)', content, re.IGNORECASE))
        
        select_stmts = [f"SELECT FROM {m.group(1)}" for m in select_matches[:10]]  # Limit to first 10
        insert_stmts = [f"INSERT INTO {m.group(1)}" for m in insert_matches[:10]]
        update_stmts = [f"UPDATE {m.group(1)}" for m in update_matches[:10]]
        delete_stmts = [f"DELETE FROM {m.group(1)}" for m in delete_matches[:10]]
        
        dml_statements = select_stmts + insert_stmts + update_stmts + delete_stmts
        
        # Extract unique table names
        tables = set()
        for m in select_matches + insert_matches + update_matches + delete_matches:
            tables.add(m.group(1))
        
        # Exception patterns
        raise_app_error = list(re.finditer(r'\braise_application_error\s*\(', content, re.IGNORECASE))
        no_data_found = list(re.finditer(r'\bNO_DATA_FOUND\b', content, re.IGNORECASE))
        too_many_rows = list(re.finditer(r'\bTOO_MANY_ROWS\b', content, re.IGNORECASE))
        raise_stmts = list(re.finditer(r'\bRAISE\b', content, re.IGNORECASE))
        exception_blocks = list(re.finditer(r'\bEXCEPTION\b', content, re.IGNORECASE))
        
        exception_patterns = []
        if raise_app_error:
            exception_patterns.append(f"raise_application_error (found {len(raise_app_error)}x)")
        if no_data_found:
            exception_patterns.append(f"NO_DATA_FOUND (found {len(no_data_found)}x)")
        if too_many_rows:
            exception_patterns.append(f"TOO_MANY_ROWS (found {len(too_many_rows)}x)")
        if raise_stmts:
            exception_patterns.append(f"RAISE statements (found {len(raise_stmts)}x)")
        if exception_blocks:
            exception_patterns.append(f"EXCEPTION blocks (found {len(exception_blocks)}x)")
        
        # Cursor signals
        cursor_keyword = list(re.finditer(r'\bCURSOR\b', content, re.IGNORECASE))
        for_select_loop = list(re.finditer(r'\bFOR\s+\w+\s+IN\s*\(?\s*SELECT\b', content, re.IGNORECASE))
        open_stmt = list(re.finditer(r'\bOPEN\s+\w+', content, re.IGNORECASE))
        fetch_stmt = list(re.finditer(r'\bFETCH\s+\w+', content, re.IGNORECASE))
        close_stmt = list(re.finditer(r'\bCLOSE\s+\w+', content, re.IGNORECASE))
        
        cursor_patterns = []
        if cursor_keyword:
            cursor_patterns.append(f"CURSOR keyword (found {len(cursor_keyword)}x)")
        if for_select_loop:
            cursor_patterns.append(f"FOR...IN(SELECT) loop (found {len(for_select_loop)}x)")
        if open_stmt or fetch_stmt or close_stmt:
            cursor_patterns.append(f"OPEN/FETCH/CLOSE (found {len(open_stmt)}x OPEN, {len(fetch_stmt)}x FETCH, {len(close_stmt)}x CLOSE)")
        
        # Loop signals
        loop_keyword = list(re.finditer(r'\bLOOP\b', content, re.IGNORECASE))
        while_keyword = list(re.finditer(r'\bWHILE\b', content, re.IGNORECASE))
        for_keyword = list(re.finditer(r'\bFOR\s+\w+\s+IN\b', content, re.IGNORECASE))
        
        loop_patterns = []
        if loop_keyword:
            loop_patterns.append(f"LOOP keyword (found {len(loop_keyword)}x)")
        if while_keyword:
            loop_patterns.append(f"WHILE keyword (found {len(while_keyword)}x)")
        if for_keyword:
            loop_patterns.append(f"FOR loops (found {len(for_keyword)}x)")
        
        # Retry signals
        goto_keyword = list(re.finditer(r'\bGOTO\s+\w*retry', content, re.IGNORECASE))
        retry_label = list(re.finditer(r'<<\w*retry\w*>>', content, re.IGNORECASE))
        
        retry_patterns = []
        if goto_keyword:
            retry_patterns.append(f"GOTO retry (found {len(goto_keyword)}x)")
        if retry_label:
            retry_patterns.append(f"retry label (found {len(retry_label)}x)")
        
        # Transaction signals
        commit = list(re.finditer(r'\bCOMMIT\b', content, re.IGNORECASE))
        rollback = list(re.finditer(r'\bROLLBACK\b', content, re.IGNORECASE))
        pragma_autonomous = list(re.finditer(r'\bPRAGMA\s+AUTONOMOUS_TRANSACTION\b', content, re.IGNORECASE))
        
        transaction_patterns = []
        if commit:
            transaction_patterns.append(f"COMMIT (found {len(commit)}x)")
        if rollback:
            transaction_patterns.append(f"ROLLBACK (found {len(rollback)}x)")
        if pragma_autonomous:
            transaction_patterns.append(f"PRAGMA AUTONOMOUS_TRANSACTION (found {len(pragma_autonomous)}x)")
        
        return {
            "tables": sorted(list(tables)),
            "dml_statements": dml_statements if dml_statements else ["NOT FOUND"],
            "exception_patterns": exception_patterns if exception_patterns else ["NOT FOUND"],
            "cursor_patterns": cursor_patterns if cursor_patterns else ["NOT FOUND"],
            "loop_patterns": loop_patterns if loop_patterns else ["NOT FOUND"],
            "retry_patterns": retry_patterns if retry_patterns else ["NOT FOUND"],
            "transaction_patterns": transaction_patterns if transaction_patterns else ["NOT FOUND"]
        }
    
    def _compute_flags(self, raw: Dict[str, Any]) -> Dict[str, bool]:
        """STEP 2: Raw flags (NO LOGIC)"""
        
        has_select = "SELECT FROM" in str(raw["dml_statements"])
        has_insert = "INSERT INTO" in str(raw["dml_statements"])
        has_update = "UPDATE" in str(raw["dml_statements"])
        has_delete = "DELETE FROM" in str(raw["dml_statements"])
        
        has_raise_application_error = any("raise_application_error" in p.lower() for p in raw["exception_patterns"])
        has_exception_block = any("EXCEPTION" in p for p in raw["exception_patterns"])
        
        has_cursor_keyword = any("CURSOR keyword" in p for p in raw["cursor_patterns"])
        has_for_select_loop = any("FOR...IN(SELECT)" in p for p in raw["cursor_patterns"])
        has_open_fetch_close = any("OPEN/FETCH" in p for p in raw["cursor_patterns"])
        
        has_loop = any("LOOP keyword" in p for p in raw["loop_patterns"])
        has_while = any("WHILE keyword" in p for p in raw["loop_patterns"])
        has_for_loop = any("FOR loops" in p for p in raw["loop_patterns"])
        
        has_goto = any("GOTO retry" in p for p in raw["retry_patterns"])
        has_retry_label = any("retry label" in p for p in raw["retry_patterns"])
        
        has_commit = any("COMMIT" in p for p in raw["transaction_patterns"])
        has_rollback = any("ROLLBACK" in p for p in raw["transaction_patterns"])
        
        return {
            "has_select": has_select,
            "has_insert": has_insert,
            "has_update": has_update,
            "has_delete": has_delete,
            "has_raise_application_error": has_raise_application_error,
            "has_exception_block": has_exception_block,
            "has_cursor_keyword": has_cursor_keyword,
            "has_for_select_loop": has_for_select_loop,
            "has_open_fetch_close": has_open_fetch_close,
            "has_loop": has_loop,
            "has_while": has_while,
            "has_for_loop": has_for_loop,
            "has_goto": has_goto,
            "has_retry_label": has_retry_label,
            "has_commit": has_commit,
            "has_rollback": has_rollback
        }
    
    def _compute_counts(self, flags: Dict[str, bool]) -> Dict[str, int]:
        """STEP 3: Counts (STRICT)"""
        
        # cursor_count = 1 IF any cursor signal exists, ELSE 0
        cursor_count = 1 if (flags["has_cursor_keyword"] or 
                            flags["has_for_select_loop"] or 
                            flags["has_open_fetch_close"]) else 0
        
        # retry_count = 1 IF (has_loop AND has_goto), ELSE 0
        retry_count = 1 if (flags["has_loop"] and flags["has_goto"]) else 0
        
        return {
            "cursor_count": cursor_count,
            "retry_count": retry_count
        }
    
    def _build_exceptions(self, flags: Dict[str, bool], raw: Dict[str, Any]) -> List[Dict]:
        """STEP 4: Exception output"""
        exceptions = []
        
        # If raise_application_error found
        if flags["has_raise_application_error"]:
            exceptions.append({
                "type": "APPLICATION_ERROR",
                "mechanism": "raise_application_error",
                "detected": True
            })
        
        # If other exception blocks
        if flags["has_exception_block"]:
            if "NO_DATA_FOUND" in str(raw["exception_patterns"]):
                exceptions.append({
                    "type": "NO_DATA_FOUND",
                    "mechanism": "predefined oracle exception",
                    "detected": True
                })
            if "TOO_MANY_ROWS" in str(raw["exception_patterns"]):
                exceptions.append({
                    "type": "TOO_MANY_ROWS",
                    "mechanism": "predefined oracle exception",
                    "detected": True
                })
            if "RAISE statements" in str(raw["exception_patterns"]):
                exceptions.append({
                    "type": "CUSTOM_EXCEPTION",
                    "mechanism": "RAISE statement",
                    "detected": True
                })
        
        return exceptions if exceptions else [{"type": "NO_EXCEPTIONS", "detected": False}]
    
    def _generate_notes(self, flags: Dict[str, bool], computed: Dict[str, int]) -> str:
        """Explain reasoning for counts"""
        notes = []
        
        # Cursor count reasoning
        cursor_signals = [
            ("CURSOR keyword", flags.get("has_cursor_keyword", False)),
            ("FOR...IN(SELECT), loop", flags.get("has_for_select_loop", False)),
            ("OPEN/FETCH/CLOSE", flags.get("has_open_fetch_close", False))
        ]
        
        found_cursor_signals = [s for s, v in cursor_signals if v]
        if found_cursor_signals:
            notes.append(f"cursor_count={computed['cursor_count']}: Found {len(found_cursor_signals)} cursor signal(s): {', '.join(found_cursor_signals)}")
        else:
            notes.append(f"cursor_count={computed['cursor_count']}: No cursor signals found")
        
        # Retry count reasoning
        if computed['retry_count'] > 0:
            notes.append(f"retry_count={computed['retry_count']}: LOOP exists AND GOTO retry pattern found")
        else:
            if flags.get("has_loop"):
                notes.append(f"retry_count={computed['retry_count']}: LOOP exists but NO GOTO retry pattern")
            else:
                notes.append(f"retry_count={computed['retry_count']}: No LOOP keyword found")
        
        return "; ".join(notes)


if __name__ == "__main__":
    analyzer = DebugPLSqlAnalyzer()
    repo = r"c:\projects\plsql_Accelerator\plsql_sample_repo"
    
    result = analyzer.analyze_repository(repo)
    
    print("=" * 100)
    print("DEBUG MODE PL/SQL ANALYZER - REPOSITORY ANALYSIS")
    print("=" * 100)
    print()
    
    print(f"Total files analyzed: {result['total_files']}")
    print()
    
    # Show first 3 files in detail
    file_count = 0
    for file_name, file_result in sorted(result['files'].items()):
        if file_count >= 3:
            print(f"... and {len(result['files']) - 3} more files")
            break
        
        print("=" * 100)
        print(f"FILE: {file_name}")
        print("=" * 100)
        print()
        
        print("RAW DETECTION:")
        print(f"  Tables: {file_result['raw_detection']['tables']}")
        print(f"  DML: {file_result['raw_detection']['dml_statements']}")
        print(f"  Exceptions: {file_result['raw_detection']['exception_patterns']}")
        print(f"  Cursors: {file_result['raw_detection']['cursor_patterns']}")
        print(f"  Loops: {file_result['raw_detection']['loop_patterns']}")
        print(f"  Retry: {file_result['raw_detection']['retry_patterns']}")
        print()
        
        print("FLAGS (TRUE/FALSE):")
        for key, value in sorted(file_result['flags'].items()):
            print(f"  {key}: {value}")
        print()
        
        print("COMPUTED:")
        print(f"  cursor_count: {file_result['computed']['cursor_count']}")
        print(f"  retry_count: {file_result['computed']['retry_count']}")
        print()
        
        print("EXCEPTIONS:")
        for exc in file_result['exceptions']:
            print(f"  - {exc}")
        print()
        
        print("NOTES:")
        print(f"  {file_result['notes']}")
        print()
        
        file_count += 1
    
    # Save full result
    import json
    output_file = r"c:\projects\plsql_Accelerator\debug_mode_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print("=" * 100)
    print(f"Full debug report saved to: {output_file}")
