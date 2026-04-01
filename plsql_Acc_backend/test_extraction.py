#!/usr/bin/env python
from src.generator.improved_plsql_extractor import ImprovedPLSQLExtractor
from src.generator.plsql_to_java_converter import PLSQLtoJavaConverter

# Test 1: new_customer (INSERT with RETURNING)
print("=" * 60)
print("TEST 1: new_customer (INSERT with RETURNING)")
print("=" * 60)

body1 = """function new_customer (p_customer_name in varchar2) return number
as
  l_returnvalue xy_customer.customer_id%type;
begin
  insert into xy_customer (customer_name)
  values (p_customer_name)
  returning customer_id into l_returnvalue;

  return l_returnvalue;

end new_customer;"""

logic1 = ImprovedPLSQLExtractor.extract_all_logic(body1)
print(f"Return type: '{logic1.return_type}'")
print(f"Parameters: {logic1.procedure_parameters}")
print(f"Inserts: {logic1.inserts}")
print()
java1 = PLSQLtoJavaConverter.generate_java_method('new_customer', logic1, entity_names={'xy_customer': 'XyCustomerEntity'})
print(java1)

# Test 2: get_customer (SELECT with NO_DATA_FOUND)
print("\n" + "=" * 60)
print("TEST 2: get_customer (SELECT with NO_DATA_FOUND and %rowtype)")
print("=" * 60)

body2 = """function get_customer (p_customer_id in number) return xy_customer%rowtype
as
  l_returnvalue xy_customer%rowtype;
begin
  begin
    select *
    into l_returnvalue
    from xy_customer
    where customer_id = p_customer_id;
  exception
    when no_data_found then
      l_returnvalue := null;
  end;

  return l_returnvalue;

end get_customer;"""

logic2 = ImprovedPLSQLExtractor.extract_all_logic(body2)
print(f"Return type: '{logic2.return_type}'")
print(f"Parameters: {logic2.procedure_parameters}")
print(f"Selects: {logic2.selects}")
print(f"Returns: {logic2.returns}")
print()
java2 = PLSQLtoJavaConverter.generate_java_method('get_customer', logic2, entity_names={'xy_customer': 'XyCustomerEntity'})
print(java2)

# Test 3: Overloaded set_customer
print("\n" + "=" * 60)
print("TEST 3: set_customer overload 1 (by ID and name)")
print("=" * 60)

body3a = """procedure set_customer (p_customer_id in number,
                        p_customer_name in varchar2)
as
begin
  update xy_customer
  set customer_name = p_customer_name
  where customer_id = p_customer_id;

end set_customer;"""

logic3a = ImprovedPLSQLExtractor.extract_all_logic(body3a)
print(f"Parameters: {logic3a.procedure_parameters}")
print(f"Updates: {logic3a.updates}")
print()
java3a = PLSQLtoJavaConverter.generate_java_method('set_customer', logic3a, entity_names={'xy_customer': 'XyCustomerEntity'})
print(java3a)

print("\n" + "=" * 60)
print("TEST 3b: set_customer overload 2 (by %rowtype)")
print("=" * 60)

body3b = """procedure set_customer (p_row in xy_customer%rowtype)
as
begin
  update xy_customer
  set row = p_row
  where customer_id = p_row.customer_id;

end set_customer;"""

logic3b = ImprovedPLSQLExtractor.extract_all_logic(body3b)
print(f"Parameters: {logic3b.procedure_parameters}")
print(f"Updates: {logic3b.updates}")
print()
java3b = PLSQLtoJavaConverter.generate_java_method('set_customer', logic3b, entity_names={'xy_customer': 'XyCustomerEntity'})
print(java3b)
