#!/usr/bin/env python3
"""
Test script for STRICT EXTRACTION RULES (7 Rules).

Tests all 7 rules for schema vs external_tables separation.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'plsql_Acc_backend'))

from src.parser.discovery_analyzer import build_discovery_model


def test_rule_1_schema_exists_only_if_ddl():
    """RULE 1: Schema EXISTS only if CREATE TABLE is present."""
    print("\n[TEST RULE 1] Schema exists only if CREATE TABLE")
    
    # Test Case 1: No DDL, only DML
    sql_no_ddl = """
    CREATE OR REPLACE PROCEDURE test_proc IS
    BEGIN
        INSERT INTO customer VALUES (1, 'John');
        SELECT * FROM customer;
    END test_proc;
    """
    
    model = build_discovery_model(sql_no_ddl)
    schema = model.get("schema", {})
    status = schema.get("status")
    
    assert status == "NOT_FOUND", f"Expected 'NOT_FOUND', got '{status}'"
    print(f"  ✓ No DDL → status = 'NOT_FOUND'")
    
    # Test Case 2: With DDL
    sql_with_ddl = """
    CREATE TABLE customer (id NUMBER, name VARCHAR2(100));
    
    CREATE OR REPLACE PROCEDURE test_proc IS
    BEGIN
        INSERT INTO customer VALUES (1, 'John');
    END test_proc;
    """
    
    model = build_discovery_model(sql_with_ddl)
    schema = model.get("schema", {})
    status = schema.get("status")
    
    assert status == "DEFINED", f"Expected 'DEFINED', got '{status}'"
    print(f"  ✓ With DDL → status = 'DEFINED'")


def test_rule_2_schema_populated_if_ddl():
    """RULE 2: If CREATE TABLE exists → Populate schema.tables"""
    print("\n[TEST RULE 2] Schema populated if DDL exists")
    
    sql = """
    CREATE TABLE customer (
        id NUMBER PRIMARY KEY,
        name VARCHAR2(100),
        card_id NUMBER
    );
    
    CREATE TABLE card (
        id NUMBER PRIMARY KEY,
        type VARCHAR2(20)
    );
    """
    
    model = build_discovery_model(sql)
    schema = model.get("schema", {})
    tables = schema.get("tables", [])
    
    assert len(tables) == 2, f"Expected 2 tables, got {len(tables)}"
    table_names = {t.get("name") for t in tables}
    assert "CUSTOMER" in table_names, "CUSTOMER table not found"
    assert "CARD" in table_names, "CARD table not found"
    print(f"  ✓ DDL exists → schema.tables populated with {len(tables)} tables")


def test_rule_3_no_hallucination():
    """RULE 3: If NO CREATE TABLE → schema.status = 'NOT_FOUND', no external_tables"""
    print("\n[TEST RULE 3] No hallucination if no DDL")
    
    sql = """
    CREATE OR REPLACE PROCEDURE test_proc IS
    BEGIN
        INSERT INTO customer VALUES (1, 'John');
        UPDATE orders SET status='SHIPPED' WHERE id=123;
        DELETE FROM archive WHERE date < TRUNC(SYSDATE);
    END test_proc;
    """
    
    model = build_discovery_model(sql)
    schema = model.get("schema", {})
    status = schema.get("status")
    tables = schema.get("tables", [])
    external_tables = schema.get("external_tables", [])
    
    assert status == "NOT_FOUND", f"Expected 'NOT_FOUND', got '{status}'"
    assert len(tables) == 0, f"Expected 0 DDL tables, got {len(tables)}"
    assert len(external_tables) == 0, f"Expected 0 external_tables (NO HALLUCINATION), got {len(external_tables)}"
    print(f"  ✓ No DDL → schema.status='NOT_FOUND', no external_tables (NO HALLUCINATION)")


def test_rule_4_5_external_from_dml():
    """RULE 4-5: External tables from DML with usage tracking"""
    print("\n[TEST RULE 4-5] External tables from DML with usage tracking")
    
    sql = """
    CREATE TABLE item (id NUMBER PRIMARY KEY);
    
    CREATE OR REPLACE PROCEDURE test_proc IS
    BEGIN
        INSERT INTO customer VALUES (1, 'John');
        UPDATE customer SET name='Jane' WHERE id=1;
        SELECT * FROM item INTO v_item FROM item;
        DELETE FROM archive WHERE date < TRUNC(SYSDATE);
    END test_proc;
    """
    
    model = build_discovery_model(sql)
    schema = model.get("schema", {})
    external_tables = schema.get("external_tables", [])
    
    # RULE 4: External tables from DML
    assert len(external_tables) > 0, "Expected external_tables from DML"
    
    # Find CUSTOMER table (appears in DML, no DDL)
    customer_table = [t for t in external_tables if t.get("name") == "CUSTOMER"]
    assert len(customer_table) == 1, "CUSTOMER should be in external_tables"
    
    # RULE 5: Usage array should have operations
    customer = customer_table[0]
    usage = customer.get("usage", [])
    assert isinstance(usage, list), f"Usage should be list, got {type(usage)}"
    assert "INSERT" in usage, f"Expected INSERT in usage, got {usage}"
    assert "UPDATE" in usage, f"Expected UPDATE in usage, got {usage}"
    
    source = customer.get("source")
    assert source == "DML only, no DDL found", f"Unexpected source: {source}"
    print(f"  ✓ CUSTOMER external table: usage={usage}, source='{source}'")
    
    # ARCHIVE should also be external
    archive_table = [t for t in external_tables if t.get("name") == "ARCHIVE"]
    assert len(archive_table) == 1, "ARCHIVE should be in external_tables"
    archive = archive_table[0]
    usage = archive.get("usage", [])
    assert "DELETE" in usage, f"Expected DELETE in usage, got {usage}"
    print(f"  ✓ ARCHIVE external table: usage={usage}")


def test_rule_6_7_no_mixing():
    """RULE 6-7: No mixing of DDL and DML tables"""
    print("\n[TEST RULE 6-7] No mixing of DDL and DML tables")
    
    sql = """
    CREATE TABLE customer (id NUMBER PRIMARY KEY, name VARCHAR2(100));
    CREATE TABLE order_tbl (id NUMBER PRIMARY KEY, customer_id NUMBER);
    
    CREATE OR REPLACE PROCEDURE test_proc IS
    BEGIN
        -- This table has DDL, should NOT be in external_tables
        INSERT INTO customer VALUES (1, 'John');
        UPDATE order_tbl SET customer_id=1 WHERE id=100;
        
        -- This table has no DDL, should be in external_tables
        INSERT INTO audit_log VALUES (SYSDATE, 'INSERT', 'CUSTOMER');
    END test_proc;
    """
    
    model = build_discovery_model(sql)
    schema = model.get("schema", {})
    tables = schema.get("tables", [])
    external_tables = schema.get("external_tables", [])
    
    ddl_names = {t.get("name") for t in tables}
    ext_names = {t.get("name") for t in external_tables}
    
    # RULE 6: No mixing
    intersection = ddl_names & ext_names
    assert len(intersection) == 0, f"RULE 6 VIOLATION: Tables in both: {intersection}"
    print(f"  ✓ No mixing: DDL tables={ddl_names}, external={ext_names}, intersection=empty")
    
    # RULE 7: CUSTOMER and ORDER_TBL have DDL → should be in schema only
    assert "CUSTOMER" in ddl_names, "CUSTOMER should be in schema (has DDL)"
    assert "CUSTOMER" not in ext_names, "CUSTOMER should NOT be in external_tables (has DDL)"
    assert "ORDER_TBL" in ddl_names, "ORDER_TBL should be in schema (has DDL)"
    assert "ORDER_TBL" not in ext_names, "ORDER_TBL should NOT be in external_tables (has DDL)"
    
    # RULE 7: AUDIT_LOG has no DDL → should be in external only
    assert "AUDIT_LOG" not in ddl_names, "AUDIT_LOG should NOT be in schema (no DDL)"
    assert "AUDIT_LOG" in ext_names, "AUDIT_LOG should be in external_tables (no DDL)"
    print(f"  ✓ RULE 7 enforced: DDL-only tables in schema, DML-only in external")


def test_completeness_flags():
    """Verify schema_completeness flags reflect all 7 rules."""
    print("\n[TEST COMPLETENESS FLAGS] Verify all 7 rules in schema_completeness")
    
    sql = """
    CREATE TABLE customer (id NUMBER PRIMARY KEY);
    CREATE OR REPLACE PROCEDURE test_proc IS
    BEGIN
        INSERT INTO external_table VALUES (1);
    END test_proc;
    """
    
    model = build_discovery_model(sql)
    schema = model.get("schema", {})
    completeness = schema.get("schema_completeness", {})
    rules = completeness.get("strict_rule_compliance", {})
    
    # Verify all rule flags exist and are boolean
    assert "rule_1_schema_exists_only_if_ddl" in rules, "rule_1 missing"
    assert "rule_2_schema_populated_if_ddl" in rules, "rule_2 missing"
    assert "rule_3_no_hallucination" in rules, "rule_3 missing"
    assert "rule_4_external_from_dml" in rules, "rule_4 missing"
    assert "rule_5_usage_tracking" in rules, "rule_5 missing"
    assert "rule_6_no_mixing" in rules, "rule_6 missing"
    assert "rule_7_both_dml_ddl_in_schema" in rules, "rule_7 missing"
    
    print(f"  ✓ All 7 rules present in schema_completeness:")
    for rule_name, rule_value in rules.items():
        print(f"     • {rule_name}: {rule_value}")


def main():
    """Run all tests."""
    print("=" * 70)
    print("STRICT EXTRACTION RULES - COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    
    try:
        test_rule_1_schema_exists_only_if_ddl()
        test_rule_2_schema_populated_if_ddl()
        test_rule_3_no_hallucination()
        test_rule_4_5_external_from_dml()
        test_rule_6_7_no_mixing()
        test_completeness_flags()
        
        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED - STRICT RULES ENFORCED")
        print("=" * 70)
        return 0
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
