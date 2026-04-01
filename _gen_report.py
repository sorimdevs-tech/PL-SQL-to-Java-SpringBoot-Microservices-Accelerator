#!/usr/bin/env python3
import json
import sys

# Load and verify JSON
try:
    with open("analysis_output.json") as f:
        data = json.load(f)
    print(f"✓ Valid JSON loaded")
    print(f"✓ Procedures: {len(data.get('procedures', []))}")
    print(f"✓ Analysis Scope: {data.get('analysis_scope')}")
    print(f"✓ Schema Status: {data['schema'].get('status')}")
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)

# Generate report
from pathlib import Path
sys.path.insert(0, ".")
from generate_report import generate_report

try:
    report = generate_report(Path("analysis_output.json"))
    Path("PLSQL_ANALYSIS_REPORT.md").write_text(report)
    print(f"✓ Report generated: PLSQL_ANALYSIS_REPORT.md")
    print(f"✓ Report size: {len(report)} bytes")
except Exception as e:
    print(f"✗ Error generating report: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
