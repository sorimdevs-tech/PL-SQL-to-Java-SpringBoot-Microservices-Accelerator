#!/usr/bin/env python
"""
Test the complete SBG-30 logic extraction flow with the actual classes
"""
import logging
import sys
import os

# Set up paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.generator.dynamic_logic_extractor import (
    PLSQLLogicExtractor, 
    ProcedureSignature, 
    DynamicServiceGenerator
)

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_sbg30_logic')

# Sample PL/SQL code from mortenbra repo
SAMPLE_PLSQL = """
CREATE OR REPLACE PACKAGE invoice_api_pkg IS
  PROCEDURE create_invoice(
    p_customer_id NUMBER,
    p_amount NUMBER,
    p_description VARCHAR2
  );
END invoice_api_pkg;
/

CREATE OR REPLACE PACKAGE BODY invoice_api_pkg IS
  PROCEDURE create_invoice(
    p_customer_id NUMBER,
    p_amount NUMBER,
    p_description VARCHAR2
  ) IS
    v_total NUMBER;
  BEGIN
    -- Validation layer
    IF p_customer_id IS NULL THEN
      RAISE_APPLICATION_ERROR(-20001, 'Customer ID is required');
    END IF;
    
    IF p_amount <= 0 THEN
      RAISE_APPLICATION_ERROR(-20002, 'Amount must be positive');
    END IF;
    
    -- Calculation layer
    v_total := p_amount * 1.15;
    
    -- Insert layer
    INSERT INTO invoices (customer_id, amount, description, total_amount)
    VALUES (p_customer_id, p_amount, p_description, v_total);
    
    COMMIT;
  END create_invoice;
END invoice_api_pkg;
"""

def test_logic_extraction():
    """Test that PL/SQL logic is correctly extracted"""
    logger.info("=" * 80)
    logger.info("Testing SBG-30 Logic Extraction")
    logger.info("=" * 80)
    
    # Extract procedure signature
    proc_sig = PLSQLLogicExtractor.extract_procedure_signature(SAMPLE_PLSQL, 'create_invoice')
    
    if not proc_sig:
        logger.error("❌ Failed to extract procedure signature")
        return False
    
    logger.info(f"✓ Extracted procedure: {proc_sig.name}")
    logger.info(f"  Parameters: {len(proc_sig.parameters)}")
    for param in proc_sig.parameters:
        logger.info(f"    - {param['name']}: {param['type']} ({param['mode']})")
    
    # Extract logic patterns
    logic = PLSQLLogicExtractor.extract_logic_patterns(proc_sig)
    
    logger.info(f"Logic extracted:")
    logger.info(f"  Validations: {len(logic.validates)}")
    for val in logic.validates:
        logger.info(f"    - {val}")
    
    logger.info(f"  Calculations: {len(logic.calculations)}")
    for calc in logic.calculations:
        logger.info(f"    - {calc}")
    
    logger.info(f"  Inserts: {len(logic.inserts)}")
    for insert in logic.inserts:
        logger.info(f"    - {insert}")
    
    logger.info(f"  Transactions: {logic.transactions}")
    
    # Expected results
    has_validation = len(logic.validates) > 0
    has_calculation = len(logic.calculations) > 0
    has_insert = len(logic.inserts) > 0
    has_transaction = logic.transactions
    
    if not (has_validation and has_calculation and has_insert and has_transaction):
        logger.error("❌ NOT ALL LOGIC PATTERNS FOUND")
        logger.error(f"  Validation: {'✓' if has_validation else '✗'}")
        logger.error(f"  Calculation: {'✓' if has_calculation else '✗'}")
        logger.error(f"  Insert: {'✓' if has_insert else '✗'}")
        logger.error(f"  Transaction: {'✓' if has_transaction else '✗'}")
        return False
    
    logger.info("✓ All logic patterns found")
    
    # Generate Java method
    logger.info("\nGenerating Java method...")
    method = DynamicServiceGenerator.generate_service_method(
        proc_sig=proc_sig,
        logic=logic,
        package_name="com.example.service",
        entity_names={"INVOICES": "InvoicesEntity"}
    )
    
    logger.info("Generated method:")
    logger.info(method)
    
    # Check that generated Java has key elements
    has_validation_java = "@Transactional" in method or "if (" in method
    has_operation_java = "Repository" in method or "new " in method or "logger" in method
    
    if not (has_validation_java and has_operation_java):
        logger.error("❌ Java method is missing expected elements")
        return False
    
    logger.info("✓ Java method generated successfully")
    return True

if __name__ == '__main__':
    success = test_logic_extraction()
    logger.info("=" * 80)
    if success:
        logger.info("✓ SBG-30 LOGIC EXTRACTION TEST PASSED")
        exit(0)
    else:
        logger.error("❌ SBG-30 LOGIC EXTRACTION TEST FAILED")
        exit(1)
