#!/usr/bin/env python3
"""
STRICT PL/SQL ANALYSIS REPORT GENERATOR

Generates comprehensive markdown reports from strict analysis JSON output.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any


def generate_report(json_file: Path) -> str:
    """Generate markdown report from JSON analysis."""
    
    with open(json_file) as f:
        analysis = json.load(f)
    
    procedures = analysis.get("procedures", [])
    schema = analysis.get("schema", {})
    
    # Calculate statistics
    total_procedures = len(procedures)
    total_exceptions = sum(len(p.get("exceptions", [])) for p in procedures)
    total_cursors = sum(p.get("cursor_count", 0) for p in procedures)
    total_retries = sum(p.get("retry_count", 0) for p in procedures)
    
    procedures_with_exceptions = sum(1 for p in procedures if p.get("exceptions"))
    procedures_with_cursors = sum(1 for p in procedures if p.get("cursor_count", 0) > 0)
    procedures_with_retries = sum(1 for p in procedures if p.get("retry_count", 0) > 0)
    
    all_tables = set()
    for p in procedures:
        all_tables.update(p.get("tables_used", []))
    
    crud_operations = set()
    for p in procedures:
        crud_operations.update(p.get("crud", []))
    
    # Build report
    report = []
    report.append("# STRICT PL/SQL ANALYSIS REPORT")
    report.append("")
    report.append(f"## Analysis Scope: {analysis.get('analysis_scope', 'UNKNOWN')}")
    report.append("")
    
    # Executive Summary
    report.append("## Executive Summary")
    report.append("")
    report.append(f"- **Procedures Analyzed**: {total_procedures}")
    report.append(f"- **Schema Status**: {schema.get('status', 'UNKNOWN')}")
    report.append(f"- **DDL Tables Found**: {len(schema.get('tables', []))}")
    report.append(f"- **External Tables Used**: {len(all_tables)}")
    report.append(f"- **Total Exceptions**: {total_exceptions} in {procedures_with_exceptions} procedures")
    report.append(f"- **Cursor Usage**: {total_cursors} cursors in {procedures_with_cursors} procedures")
    report.append(f"- **Retry Logic**: {total_retries} retry patterns in {procedures_with_retries} procedures")
    report.append("")
    
    # Schema Information
    report.append("## Schema Information")
    report.append("")
    report.append(f"**Status**: `{schema.get('status')}`")
    report.append("")
    
    if schema.get('tables'):
        report.append("### DDL Tables")
        for table in schema.get('tables', []):
            report.append(f"- `{table.get('name')}` - {table.get('type')}")
    else:
        report.append("**Note**: No CREATE TABLE or ALTER TABLE statements found in source code.")
    report.append("")
    
    # Table Usage Summary
    if all_tables:
        report.append("## Table Usage Summary")
        report.append("")
        report.append(f"**Total External Tables Referenced**: {len(all_tables)}")
        report.append("")
        for table in sorted(all_tables):
            report.append(f"- `{table}`")
        report.append("")
    
    # CRUD Operations
    if crud_operations:
        report.append("## CRUD Operations")
        report.append("")
        report.append(f"**Operations Found**: {', '.join(sorted(crud_operations))}")
        report.append("")
    
    # Procedure Details
    report.append("## Procedure Details")
    report.append("")
    
    for proc in procedures:
        proc_type = proc.get("type", "UNKNOWN")
        proc_name = proc.get("name", "UNKNOWN")
        
        report.append(f"### {proc_name} ({proc_type})")
        report.append("")
        
        # Parameters
        params = proc.get("parameters", [])
        if params:
            report.append("**Parameters**:")
            for param in params:
                direction = param.get("direction", "IN")
                datatype = param.get("datatype", "UNKNOWN")
                report.append(f"- `{param.get('name')}` ({direction} {datatype})")
            report.append("")
        
        # Tables Used
        tables = proc.get("tables_used", [])
        if tables:
            report.append(f"**Tables Used**: {', '.join(f'`{t}`' for t in sorted(tables))}")
            report.append("")
        
        # CRUD Operations
        crud = proc.get("crud", [])
        if crud:
            report.append(f"**CRUD Operations**: {', '.join(sorted(crud))}")
            report.append("")
        
        # Exceptions
        exceptions = proc.get("exceptions", [])
        if exceptions:
            report.append("**Exceptions**:")
            for exc in exceptions:
                exc_type = exc.get("type", "UNKNOWN")
                mechanism = exc.get("mechanism", "UNKNOWN")
                
                if exc_type == "APPLICATION_ERROR":
                    code = exc.get("error_code", "?")
                    msg = exc.get("message_expression", "?")
                    report.append(f"- `raise_application_error({code}, {msg})`")
                elif exc_type == "NAMED_EXCEPTION":
                    exc_name = exc.get("exception_name", "?")
                    report.append(f"- `RAISE {exc_name}` ({mechanism})")
                elif exc_type == "EXCEPTION_HANDLER":
                    exc_name = exc.get("exception_name", "?")
                    report.append(f"- Handler: `WHEN {exc_name} THEN`")
            report.append("")
        
        # Error Handling Summary
        error_handling = proc.get("error_handling")
        if error_handling:
            report.append("**Error Handling**:")
            behavior = error_handling.get("behavior", {})
            report.append(f"- Type: {error_handling.get('type')}")
            report.append(f"- Mechanism: {error_handling.get('mechanism')}")
            report.append(f"- Exception Handlers: {behavior.get('exception_handlers', 0)}")
            report.append("")
        
        # Cursor and Retry Info
        cursors = proc.get("cursor_count", 0)
        retries = proc.get("retry_count", 0)
        
        if cursors > 0 or retries > 0:
            report.append(f"**Cursor Count**: {cursors} | **Retry Logic**: {retries}")
            report.append("")
        
        report.append("---")
        report.append("")
    
    # Statistics
    report.append("## Statistics")
    report.append("")
    report.append(f"| Metric | Count |")
    report.append(f"|--------|-------|")
    report.append(f"| Total Procedures | {total_procedures} |")
    report.append(f"| Procedures with Exceptions | {procedures_with_exceptions} |")
    report.append(f"| Total Exceptions | {total_exceptions} |")
    report.append(f"| Procedures with Cursors | {procedures_with_cursors} |")
    report.append(f"| Total Cursors | {total_cursors} |")
    report.append(f"| Procedures with Retry Logic | {procedures_with_retries} |")
    report.append(f"| Total Retry Patterns | {total_retries} |")
    report.append(f"| Distinct Tables Used | {len(all_tables)} |")
    report.append("")
    
    # Compliance Notes
    report.append("## STRICT ANALYSIS RULES - COMPLIANCE NOTES")
    report.append("")
    report.append("This analysis follows 7 STRICT RULES:")
    report.append("")
    report.append("1. **SCOPE**: Clearly marked as `" + analysis.get("analysis_scope") + "`")
    report.append("2. **SCHEMA RULE**: Schema status = `" + schema.get("status") + "` (only if CREATE TABLE/ALTER TABLE present)")
    report.append("3. **TABLE USAGE**: Extracted from DML operations (SELECT, INSERT, UPDATE, DELETE)")
    report.append("4. **EXCEPTION DETECTION (MANDATORY)**: All exceptions detected - `raise_application_error`, `RAISE`, `WHEN...THEN`")
    report.append("5. **CURSOR DETECTION (STRICT)**: Counted only explicit CURSOR, FOR...IN, OPEN/FETCH/CLOSE")
    report.append("6. **RETRY LOGIC (STRICT)**: Counted only LOOP, GOTO, or exception retry patterns")
    report.append("7. **ERROR HANDLING**: Filled completely or null (never N/A)")
    report.append("")
    report.append("**Key Principle**: Accuracy > Completeness. If unsure, left empty.")
    report.append("")
    
    return "\n".join(report)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python generate_report.py <json_file> [--output <markdown_file>]")
        sys.exit(1)
    
    json_file = Path(sys.argv[1])
    if not json_file.exists():
        print(f"Error: File not found: {json_file}")
        sys.exit(1)
    
    output_file = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_file = Path(sys.argv[idx + 1])
    
    # Generate report
    report = generate_report(json_file)
    
    # Output
    if output_file:
        output_file.write_text(report)
        print(f"Report saved to: {output_file}")
    else:
        print(report)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
