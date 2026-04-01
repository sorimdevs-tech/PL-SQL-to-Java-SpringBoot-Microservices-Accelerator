"""Test to verify FK data flows from backend to frontend API response."""
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.logger import get_logger
from parser.discovery_analyzer import build_discovery_model

logger = get_logger("FK_Frontend_Test")

# Test SQL with FK
SQL_TEXT = """
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

def test_frontend_api_response():
    """Simulate what frontend receives from /api/discovery/analyze endpoint."""
    
    logger.info("=" * 80)
    logger.info("Testing FK data in frontend API response")
    logger.info("=" * 80)
    
    # Build discovery model (same as backend does)
    discovery_model = build_discovery_model(SQL_TEXT)
    
    # Simulate the API response (as returned by /api/discovery/analyze)
    api_response = {
        "procedureName": "",
        "objectType": "",
        "parameters": {"in": [], "out": []},
        "objects": [],
        "discovery": discovery_model,  # This is what gets returned to frontend
        "count": 0,
        "source": "upload"
    }
    
    logger.info("\n1. Full API Response Structure:")
    logger.info(json.dumps(api_response, indent=2)[:2000])
    
    # Frontend extracts schema from discovery
    schema = api_response.get("discovery", {}).get("schema", {})
    logger.info("\n2. Frontend extracts schema from response (analysis?.discovery?.schema):")
    logger.info(f"   Schema keys: {list(schema.keys())}")
    logger.info(f"   Has tables: {'tables' in schema}")
    
    tables = schema.get("tables", [])
    logger.info(f"\n3. Frontend gets tables from schema (globalSchema?.tables):")
    logger.info(f"   Number of tables: {len(tables)}")
    
    for table in tables:
        logger.info(f"\n   Table: {table.get('name')}")
        logger.info(f"     - Columns: {[col['name'] for col in table.get('columns', [])]}")
        logger.info(f"     - Primary keys: {table.get('primary_keys', [])}")
        
        fks = table.get("foreign_keys", [])
        logger.info(f"     - Foreign keys: {len(fks)}")
        
        if fks:
            for fk in fks:
                logger.info(f"       • {table.get('name')}.{fk.get('source_column')} -> {fk.get('target_table')}.{fk.get('target_column')}")
        else:
            logger.info(f"       • [No foreign keys]")
    
    # Alert if ORDERS table doesn't have FKs
    orders_table = next((t for t in tables if t.get("name") == "ORDERS"), None)
    if orders_table:
        fks = orders_table.get("foreign_keys", [])
        if fks:
            logger.info("\n✓ SUCCESS: ORDERS table has foreign_keys in API response")
            return True
        else:
            logger.error("\n✗ FAILURE: ORDERS table has NO foreign_keys in API response")
            logger.error(f"   ORDERS table structure: {json.dumps(orders_table, indent=2)}")
            return False
    else:
        logger.error("\n✗ FAILURE: ORDERS table not found")
        return False


if __name__ == "__main__":
    success = test_frontend_api_response()
    sys.exit(0 if success else 1)
