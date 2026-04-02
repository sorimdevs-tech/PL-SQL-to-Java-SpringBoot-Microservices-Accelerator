#!/usr/bin/env python3
"""
Comprehensive test of the 5 FK inference fixes using realistic test cases.
"""

from src.parser.discovery_analyzer import _infer_implied_foreign_keys


def create_test(name, tables_dict, sql_text, params_list, expected_fks):
    """
    Test a FK inference scenario.
    
    Args:
    - expected_fks: list of tuples (from_table, from_col, to_table, to_col)
    """
    print(f"\n{'='*70}")
    print(f"TEST: {name}")
    print(f"{'='*70}")
    
    detected = _infer_implied_foreign_keys(sql_text, tables_dict, params_list)
    
    detected_keys = {(fk["from_table"], fk["from_column"], fk["to_table"], fk["to_column"]) 
                     for fk in detected}
    expected_keys = set(expected_fks)
    
    print(f"\nExpected FKs: {len(expected_keys)}")
    for exp in expected_keys:
        status = "✓" if exp in detected_keys else "✗"
        print(f"  {status} {exp[0]}.{exp[1]} → {exp[2]}.{exp[3]}")
    
    print(f"\nDetected FKs: {len(detected)}")
    for fk in detected:
        key = (fk["from_table"], fk["from_column"], fk["to_table"], fk["to_column"])
        status = "✓" if key in expected_keys else "⚠"
        conf = fk.get("confidence", "?")
        print(f"  {status} {key[0]}.{key[1]} → {key[2]}.{key[3]} [{conf}]")
    
    # Self-reference check (FIX 1)
    self_refs = [fk for fk in detected if fk["from_table"] == fk["to_table"]]
    if self_refs:
        print(f"\n❌ FIX 1 VIOLATION: Found {len(self_refs)} self-referencing FKs!")
        return False
    
    passed = expected_keys == detected_keys
    result = "✓ PASS" if passed else "✗ FAIL"
    print(f"\n{result}")
    
    return passed


# ============================================================================
# TEST 1: Parameter Threading with Ownership Detection (FIX 2 + FIX 5)
# ============================================================================

def test_parameter_threading():
    tables = {
        "XY_CUSTOMER": {
            "columns": [{"name": "CUSTOMER_ID"}, {"name": "CUSTOMER_NAME"}]
        },
        "XY_INVOICE": {
            "columns": [{"name": "INVOICE_ID"}, {"name": "CUSTOMER_ID"}, {"name": "AMOUNT"}]
        },
    }
    
    sql = """
    PROCEDURE create_invoice(p_customer_id IN NUMBER, p_amount IN NUMBER) AS
    BEGIN
        INSERT INTO xy_invoice(customer_id, amount) 
        VALUES (p_customer_id, p_amount);
    END;
    """
    
    params = [{"name": "P_CUSTOMER_ID"}, {"name": "P_AMOUNT"}]
    expected = [
        ("XY_INVOICE", "CUSTOMER_ID", "XY_CUSTOMER", "CUSTOMER_ID")
    ]
    
    return create_test("Parameter Threading (FIX 2+5)", tables, sql, params, expected)


# ============================================================================
# TEST 2: Shared Column Detection (FIX 1 + FIX 5)
# ============================================================================

def test_shared_column():
    tables = {
        "XY_STATUS": {
            "columns": [{"name": "STATUS_ID"}, {"name": "STATUS_NAME"}]
        },
        "XY_ORDER": {
            "columns": [{"name": "ORDER_ID"}, {"name": "STATUS_ID"}, {"name": "AMOUNT"}]
        },
    }
    
    sql = """
    PROCEDURE apply_status(p_order_id IN NUMBER, p_status_id IN NUMBER) AS
    BEGIN
        INSERT INTO xy_order(status_id, amount) VALUES (p_status_id, 100);
        SELECT * FROM xy_status WHERE status_id = p_status_id;
    END;
    """
    
    params = [{"name": "P_ORDER_ID"}, {"name": "P_STATUS_ID"}]
    expected = [
        ("XY_ORDER", "STATUS_ID", "XY_STATUS", "STATUS_ID")
    ]
    
    return create_test("Shared Column Detection (FIX 1+5)", tables, sql, params, expected)


# ============================================================================
# TEST 3: Absolute Self-Reference Prevention (FIX 1)
# ============================================================================

def test_self_reference_blocker():
    tables = {
        "XY_EMPLOYEE": {
            "columns": [
                {"name": "EMPLOYEE_ID"}, 
                {"name": "MANAGER_ID"},  # Foreign key to same table!
                {"name": "EMPLOYEE_NAME"}
            ]
        },
    }
    
    sql = """
    PROCEDURE update_manager(p_employee_id IN NUMBER, p_manager_id IN NUMBER) AS
    BEGIN
        UPDATE xy_employee SET manager_id = p_manager_id 
        WHERE employee_id = p_employee_id;
    END;
    """
    
    params = [{"name": "P_EMPLOYEE_ID"}, {"name": "P_MANAGER_ID"}]
    
    # Self-references should NOT be detected
    expected = []
    
    return create_test("Self-Reference Blocker (FIX 1)", tables, sql, params, expected)


