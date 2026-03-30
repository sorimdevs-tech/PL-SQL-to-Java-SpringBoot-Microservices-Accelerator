#!/usr/bin/env python
"""
Debug the body extraction
"""
import re

SAMPLE_PLSQL = """
CREATE OR REPLACE PACKAGE invoice_api_pkg IS
  PROCEDURE create_invoice(
    p_customer_id NUMBER,
    p_amount NUMBER,
    p_description VARCHAR2
  );
END invoice_api_pkg;
/

CREATE OR REPLACE PACKAGE BODY invoice_api_pkg IS
  PROCEDURE create_invoice(
    p_customer_id NUMBER,
    p_amount NUMBER,
    p_description VARCHAR2
  ) IS
    v_total NUMBER;
  BEGIN
    -- Validation layer
    IF p_customer_id IS NULL THEN
      RAISE_APPLICATION_ERROR(-20001, 'Customer ID is required');
    END IF;
    
    IF p_amount <= 0 THEN
      RAISE_APPLICATION_ERROR(-20002, 'Amount must be positive');
    END IF;
    
    -- Calculation layer
    v_total := p_amount * 1.15;
    
    -- Insert layer
    INSERT INTO invoices (customer_id, amount, description, total_amount)
    VALUES (p_customer_id, p_amount, p_description, v_total);
    
    COMMIT;
  END create_invoice;
END invoice_api_pkg;
"""

proc_name = 'create_invoice'

# Better pattern: look for PROCEDURE/FUNCTION keyword, skip parameters, find BEGIN...END PROCEDURE
# Must handle nested ENDs (END IF, END LOOP, etc.)
# Pattern: match from BEGIN to END [procedure_name] or just END if it's the last one
body_pattern = rf'(?:PROCEDURE|FUNCTION)\s+{re.escape(proc_name)}\s*\([^)]*\)\s*(?:IS|AS)(.*?)(?:END\s+(?:{proc_name}|IF|LOOP|CASE)\s*|END\s*;)'
body_match = re.search(body_pattern, SAMPLE_PLSQL, re.IGNORECASE | re.DOTALL)
if body_match:
    full_body = body_match.group(1)
    # We need to pick out just the procedure body (between BEGIN and END procedure_name)
    # This is tricky with nested ENDs, so let's try a different approach
    begin_idx = SAMPLE_PLSQL.upper().find(f'PROCEDURE {proc_name.upper()}')
    if begin_idx > 0:
        # Find BEGIN after the procedure declaration
        begin_pos = SAMPLE_PLSQL.upper().find('BEGIN', begin_idx)
        if begin_pos > 0:
            # Find corresponding END (tracking depth of nested structures)
            text_after_begin = SAMPLE_PLSQL[begin_pos+5:]
            # For simplicity, just extract until we find END at appropriate level
            # This is complex, so let's use a simpler approach: extract everything between BEGIN and the LAST END
            
            # Find all END keywords and match them with depth
            body = SAMPLE_PLSQL[begin_pos+5:]
            # Count balanced structures
            depth = 0
            for i, char_group in enumerate(zip(body[::4], body[1::4], body[2::4], body[3::4]), 1):
                pass
            # Simplified: just find "END [procname]" or last standalone END
            end_match = re.search(rf'END\s+{proc_name}\s*(?:;|$)', body, re.IGNORECASE | re.DOTALL)
            if end_match:
                body = body[:end_match.start()]
            else:
                # Find last END;
                end_idx = body.upper().rfind('END;')
                if end_idx > 0:
                    body = body[:end_idx]
else:
    body = ""

print(f"Found body with length: {len(body)}")
print(f"Body:\n{body}")
print(f"\nUPPER body:\n{body.upper()}")

# Check if patterns match
validations_pattern = r'IF\s+(.+?)\s+THEN\s+RAISE_APPLICATION_ERROR'
matches = re.findall(validations_pattern, body, re.IGNORECASE | re.MULTILINE | re.DOTALL)
print(f"\nFound {len(matches)} validations (pattern 1)")

# Check INSERT
insert_pattern = r'INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES'
matches = re.findall(insert_pattern, body.upper(), re.IGNORECASE | re.DOTALL)
print(f"Found {len(matches)} INSERTs")
if matches:
    print(f"  {matches}")

# Check COMMIT
commit_pattern = r'(COMMIT|ROLLBACK|PRAGMA|SAVEPOINT)'
if re.search(commit_pattern, body.upper()):
    print("Found COMMIT/ROLLBACK")
