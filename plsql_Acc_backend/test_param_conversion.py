#!/usr/bin/env python3
"""
Quick test to verify parameter name conversion in generated code
"""
import sys
sys.path.insert(0, 'src')

from src.generator.plsql_to_java_converter import PLSQLtoJavaConverter

# Test the NVL replacement
expr = "((p_amount != null ? p_amount : 0) * l_vat_rate)"
print(f"Expression: {expr}")

# Check parameter name conversion more explicitly
test_expression = "SUBSTR(p_text, 1, 255)"
print(f"\nOriginal: {test_expression}")

# We need a function to convert ALL variable references
def convert_param_names(java_code):
    """Convert p_* and l_* variable names to camelCase"""
    import re
    
    # Find all p_xxx, l_xxx patterns
    def replace_param(m):
        var_name = m.group(1)
        # Remove p_ or l_ prefix
        clean = var_name lstrip('pl_')
        # Convert to camelCase
        return PLSQLtoJavaConverter._to_camel_case(clean)
    
    # Replace all p_xxx and l_xxx
    result = re.sub(r'\b[pl]_(\w+)\b', replace_param, java_code)
    return result

print(convert_param_names("p_text, l_value, p_customer_id"))
