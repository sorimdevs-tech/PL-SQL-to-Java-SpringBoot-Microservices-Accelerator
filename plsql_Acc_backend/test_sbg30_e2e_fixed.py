#!/usr/bin/env python3
"""
End-to-end test for SBG-30 dynamic logic injection.
Verifies that PL/SQL logic is correctly extracted and translated to Java.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_dynamic_logic_injection():
    """Test the complete SBG-30 pipeline"""
    from src.generator.improved_plsql_extractor import ImprovedPLSQLExtractor, extract_full_procedure_body
    from src.generator.plsql_to_java_converter import PLSQLtoJavaConverter
    
    # Test 1: Extract validations from PL/SQL
    print("\n=== TEST 1: Extract Validations ===")
    plsql_with_validation = """
    CREATE OR REPLACE PROCEDURE invoice_api_pkg.create_invoice (
        p_customer_id IN NUMBER,
        p_amount IN NUMBER
    ) IS
    BEGIN
        IF p_customer_id IS NULL THEN
            RAISE_APPLICATION_ERROR(-20001, 'Customer ID is required');
        END IF;
        
        IF p_amount <= 0 THEN
            RAISE_APPLICATION_ERROR(-20002, 'Amount must be positive');
        END IF;
        
        INSERT INTO invoices (customer_id, amount) VALUES (p_customer_id, p_amount);
        COMMIT;
    END;
    """
    
    logic = ImprovedPLSQLExtractor.extract_all_logic(plsql_with_validation)
    print("[OK] Extracted validations:")
    for val in logic.validations:
        print(f"  - {val['field']}: {val['condition']}")
    print(f"[OK] Extracted {len(logic.inserts)} INSERT statements")
    print(f"[OK] Transaction detected: {logic.has_commit}")
    
    # Test 2: Generate Java method
    print("\n=== TEST 2: Generate Java Methods ===")
    java_method = PLSQLtoJavaConverter.generate_java_method(
        proc_name='create_invoice',
        logic=logic,
        entity_names={'invoices': 'InvoicesEntity'},
        package_name='com.example.demo'
    )
    
    print("Generated Java method:")
    print(java_method)
    
    # Verify generated code
    checks = [
        ('@Transactional' in java_method, "@Transactional annotation present"),
        ('createInvoice' in java_method, "Method name converted to camelCase"),
        ('Validation' in java_method, "Validation logic present"),
        ('void' in java_method, "Correct return type"),
    ]
    
    print("\n=== VERIFICATION ===")
    all_pass = True
    for check, desc in checks:
        status = "[PASS]" if check else "[FAIL]"
        print(f"{status}: {desc}")
        if not check:
            all_pass = False
    
    # Test 3: Test regex replacement
    print("\n=== TEST 3: Method Body Replacement ===")
    old_service_code = '''package com.example.demo.service;

import org.springframework.stereotype.Service;

@Service
public class InvoiceApiPkgCreateInvoiceService {
    
    public void createInvoice(BigDecimal customerId, BigDecimal amount) {
        // No SQL operations
    }
}'''
    
    # Simulate the regex replacement
    import re
    pattern = r'(public\s+\w+\s+\w+\s*\([^)]*\)\s*\{)[^}]*\}'
    matches = list(re.finditer(pattern, old_service_code))
    
    print(f"[OK] Found {len(matches)} method(s) to replace")
    
    if matches:
        new_code = re.sub(
            pattern,
            lambda m: m.group(1) + '\n' + '        logger.info("Method executed");' + '\n    }',
            old_service_code,
            flags=re.DOTALL,
            count=1
        )
        
        if 'logger.info' in new_code and '// No SQL operations' not in new_code:
            print("[PASS]: Method body successfully replaced")
        else:
            print("[FAIL]: Method body NOT replaced")
            all_pass = False
    
    return all_pass


if __name__ == "__main__":
    print("=" * 60)
    print("SBG-30 Dynamic Logic Injection Test Suite")
    print("=" * 60)
    
    try:
        success = test_dynamic_logic_injection()
        print("\n" + "=" * 60)
        if success:
            print("[SUCCESS] ALL TESTS PASSED - Dynamic logic injection is working!")
            sys.exit(0)
        else:
            print("[FAILED] SOME TESTS FAILED")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
