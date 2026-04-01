#!/usr/bin/env python
"""Simulate the complete API response that frontend receives."""
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

CREATE OR REPLACE PROCEDURE process_orders IS
BEGIN
    SELECT * FROM ORDERS WHERE CUSTOMER_ID = 1;
END;
/
"""

def test():
    print("=" * 80)
    print("Simulating Frontend API Response /api/discovery/analyze")
    print("=" * 80)
    
    discovery_model = build_discovery_model(SQL_WITH_FK)
    
    # Simulate the exact response from /api/discovery/analyze endpoint (line 1151 in app.py)
    api_response = {
        "procedureName": "process_orders",
        "objectType": "PROCEDURE",
        "objects": [],
        "discovery": discovery_model,  # This is the key field
        "count": 0,
        "source": "upload"
    }
    
    print("\n1. API Response top-level keys:")
    print(f"   {list(api_response.keys())}")
    
    # Simulate what frontend does at line 1322:
    # const globalSchema: SqlDiscoverySchema | null = analysis?.discovery?.schema ?? null
    print("\n2. Frontend extraction: analysis?.discovery?.schema")
    analysis = api_response  # This is what comes back from fetch()
    discovery = analysis.get("discovery")
    schema = discovery.get("schema") if discovery else None
    
    print(f"   analysis exists: {analysis is not None}")
    print(f"   discovery exists: {discovery is not None}")
    print(f"   schema exists: {schema is not None}")
    print(f"   schema keys: {list(schema.keys()) if schema else 'N/A'}")
    
    # Extract tables
    print("\n3. Frontend extraction: globalSchema?.tables")
    tables = schema.get("tables", []) if schema else []
    print(f"   Tables: {len(tables)}")
    for table in tables:
        print(f"     - {table.get('name')}: {len(table.get('foreign_keys', []))} FKs")
    
    # Find ORDERS and select it
    print("\n4. Frontend selection: selectedSchemaTable = globalTables.find(t => t.name === 'ORDERS')")
    selected_table = next((t for t in tables if t.get("name") == "ORDERS"), None)
    if selected_table:
        print(f"   Found ORDERS table")
        print(f"   Foreign keys: {selected_table.get('foreign_keys', [])}")
        
        # Check rendering condition
        print("\n5. Frontend rendering: (selectedSchemaTable?.foreign_keys ?? []).length > 0")
        fks = selected_table.get("foreign_keys", [])
        print(f"   Condition result: {len(fks) > 0}")
        if fks:
            print(f"   Will render {len(fks)} FK(s):")
            for fk in fks:
                print(f"     • {selected_table.get('name')}.{fk.get('source_column')} -> {fk.get('target_table')}.{fk.get('target_column')}")
            print("\n✓ SUCCESS: FKs should display in frontend")
            return True
        else:
            print("   ✗ No FKs to render!")
            return False
    else:
        print("   ✗ ORDERS table not found!")
        return False


if __name__ == "__main__":
    success = test()
    sys.exit(0 if success else 1)
