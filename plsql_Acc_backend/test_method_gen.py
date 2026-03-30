#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')

from src.generator.plsql_to_java_converter import PLSQLtoJavaConverter
from src.generator.improved_plsql_extractor import ImprovedPLSQLExtractor

plsql = """
BEGIN
  v_vat_rate := 0;
  RETURN ((p_amount * v_vat_rate) / 100);
END;
"""

logic = ImprovedPLSQLExtractor.extract_all_logic(plsql)
method = PLSQLtoJavaConverter.generate_java_method(
    proc_name='get_vat_amount',
    logic=logic,
    entity_names={},
    package_name='com.example'
)

print("=== GENERATED METHOD ===")
print(method)
print("\n=== METHOD STRUCTURE ===")
print(f"Lines: {len(method.splitlines())}")
for i, line in enumerate(method.splitlines(), 1):
    print(f"{i}: {repr(line)}")
