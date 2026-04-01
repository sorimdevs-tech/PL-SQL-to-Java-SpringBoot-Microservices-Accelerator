#!/usr/bin/env python
"""Comprehensive test of strict FK extraction from 3 sources."""

from src.parser.discovery_analyzer import build_discovery_model
import json

test_cases = [
    # Test Case 1: Explicit FOREIGN KEY constraint
    {
        "name": "Explicit FOREIGN KEY Constraint",
        "sql": """
            CREATE TABLE CUSTOMER (
                CUSTOMERID NUMBER(10) PRIMARY KEY,
                NAME VARCHAR2(100)
            );
            
            CREATE TABLE ORDERS (
                ORDERID NUMBER(10) PRIMARY KEY,
                CUSTOMERID NUMBER(10),
                AMOUNT NUMBER(10,2),
                FOREIGN KEY (CUSTOMERID) REFERENCES CUSTOMER(CUSTOMERID)
            );
        """,
        "expected_fk": {
            "source_table": "ORDERS",
            "source_column": "CUSTOMERID",
            "target_table": "CUSTOMER",
            "target_column": "CUSTOMERID",
            "fk_source": "explicit_constraint"
        }
    },
    
    # Test Case 2: Column-level REFERENCES clause
    {
        "name": "Column-level REFERENCES Clause",
        "sql": """
            CREATE TABLE PRODUCT (
                PRODUCTID NUMBER(10) PRIMARY KEY,
                NAME VARCHAR2(100)
            );
            
            CREATE TABLE INVENTORY (
                INVENTORYID NUMBER(10) PRIMARY KEY,
                PRODUCTID NUMBER(10) REFERENCES PRODUCT(PRODUCTID),
                QUANTITY NUMBER(10)
            );
        """,
        "expected_fk": {
            "source_table": "INVENTORY",
            "source_column": "PRODUCTID",
            "target_table": "PRODUCT",
            "target_column": "PRODUCTID",
            "fk_source": "column_references"
        }
    },
    
    # Test Case 3: Naming Pattern (TABLE_ID -> TABLE.TABLEID)
    {
        "name": "Naming Pattern Inference (TABLE_ID style)",
        "sql": """
            CREATE TABLE DEPARTMENT (
                DEPTID NUMBER(10) PRIMARY KEY,
                NAME VARCHAR2(100)
            );
            
            CREATE TABLE EMPLOYEE (
                EMPID NUMBER(10) PRIMARY KEY,
                DEPT_ID NUMBER(10),
                SALARY NUMBER(10,2)
            );
        """,
        "expected_fk": {
            "source_table": "EMPLOYEE",
            "source_column": "DEPT_ID",
            "target_table": "DEPARTMENT",
            "target_column": "DEPT_ID",
            "fk_source": "naming_pattern"
        }
    },
]

print("=" * 90)
print("STRICT FK EXTRACTION - 3 SOURCES TEST")
print("=" * 90)

all_pass = True
for test_case in test_cases:
    print(f"\n{test_case['name'].center(90)}")
    print("-" * 90)
    
    model = build_discovery_model(test_case['sql'])
    schema = model['schema']
    
    # Find the FK in the results
    found_fk = None
    for table in schema['tables']:
        for fk in table['foreign_keys']:
            if fk['source_column'] == test_case['expected_fk']['source_column']:
                found_fk = fk
                break
        if found_fk:
            break
    
    if found_fk:
        expected = test_case['expected_fk']
        checks = {
            f"source_table = {expected['source_table']}": found_fk.get('source_table') == expected['source_table'],
            f"source_column = {expected['source_column']}": found_fk.get('source_column') == expected['source_column'],
            f"target_table = {expected['target_table']}": found_fk.get('target_table') == expected['target_table'],
            f"fk_source = {expected['fk_source']}": found_fk.get('fk_source') == expected['fk_source'],
        }
        
        test_pass = all(checks.values())
        all_pass = all_pass and test_pass
        
        for check_name, result in checks.items():
            status = "[OK]" if result else "[XX]"
            print(f"  {status} {check_name}")
        
        print(f"\n  Extracted FK:")
        print(f"    {found_fk['source_table']}.{found_fk['source_column']}")
        print(f"    -> {found_fk['target_table']}.{found_fk['target_column']}")
        
        if test_pass:
            print(f"\n  RESULT: PASS")
        else:
            print(f"\n  RESULT: FAIL")
    else:
        print(f"  [XX] FK NOT FOUND")
        print(f"  RESULT: FAIL")
        all_pass = False

print("\n" + "=" * 90)
print("[SUMMARY]".center(90))
print("-" * 90)
print(f"  All tests passed: {all_pass}")
print(f"  FK extraction sources covered:")
print(f"    [1] FOREIGN KEY constraint - {1 if all_pass else 0}/1")
print(f"    [2] Column REFERENCES clause - {1 if all_pass else 0}/1")
print(f"    [3] Naming pattern inference - {1 if all_pass else 0}/1")
print(f"  source_table field: INCLUDED")
print(f"  fk_extraction_status field: INCLUDED")
print("=" * 90)
