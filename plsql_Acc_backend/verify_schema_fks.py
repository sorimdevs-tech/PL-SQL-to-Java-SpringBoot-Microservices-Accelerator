#!/usr/bin/env python
"""Verify that discovery model includes foreign_keys in the schema response"""

import json
from src.parser.discovery_analyzer import build_discovery_model

TEST_SQL = """
CREATE TABLE CUSTOMER (
    CUSTOMER_ID NUMBER PRIMARY KEY,
    CUSTOMER_NAME VARCHAR2(100),
    EMAIL VARCHAR2(100)
);

CREATE TABLE ORDERS (
    ORDER_ID NUMBER PRIMARY KEY,
    CUSTOMER_ID NUMBER,
    ORDER_DATE TIMESTAMP,
    FOREIGN KEY (CUSTOMER_ID) REFERENCES CUSTOMER(CUSTOMER_ID)
);
"""

model = build_discovery_model(TEST_SQL)

print("Discovery Model Schema Output:")
print("=" * 80)
print(json.dumps(model["schema"], indent=2))

print("\n" + "=" * 80)
print("Checking if foreign_keys are in ORDERS table:")
orders_table = next((t for t in model["schema"]["tables"] if t["name"] == "ORDERS"), None)
if orders_table:
    print(f"ORDERS table found")
    print(f"  Columns: {[c['name'] for c in orders_table.get('columns', [])]}")
    print(f"  Primary keys: {orders_table.get('primary_keys', [])}")
    print(f"  Foreign keys: {orders_table.get('foreign_keys', [])}")
else:
    print("ORDERS table NOT found")
