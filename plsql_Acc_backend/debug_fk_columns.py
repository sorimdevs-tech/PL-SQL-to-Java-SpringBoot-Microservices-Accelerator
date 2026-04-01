#!/usr/bin/env python
"""Debug FK list for entities"""

from src.parser.discovery_analyzer import build_discovery_model

TEST_SQL = """
CREATE TABLE CUSTOMER (
    CUSTOMER_ID NUMBER PRIMARY KEY,
    CUSTOMER_NAME VARCHAR2(100) NOT NULL,
    EMAIL VARCHAR2(100),
    CREATED_AT TIMESTAMP DEFAULT SYSDATE
);

CREATE TABLE ORDERS (
    ORDER_ID NUMBER PRIMARY KEY,
    CUSTOMER_ID NUMBER NOT NULL,
    ORDER_DATE TIMESTAMP DEFAULT SYSDATE,
    ORDER_AMOUNT NUMBER(10,2),
    STATUS VARCHAR2(20),
    FOREIGN KEY (CUSTOMER_ID) REFERENCES CUSTOMER(CUSTOMER_ID)
);

CREATE TABLE ORDER_ITEMS (
    ITEM_ID NUMBER PRIMARY KEY,
    ORDER_ID NUMBER NOT NULL,
    PRODUCT_ID NUMBER,
    QUANTITY NUMBER,
    PRICE NUMBER(10,2),
    FOREIGN KEY (ORDER_ID) REFERENCES ORDERS(ORDER_ID)
);
"""

discovery = build_discovery_model(TEST_SQL)

print("FK Analysis:")
print("=" * 80)
for table in discovery.get("schema", {}).get("tables", []):
    table_name = table.get("name")
    print(f"\nTable: {table_name}")
    print(f"  Columns: {[c['name'] for c in table.get('columns', [])]}")
    print(f"  Foreign Keys (from schema):")
    for fk in table.get("foreign_keys", []):
        print(f"    {fk.get('source_table')}.{fk.get('source_column')} → {fk.get('target_table')}.{fk.get('target_column')}")
        print(f"    Source: {fk.get('fk_source')}")
    
print("\n" + "=" * 80)
print("FK Columns that will be SKIPPED in _generate_entity_from_ddl:")
print("=" * 80)

for table in discovery.get("schema", {}).get("tables", []):
    table_name = table.get("name")
    fk_columns = set()
    for fk in table.get("foreign_keys", []):
        fk_columns.add(fk.get("source_column", "").upper())
    
    if fk_columns:
        print(f"\n{table_name}: {fk_columns}")
    else:
        print(f"\n{table_name}: (no FKs)")
