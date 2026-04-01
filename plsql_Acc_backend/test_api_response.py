#!/usr/bin/env python
"""Direct test of API response structure with FKs."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser.discovery_analyzer import build_discovery_model

SQL_WITH_FK = """
CREATE TABLE CUSTOMER (
    CUSTOMER_ID NUMBER PRIMARY KEY,
    CUSTOMER_NAME VARCHAR2(100),
    EMAIL VARCHAR2(100)
);

CREATE TABLE ORDERS (
    ORDER_ID NUMBER PRIMARY KEY,
    CUSTOMER_ID NUMBER REFERENCES CUSTOMER(CUSTOMER_ID),
    ORDER_DATE TIMESTAMP
);
"""

def test():
    print("=" * 80)
    print("Testing API Response with Foreign Keys")
    print("=" * 80)
    
    discovery_model = build_discovery_model(SQL_WITH_FK)
    
    # This is what gets returned as "discovery" field in API response
    print("\n1. Discovery Model Structure:")
    print(json.dumps({
        "status": "SUCCESS",
        "schema_keys": list(discovery_model.get("schema", {}).keys()),
    }, indent=2))
    
    # Check tables in schema
    schema = discovery_model.get("schema", {})
    tables = schema.get("tables", [])
    
    print(f"\n2. Number of tables: {len(tables)}")
    for table in tables:
        print(f"\n   Table: {table.get('name')}")
        print(f"     - Columns: {[c['name'] for c in table.get('columns', [])]}")
        print(f"     - Primary keys: {table.get('primary_keys', [])}")
        print(f"     - Foreign keys count: {len(table.get('foreign_keys', []))}")
        if table.get('foreign_keys'):
            for fk in table.get('foreign_keys'):
                print(f"       • {fk.get('source_column')} -> {fk.get('target_table')}.{fk.get('target_column')}")
    
    # Find ORDERS table
    orders = next((t for t in tables if t.get("name") == "ORDERS"), None)
    if not orders:
        print("\n✗ ERROR: ORDERS table not found")
        return False
    
    fks = orders.get("foreign_keys", [])
    print(f"\n3. ORDERS table foreign_keys field:")
    print(f"   Type: {type(fks)}")
    print(f"   Length: {len(fks)}")
    print(f"   Content: {json.dumps(fks, indent=2)}")
    
    if fks:
        print(f"\n✓ SUCCESS: ORDERS has {len(fks)} foreign key(s)")
        return True
    else:
        print(f"\n✗ FAILURE: ORDERS has NO foreign keys")
        print(f"\nFull ORDERS table structure:")
        print(json.dumps(orders, indent=2))
        return False


if __name__ == "__main__":
    success = test()
    sys.exit(0 if success else 1)
