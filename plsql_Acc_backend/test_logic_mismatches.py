#!/usr/bin/env python
"""
Test script to verify AND/OR fix generator output for critical services
"""
import sys
import os

# Add backend to path
sys.path.insert(0, r'c:\projects\plsql_Accelerator\plsql_Acc_backend')

from src.generator.improved_plsql_extractor import ImprovedPLSQLExtractor
from src.generator.plsql_to_java_converter import PLSQLtoJavaConverter

def test_appl_error_assert():
    """Test appl_error_pkg.assert"""
    print("\n" + "="*60)
    print("TEST: appl_error_pkg.assert")
    print("="*60)
    
    source = """procedure assert (p_condition in boolean,
                  p_error_message in varchar2)
as
begin
  if not nvl(p_condition, false) then
    raise_application_error (-20000, p_error_message);
  end if;
end assert;"""
    
    logic = ImprovedPLSQLExtractor.extract_all_logic(source)
    print(f"Extracted logic:")
    print(f"  Parameters: {logic.procedure_parameters}")
    print(f"  Validations: {logic.validations}")
    print(f"  Error assertions: {logic.error_assertions}")
    print(f"  Exceptions raised: {logic.exceptions_raised}")
    
    java_method = PLSQLtoJavaConverter.generate_java_method('assert', logic)
    print(f"\nGenerated Java method signature:")
    print(f"{java_method[:500]}")

def test_customer_new_customer():
    """Test customer_pkg.new_customer"""
    print("\n" + "="*60)
    print("TEST: customer_pkg.new_customer")
    print("="*60)
    
    source = """function new_customer (p_customer_name in varchar2) return number
as
  l_returnvalue xy_customer.customer_id%type;
begin
  insert into xy_customer (customer_name)
  values (p_customer_name)
  returning customer_id into l_returnvalue;

  return l_returnvalue;

end new_customer;"""
    
    logic = ImprovedPLSQLExtractor.extract_all_logic(source)
    print(f"Extracted logic:")
    print(f"  Return type: '{logic.return_type}'")
    print(f"  Parameters: {logic.procedure_parameters}")
    print(f"  Inserts: {logic.inserts}")
    print(f"  Returns: {logic.returns}")
    
    java_method = PLSQLtoJavaConverter.generate_java_method('new_customer', logic, entity_names={'xy_customer': 'XyCustomerEntity'})
    print(f"\nGenerated Java:")
    print(java_method)

def test_appl_log_log():
    """Test appl_log_pkg.log"""
    print("\n" + "="*60)
    print("TEST: appl_log_pkg.log")
    print("="*60)
    
    source = """procedure log (p_text in varchar2,
               p_level in number := null)
as
  pragma autonomous_transaction;
begin
  insert into appl_log (log_text, log_status, log_date)
  values (substr(p_text, 1, 255), nvl(p_level, c_log_level_debug), sysdate);

  commit;

end log;"""
    
    logic = ImprovedPLSQLExtractor.extract_all_logic(source)
    print(f"Extracted logic:")
    print(f"  Parameters: {logic.procedure_parameters}")
    print(f"  Inserts: {logic.inserts}")
    print(f"  Has commit: {logic.has_commit}")
    
    java_method = PLSQLtoJavaConverter.generate_java_method('log', logic, entity_names={'appl_log': 'ApplLogEntity'})
    print(f"\nGenerated Java:")
    print(java_method)

if __name__ == '__main__':
    test_appl_error_assert()
    test_customer_new_customer()
    test_appl_log_log()
