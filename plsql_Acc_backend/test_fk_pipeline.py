#!/usr/bin/env python
"""End-to-end test: FK extraction → main.py → Spring Boot Generator"""

import sys
import json
from pathlib import Path

# Test SQL with FK defined
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
    ORDER_AMOUNT NUMBER,
    FOREIGN KEY (CUSTOMER_ID) REFERENCES CUSTOMER(CUSTOMER_ID)
);
"""

def test_fk_pipeline():
    """Test FK extraction through discovery_analyzer and entity generation"""
    
    from src.parser.discovery_analyzer import build_discovery_model
    from src.generator.spring_boot_generator import SpringBootGenerator
    
    print("=" * 80)
    print("PHASE 1: FK EXTRACTION VIA discovery_analyzer")
    print("=" * 80)
    
    # Build discovery model from SQL
    discovery = build_discovery_model(TEST_SQL)
    
    print("\n[OK] Discovery model built")
    print("[OK] Tables found: {}".format(len(discovery.get('schema', {}).get('tables', []))))
    
    # Display FKs
    print("\nForeign Keys Extracted:")
    total_fks = 0
    for table in discovery.get("schema", {}).get("tables", []):
        table_name = table.get("name")
        fks = table.get("foreign_keys", [])
        if fks:
            print("  Table: {}".format(table_name))
            for fk in fks:
                print("    - {}.{} -> {}.{}".format(
                    fk.get('source_table'), fk.get('source_column'),
                    fk.get('target_table'), fk.get('target_column')))
                print("      Source: {}, Confidence: {}".format(
                    fk.get('fk_source'), fk.get('confidence')))
                total_fks += 1
    
    if total_fks == 0:
        print("  [WARN] WARNING: No FKs found in discovery model!")
        return False
    
    print("\n[OK] Total FKs extracted: {}".format(total_fks))
    
    print("\n" + "=" * 80)
    print("PHASE 2: FK MAP CONSTRUCTION FOR ENTITY GENERATION")
    print("=" * 80)
    
    # Build FK map like main.py does
    fk_map = {}
    for table in discovery.get("schema", {}).get("tables", []):
        table_name = table.get("name")
        if not table_name:
            continue
        for fk in table.get("foreign_keys", []) or []:
            if table_name.upper() not in fk_map:
                fk_map[table_name.upper()] = []
            fk_map[table_name.upper()].append({
                "column": fk.get("source_column", ""),
                "ref_table": fk.get("target_table", ""),
                "ref_column": fk.get("target_column", ""),
            })
    
    print("\nFK Map constructed:")
    for table, fks in fk_map.items():
        print("  {}: {} FK(s)".format(table, len(fks)))
        for fk in fks:
            print("    - {} -> {}.{}".format(fk['column'], fk['ref_table'], fk['ref_column']))
    
    print("\n" + "=" * 80)
    print("PHASE 3: ENTITY GENERATION WITH FK RELATIONSHIPS")
    print("=" * 80)
    
    # Create Spring Boot generator
    config = {
        "package_name": "com.example.orders",
        "artifact_id": "orders-app",
        "java_version": "17",
        "build_tool": "maven",
        "spring_boot_version": "3.0.0",
        "group_id": "com.example",
        "target_directory": "./test_output"
    }
    
    generator = SpringBootGenerator(config)
    
    # Build DDL columns map
    ddl_columns = {}
    for table in discovery.get("schema", {}).get("tables", []):
        table_name = table.get("name")
        if table_name:
            ddl_columns[table_name.upper()] = list(table.get("columns", []))
    
    print("\nDDL Columns for {} table(s)".format(len(ddl_columns)))
    
    # Generate entities
    entities = generator.generate_entities(
        java_code={},
        ddl_columns=ddl_columns,
        fk_map=fk_map,
        write_files=False
    )
    
    print("\n[OK] Generated {} entity file(s)".format(len(entities)))
    
    # Check for FK annotations in ORDERS entity
    orders_entity = None
    for filename, code in entities.items():
        if "OrdersEntity" in filename or "order" in filename.lower():
            orders_entity = code
            break
    
    if not orders_entity:
        print("[WARN] WARNING: OrdersEntity not found in generated entities!")
        return False
    
    print("\n" + "-" * 80)
    print("Generated ORDERS Entity:")
    print("-" * 80)
    print(orders_entity)
    
    # Verify FK-specific content
    print("\n" + "-" * 80)
    print("FK Verification:")
    print("-" * 80)
    
    checks = [
        ("@ManyToOne", "@ManyToOne annotation present"),
        ("@JoinColumn", "@JoinColumn annotation present"),
        ("CustomerEntity", "CustomerEntity imported/referenced"),
        ("FetchType.LAZY", "LAZY fetch strategy applied"),
    ]
    
    all_passed = True
    for check, description in checks:
        if check in orders_entity:
            print("[PASS] {}".format(description))
        else:
            print("[FAIL] {}".format(description))
            all_passed = False
    
    if all_passed:
        print("\n[SUCCESS] END-TO-END FK PIPELINE TEST PASSED!")
        return True
    else:
        print("\n[FAIL] END-TO-END FK PIPELINE TEST FAILED!")
        return False

if __name__ == "__main__":
    success = test_fk_pipeline()
    sys.exit(0 if success else 1)