# ============================================================================
# TEST 4: Multi-Table FK Detection (FIX 4 Direction)
# ============================================================================

def test_direction_multiple_tables():
    tables = {
        "XY_COMPANY": {
            "columns": [{"name": "COMPANY_ID"}, {"name": "COMPANY_NAME"}]
        },
        "XY_DEPARTMENT": {
            "columns": [{"name": "DEPARTMENT_ID"}, {"name": "COMPANY_ID"}, {"name": "DEPT_NAME"}]
        },
        "XY_EMPLOYEE": {
            "columns": [{"name": "EMPLOYEE_ID"}, {"name": "DEPARTMENT_ID"}, {"name": "EMP_NAME"}]
        },
    }
    
    sql = """
    PROCEDURE hiring(p_company_id IN NUMBER, p_dept_id IN NUMBER, p_emp_name IN VARCHAR2) AS
    BEGIN
        -- Create department link
        INSERT INTO xy_department(company_id) VALUES (p_company_id);
        
        -- Create employee link
        INSERT INTO xy_employee(department_id, emp_name) VALUES (p_dept_id, p_emp_name);
        
        -- Verify company exists
        SELECT * FROM xy_company WHERE company_id = p_company_id;
        
        -- Verify dept exists
        SELECT * FROM xy_department WHERE department_id = p_dept_id;
    END;
    """
    
    params = [
        {"name": "P_COMPANY_ID"}, 
        {"name": "P_DEPT_ID"}, 
        {"name": "P_EMP_NAME"}
    ]
    
    expected = [
        ("XY_DEPARTMENT", "COMPANY_ID", "XY_COMPANY", "COMPANY_ID"),
        ("XY_EMPLOYEE", "DEPARTMENT_ID", "XY_DEPARTMENT", "DEPARTMENT_ID"),
    ]
    
    return create_test("Multi-Table FK Direction (FIX 4)", tables, sql, params, expected)


# ============================================================================
# TEST 5: Complex Ownership (FIX 5 - Semantic Matching)
# ============================================================================

def test_complex_ownership():
    tables = {
        "XY_PRODUCT": {
            "columns": [{"name": "PRODUCT_ID"}, {"name": "PRODUCT_NAME"}]
        },
        "XY_INVENTORY": {
            "columns": [{"name": "PRODUCT_ID"}, {"name": "QUANTITY"}]
        },
        "XY_ORDER": {
            "columns": [{"name": "ORDER_ID"}, {"name": "PRODUCT_ID"}, {"name": "QTY"}]
        },
    }
    
    sql = """
    PACKAGE product_mgmt AS
    
    FUNCTION add_product(p_name VARCHAR2) RETURN NUMBER AS
    BEGIN
        INSERT INTO xy_product(product_name) VALUES (p_name)
        RETURNING product_id INTO l_id;
        RETURN l_id;
    END;
    
    PROCEDURE order_product(p_product_id IN NUMBER, p_qty IN NUMBER) AS
        l_inventory NUMBER;
    BEGIN
        SELECT quantity INTO l_inventory FROM xy_inventory 
        WHERE product_id = p_product_id;
        
        INSERT INTO xy_order(product_id, qty) VALUES (p_product_id, p_qty);
    END;
    
    END product_mgmt;
    """
    
    params = [{"name": "P_PRODUCT_ID"}, {"name": "P_QTY"}]
    
    expected = [
        ("XY_INVENTORY", "PRODUCT_ID", "XY_PRODUCT", "PRODUCT_ID"),
        ("XY_ORDER", "PRODUCT_ID", "XY_PRODUCT", "PRODUCT_ID"),
    ]
    
    return create_test("Complex Ownership (FIX 5)", tables, sql, params, expected)


if __name__ == "__main__":
    print("\n" + "#"*70)
    print("# FK INFERENCE TESTS - ALL 5 FIXES")
    print("#"*70)
    
    tests = [
        ("Test 1", test_parameter_threading),
        ("Test 2", test_shared_column),
        ("Test 3", test_self_reference_blocker),
        ("Test 4", test_direction_multiple_tables),
        ("Test 5", test_complex_ownership),
    ]
    
    results = {}
    for testname, testfunc in tests:
        try:
            results[testname] = testfunc()
        except Exception as e:
            print(f"\n❌ ERROR in {testname}: {e}")
            import traceback
            traceback.print_exc()
            results[testname] = False
    
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    
    for testname, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} {testname}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*70 + "\n")
