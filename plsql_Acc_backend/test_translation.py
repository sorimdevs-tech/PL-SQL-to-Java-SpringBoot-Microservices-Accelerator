#!/usr/bin/env python3
"""Test PL/SQL to Java translation fixes"""

import sys
sys.path.insert(0, '/c/projects/plsql_Accelerator/plsql_Acc_backend/src')

from generator.plsql_to_java_converter import PLSQLtoJavaConverter

# Test cases
tests = [
    ("p_customer_id is not null", "customerId != null"),
    ("p_amount > 0", "amount > 0"),
    ("l_customer.customer_id is not null", "customer.customerId != null"),
    ("NVL(p_amount, 0)", "(amount != null ? amount : 0)"),
    ("COALESCE(p_desc, 'default')", "(desc != null ? desc : 'default')"),
]

print("Testing PL/SQL to Java Expression Translation:")
print("=" * 60)

for plsql_expr, expected in tests:
    result = PLSQLtoJavaConverter._translate_plsql_expression(plsql_expr)
    status = "✓ PASS" if result == expected else "✗ FAIL"
    print(f"\n{status}")
    print(f"  Input:    {plsql_expr}")
    print(f"  Expected: {expected}")
    print(f"  Got:      {result}")
