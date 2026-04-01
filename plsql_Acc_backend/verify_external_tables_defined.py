#!/usr/bin/env python
"""Verify external_tables still works when schema IS DEFINED."""

from src.parser.discovery_analyzer import build_discovery_model
import json

code_with_ddl = """
CREATE TABLE CUSTOMER (
    CUSTOMER_ID NUMBER(10) PRIMARY KEY,
    CUSTOMER_NAME VARCHAR2(100),
    EMAIL VARCHAR2(100)
);

CREATE TABLE PAYMENT (
    PAYMENT_ID NUMBER(10) PRIMARY KEY,
    CUSTOMER_ID NUMBER(10) REFERENCES CUSTOMER(CUSTOMER_ID),
    AMOUNT NUMBER(10,2)
);

CREATE PROCEDURE PROCESS_PAYMENTS IS
BEGIN
    -- Process payments and audit logs
    INSERT INTO PAYMENT_AUDIT (payment_id, action_date)
    SELECT payment_id, SYSDATE FROM PAYMENT WHERE status = 'PENDING';
    
    UPDATE CUSTOMER_BALANCE
    SET last_updated = SYSDATE;
    
    DELETE FROM PAYMENT_STAGING WHERE processed = 1;
END;
/
"""

print("=" * 80)
print("VERIFICATION: external_tables works when schema IS DEFINED")
print("=" * 80)

model = build_discovery_model(code_with_ddl)
schema = model['schema']

print(f"\nSchema Status: {schema['status']}")
print(f"DDL Tables: {len(schema['tables'])}")
print(f"  - DDL Tables: {[t['name'] for t in schema['tables']]}")
print(f"\nExternal Tables: {len(schema['external_tables'])}")
if schema['external_tables']:
    for ext in schema['external_tables']:
        print(f"  - {ext['name']}: {ext['reason']}")

print("\n[TEST RESULTS]")
checks = {
    "schema.status is DEFINED": schema['status'] == 'DEFINED',
    "DDL tables detected": len(schema['tables']) == 2,  # CUSTOMER, PAYMENT
    "external_tables populated": len(schema['external_tables']) > 0,
    "external tables correct": set(t['name'] for t in schema['external_tables']) >= {'PAYMENT_AUDIT', 'CUSTOMER_BALANCE', 'PAYMENT_STAGING'},
}

all_pass = True
for check_name, result in checks.items():
    status = "[OK]" if result else "[XX]"
    print(f"  {status} {check_name}: {result}")
    if not result:
        all_pass = False

print("\n" + "=" * 80)
if all_pass:
    print("RESULT: external_tables correctly shown when schema DEFINED")
    print("  - DDL tables (CUSTOMER, PAYMENT) in schema.tables")
    print("  - DML-only tables in external_tables")
    print("  - external_tables NOT empty when schema DEFINED")
else:
    print("RESULT: ISSUE DETECTED")
print("=" * 80)
