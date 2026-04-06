#!/usr/bin/env python3
"""
Function Signature Analyzer - Detects return types from PL/SQL signatures
"""

import re
from typing import Dict, Optional, Tuple


class FunctionSignatureAnalyzer:
    """Analyzes PL/SQL function signatures to detect correct Java return types"""
    
    @staticmethod
    def extract_return_type_from_signature(plsql_code: str, proc_name: str) -> Optional[str]:
        """
        Extract the return type from a PL/SQL function signature.
        
        Args:
            plsql_code: PL/SQL source code
            proc_name: Procedure/function name to look for
            
        Returns:
            Java type or None if not found/not a function
        """
        # Pattern 1: FUNCTION name(...) RETURN type
        pattern1 = rf'FUNCTION\s+{proc_name}\s*\([^)]*\)\s+RETURN\s+(\w+)'
        match = re.search(pattern1, plsql_code, re.IGNORECASE)
        if match:
            pl_sql_type = match.group(1).upper()
            return FunctionSignatureAnalyzer._convert_plsql_type_to_java(pl_sql_type)
        
        # Pattern 2: FUNCTION name(...) return type;
        pattern2 = rf'FUNCTION\s+{proc_name}\s*\([^)]*\)\s+(NUMBER|VARCHAR2|VARCHAR|DATE|TIMESTAMP|BOOLEAN|CLOB|BLOB|ROWID)'
        match = re.search(pattern2, plsql_code, re.IGNORECASE)
        if match:
            pl_sql_type = match.group(1).upper()
            return FunctionSignatureAnalyzer._convert_plsql_type_to_java(pl_sql_type)
        
        # Check if it's a PROCEDURE (not a function)
        pattern3 = rf'PROCEDURE\s+{proc_name}\s*\('
        if re.search(pattern3, plsql_code, re.IGNORECASE):
            return None  # Procedures don't return anything
        
        return None
    
    @staticmethod
    def _convert_plsql_type_to_java(plsql_type: str) -> str:
        """Convert PL/SQL type to Java type"""
        type_mapping = {
            'NUMBER': 'Long',
            'BINARY_INTEGER': 'int',
            'INTEGER': 'int',
            'PLS_INTEGER': 'int',
            'VARCHAR': 'String',
            'VARCHAR2': 'String',
            'CHAR': 'String',
            'CHARACTER': 'String',
            'NCHAR': 'String',
            'NVARCHAR2': 'String',
            'CLOB': 'String',
            'NCLOB': 'String',
            'BLOB': 'byte[]',
            'RAW': 'byte[]',
            'LONG_RAW': 'byte[]',
            'DATE': 'java.time.LocalDateTime',
            'TIMESTAMP': 'java.time.LocalDateTime',
            'TIMESTAMP WITH TIME ZONE': 'java.time.OffsetDateTime',
            'INTERVAL YEAR TO MONTH': 'String',
            'INTERVAL DAY TO SECOND': 'String',
            'BOOLEAN': 'Boolean',
            'ROWID': 'String',
            'UROWID': 'String',
        }
        
        plsql_type = plsql_type.strip().upper()
        return type_mapping.get(plsql_type, 'Object')
    
    @staticmethod
    def detect_function_vs_procedure(plsql_code: str, name: str) -> Tuple[bool, Optional[str]]:
        """
        Determine if a subprogram is a function or procedure.
        
        Args:
            plsql_code: PL/SQL source code
            name: Procedure/function name
            
        Returns:
            Tuple of (is_function, return_type or None)
        """
        # Look for FUNCTION keyword
        func_pattern = rf'\bFUNCTION\s+{name}\s*\('
        if re.search(func_pattern, plsql_code, re.IGNORECASE):
            return_type = FunctionSignatureAnalyzer.extract_return_type_from_signature(plsql_code, name)
            return True, return_type
        
        # Look for PROCEDURE keyword
        proc_pattern = rf'\bPROCEDURE\s+{name}\s*\('
        if re.search(proc_pattern, plsql_code, re.IGNORECASE):
            return False, None
        
        return False, None


# Test examples
if __name__ == "__main__":
    test_pls_sql = """
    PACKAGE invoice_pkg IS
        FUNCTION new_invoice(
            p_customer_id IN NUMBER,
            p_amount IN NUMBER
        ) RETURN NUMBER;
        
        PROCEDURE set_invoice(
            p_invoice_id IN NUMBER,
            p_status IN VARCHAR2
        );
        
        FUNCTION get_vat_amount(
            p_amount IN NUMBER,
            p_vat_code IN VARCHAR2
        ) RETURN NUMBER;
        
        FUNCTION get_default_invoice_description
        RETURN VARCHAR2;
    END invoice_pkg;
    """
    
    analyzer = FunctionSignatureAnalyzer()
    
    test_cases = [
        'new_invoice',
        'set_invoice',
        'get_vat_amount',
        'get_default_invoice_description'
    ]
    
    for test_case in test_cases:
        is_func, ret_type = analyzer.detect_function_vs_procedure(test_pls_sql, test_case)
        print(f"{test_case}: function={is_func}, return_type={ret_type}")
