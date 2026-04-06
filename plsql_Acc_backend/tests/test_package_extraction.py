"""Tests for PL/SQL package procedure extraction."""

import pytest
from src.parser.discovery_analyzer import analyze_sql_source, build_discovery_model


class TestPackageProcedureExtraction:
    """Tests for extracting individual procedures from packages."""
    
    def test_extract_procedures_from_package_body(self):
        """Test that procedures are extracted individually from PACKAGE BODY."""
        sql = """
        CREATE OR REPLACE PACKAGE BODY appl_error_pkg IS
            PROCEDURE assert(p_condition BOOLEAN, p_error_message VARCHAR2) IS
            BEGIN
                IF NOT p_condition THEN
                    RAISE_APPLICATION_ERROR(-20001, p_error_message);
                END IF;
            END assert;
            
            PROCEDURE log_error(p_error_code NUMBER, p_error_message VARCHAR2) IS
            BEGIN
                INSERT INTO error_log (error_code, error_message) 
                VALUES (p_error_code, p_error_message);
            END log_error;
        END appl_error_pkg;
        """
        results = analyze_sql_source(sql)
        
        # Should extract 2 procedures, not 1 package
        assert len(results) == 2, f"Expected 2 procedures, got {len(results)}"
        
        # Check first procedure
        assert results[0]["procedureName"] == "assert"
        assert results[0]["objectType"] == "PROCEDURE"
        assert any(p["name"] == "p_condition" for p in results[0]["parameters"]["in"])
        assert any(p["name"] == "p_error_message" for p in results[0]["parameters"]["in"])
        
        # Check second procedure
        assert results[1]["procedureName"] == "log_error"
        assert results[1]["objectType"] == "PROCEDURE"
        assert any(t.upper() == "ERROR_LOG" for t in results[1]["tablesUsed"])
    
    def test_extract_multiple_procedures_with_operations(self):
        """Test extraction of multiple procedures with different operations."""
        sql = """
        CREATE OR REPLACE PACKAGE BODY customer_pkg IS
            PROCEDURE insert_customer(p_name VARCHAR2, p_email VARCHAR2) IS
            BEGIN
                INSERT INTO customers (name, email) VALUES (p_name, p_email);
            END insert_customer;
            
            PROCEDURE get_customer_balance(p_customer_id NUMBER) RETURN NUMBER IS
                v_balance NUMBER;
            BEGIN
                SELECT balance INTO v_balance 
                FROM customers 
                WHERE customer_id = p_customer_id;
                RETURN v_balance;
            END get_customer_balance;
            
            PROCEDURE update_customer_status(p_customer_id NUMBER, p_status VARCHAR2) IS
            BEGIN
                UPDATE customers 
                SET status = p_status 
                WHERE customer_id = p_customer_id;
            END update_customer_status;
        END customer_pkg;
        """
        results = analyze_sql_source(sql)
        
        # Should extract 3 procedures
        assert len(results) == 3
        
        procedure_names = [r["procedureName"] for r in results]
        assert "insert_customer" in procedure_names
        assert "get_customer_balance" in procedure_names
        assert "update_customer_status" in procedure_names
        
        # Check operations
        for result in results:
            if result["procedureName"] == "insert_customer":
                assert "INSERT" in result["operations"]
                assert any(t.upper() == "CUSTOMERS" for t in result["tablesUsed"])
            elif result["procedureName"] == "update_customer_status":
                assert "UPDATE" in result["operations"]
                assert any(t.upper() == "CUSTOMERS" for t in result["tablesUsed"])
    
    def test_skip_package_spec(self):
        """Test that PACKAGE SPEC (declaration-only) is skipped."""
        sql = """
        CREATE OR REPLACE PACKAGE math_pkg IS
            FUNCTION add(p_a NUMBER, p_b NUMBER) RETURN NUMBER;
            FUNCTION multiply(p_a NUMBER, p_b NUMBER) RETURN NUMBER;
        END math_pkg;
        """
        results = analyze_sql_source(sql)
        
        # PACKAGE SPEC should not produce any procedures
        assert len(results) == 0
    
    def test_mixed_standalone_and_package_procedures(self):
        """Test handling of both standalone and package procedures."""
        sql = """
        CREATE OR REPLACE PROCEDURE standalone_proc IS
        BEGIN
            NULL;
        END standalone_proc;
        
        CREATE OR REPLACE PACKAGE BODY auth_pkg IS
            PROCEDURE validate_user(p_username VARCHAR2) IS
            BEGIN
                NULL;
            END validate_user;
            
            PROCEDURE log_login(p_username VARCHAR2) IS
            BEGIN
                NULL;
            END log_login;
        END auth_pkg;
        """
        results = analyze_sql_source(sql)
        
        # Should extract 1 standalone + 2 package procedures = 3 total
        assert len(results) == 3
        
        names = [r["procedureName"] for r in results]
        assert "standalone_proc" in names
        assert "validate_user" in names
        assert "log_login" in names
    
    def test_package_with_constants(self):
        """Test that package-level constants are included with procedures."""
        sql = """
        CREATE OR REPLACE PACKAGE BODY config_pkg IS
            g_max_attempts CONSTANT NUMBER := 3;
            g_timeout CONSTANT NUMBER := 30;
            
            PROCEDURE check_attempts(p_attempts NUMBER) IS
            BEGIN
                IF p_attempts > g_max_attempts THEN
                    RAISE_APPLICATION_ERROR(-20001, 'Too many attempts');
                END IF;
            END check_attempts;
        END config_pkg;
        """
        results = analyze_sql_source(sql)
        
        # Should extract 1 procedure
        assert len(results) == 1
        assert results[0]["procedureName"] == "check_attempts"
        
        # Should include package constants
        constants = results[0].get("package_constants", [])
        assert len(constants) > 0
        const_names = [c.get("name") for c in constants]
        assert any("max_attempts" in (name or "").lower() for name in const_names)
    
    def test_package_with_function_and_procedure(self):
        """Test extraction of both functions and procedures from package."""
        sql = """
        CREATE OR REPLACE PACKAGE BODY invoice_api_pkg IS
            FUNCTION create_invoice(p_amount NUMBER, p_customer_id NUMBER) RETURN NUMBER IS
                v_invoice_id NUMBER;
            BEGIN
                INSERT INTO invoices (amount, customer_id) VALUES (p_amount, p_customer_id)
                RETURNING invoice_id INTO v_invoice_id;
                RETURN v_invoice_id;
            END create_invoice;
            
            PROCEDURE update_invoice_status(p_invoice_id NUMBER, p_status VARCHAR2) IS
            BEGIN
                UPDATE invoices SET status = p_status WHERE invoice_id = p_invoice_id;
            END update_invoice_status;
            
            FUNCTION get_invoice_amount(p_invoice_id NUMBER) RETURN NUMBER IS
                v_amount NUMBER;
            BEGIN
                SELECT amount INTO v_amount FROM invoices WHERE invoice_id = p_invoice_id;
                RETURN v_amount;
            END get_invoice_amount;
        END invoice_api_pkg;
        """
        results = analyze_sql_source(sql)
        
        # Should extract 3 subprograms (2 functions + 1 procedure)
        assert len(results) == 3
        
        # Verify types
        types = {r["procedureName"]: r["objectType"] for r in results}
        assert types["create_invoice"] == "FUNCTION"
        assert types["update_invoice_status"] == "PROCEDURE"
        assert types["get_invoice_amount"] == "FUNCTION"
        
        # Verify tables are correctly identified
        for result in results:
            assert any(t.upper() == "INVOICES" for t in result["tablesUsed"])
    
    def test_discovery_model_returns_procedures_not_package(self):
        """Test that build_discovery_model returns procedures, not package."""
        sql = """
        CREATE OR REPLACE PACKAGE BODY util_pkg IS
            PROCEDURE proc1 IS BEGIN NULL; END proc1;
            PROCEDURE proc2 IS BEGIN NULL; END proc2;
        END util_pkg;
        """
        model = build_discovery_model(sql)
        
        procedures = model.get("procedures", [])
        assert len(procedures) == 2
        
        # Should have procedure entries, not package entry
        names = [p.get("name") for p in procedures]
        assert "proc1" in names
        assert "proc2" in names
        assert "util_pkg" not in names


class TestParameterExtraction:
    """Tests for parameter extraction from package procedures."""
    
    def test_procedure_parameter_directions(self):
        """Test that IN/OUT parameter directions are correctly extracted."""
        sql = """
        CREATE OR REPLACE PACKAGE BODY proc_params_pkg IS
            PROCEDURE test_proc(
                p_in_param IN VARCHAR2,
                p_out_param OUT NUMBER,
                p_inout_param IN OUT VARCHAR2
            ) IS
            BEGIN
                NULL;
            END test_proc;
        END proc_params_pkg;
        """
        results = analyze_sql_source(sql)
        
        assert len(results) == 1
        proc = results[0]
        
        # Check IN parameters
        in_params = proc["parameters"]["in"]
        assert any(p["name"] == "p_in_param" for p in in_params)
        assert any(p["name"] == "p_inout_param" for p in in_params)
        
        # Check OUT parameters
        out_params = proc["parameters"]["out"]
        assert any(p["name"] == "p_out_param" for p in out_params)
        assert any(p["name"] == "p_inout_param" for p in out_params)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
