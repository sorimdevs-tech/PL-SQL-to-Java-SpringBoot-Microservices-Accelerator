#!/usr/bin/env python3
"""Debug parameter extraction."""

import sys
import re
sys.path.insert(0, 'src')

from parser.discovery_analyzer import _prepare_sql_text, _normalize_identifier

test_sql = '''
DECLARE
    p_invoice_id IN NUMBER;
    p_customer_id IN NUMBER;
    p_vat_code IN VARCHAR2;
BEGIN
    INSERT INTO XY_INVOICE (INVOICE_ID, CUSTOMER_ID, VAT_CODE, INVOICE_AMOUNT)
    VALUES (p_invoice_id, p_customer_id, p_vat_code, 100);
END;
/
'''

cleaned = _prepare_sql_text(test_sql)
print("CLEANED SQL:")
print(repr(cleaned))
print("\nDECLARE section:")
# Extract DECLARE block
declare_match = re.search(r'DECLARE(.*?)BEGIN', cleaned, re.IGNORECASE | re.DOTALL)
if declare_match:
    print(declare_match.group(1))

print("\n\nTesting parameter regex:")
pattern = r'\b(?:in|out|in\s+out)\s+(?:nocopy\s+)?(\w+)\s+(?:in\s+)?([A-Z0-9_#\$\.]+)'
for match in re.finditer(pattern, cleaned, re.IGNORECASE):
    print(f"Match: {match.group(0)}")
    print(f"  Param: {match.group(1)}, Type: {match.group(2)}")

print("\n\nTrying simpler pattern for DECLARE variables:")
pattern2 = r'^\s+(\w+)\s+(IN\s+)?(NUMBER|VARCHAR2|DATE|BOOLEAN|CLOB|BLOB|[A-Z0-9_\.]+)'
for match in re.finditer(pattern2, cleaned, re.IGNORECASE | re.MULTILINE):
    print(f"Match: {match.group(0)}")
    print(f"  Var: {match.group(1)}, Type: {match.group(3)}")
