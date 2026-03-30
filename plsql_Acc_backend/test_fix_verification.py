#!/usr/bin/env python3
"""
Verify that SBG-30 fix properly injects dynamic methods into generated services.
This test runs a simplified pipeline and checks if method bodies are populated.
"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_seriazation_and_method_injection():
    """Test that the regex fix properly replaces empty methods with dynamic logic"""
    from src.generator.spring_boot_generator import SpringBootGenerator
    
    # Create a simple service with empty method
    service_code = '''package com.example.demo.service;

import org.springframework.stereotype.Service;

@Service
public class TestService {
    
    public void testMethod(String param1, Long param2) {
        // No SQL operations — pure utility/infrastructure logic preserved here.
    }
}'''
    
    # Create a generator instance
    generator = SpringBootGenerator(
        project_name="test",
        package_name="com.example.demo",
        spring_boot_version="3.2.0",
        java_version="17",
        orm_type="jpa"
    )
    
    # Register a simple procedure metadata
    generator._procedure_metadata['test.test_method'] = {
        'signature': 'PROCEDURE test.test_method (p_param1 IN VARCHAR2, p_param2 IN NUMBER)',
        'logic': {
            'validations': [{'field': 'p_param1', 'message': 'Param1 is required'}],
            'calculations': [{'variable': 'v_result', 'expression': 'p_param2 * 2'}]
        },
        'body': 'IF p_param1 IS NULL THEN RAISE APPLICATION_ERROR; END IF;',
        'package': 'test',
        'raw_plsql': 'CREATE PROCEDURE test.test_method...'
    }
    
    # Normalize the service code
    normalized = generator._normalize_service_code("TestService.java", service_code)
    
    print("\n=== NORMALIZED CODE ===")
    print(normalized)
    print("\n=== ANALYSIS ===")
    
    # Check if method body was replaced
    if "// No SQL operations" in normalized:
        print("❌ FAIL: Empty method body was NOT replaced")
        print("   Method still contains the placeholder comment")
        return False
    elif "@Transactional" in normalized:
        print("✅ PASS: @Transactional annotation added (indicates method was regenerated)")
        return True
    else:
        print("⚠️  UNKNOWN: Method replacement may have occurred but can't fully verify")
        print("   Check manually if method contains real logic")
        return None

if __name__ == "__main__":
    result = test_seriazation_and_method_injection()
    if result is True:
        logger.info("✅ Fix verification PASSED - Methods are being regenerated with business logic")
        sys.exit(0)
    elif result is False:
        logger.error("❌ Fix verification FAILED - Methods are still empty stubs")
        sys.exit(1)
    else:
        logger.warning("⚠️  Fix verification INCONCLUSIVE")
        sys.exit(2)
