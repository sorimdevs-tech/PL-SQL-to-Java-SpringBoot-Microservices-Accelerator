import re

# Test 1: Basic RETURN type
text1 = 'function get_customer (p_customer_id in number) return xy_customer%rowtype as'
pattern = r'(?:PROCEDURE|FUNCTION)\s+\w+\s*\(\s*([^)]*)\s*\)\s*(?:RETURN\s+([^AS\n]+?))?\s*(?:AS|IS)'
match1 = re.search(pattern, text1, re.IGNORECASE | re.DOTALL)
print("Test 1 (with %rowtype):")
if match1:
    print('  Group 1 (params):', match1.group(1))
    print('  Group 2 (return):', repr(match1.group(2)))
else:
    print('  NO MATCH')

# Test 2: Simple RETURN
text2 = 'function new_customer (p_customer_name in varchar2) return number as'
match2 = re.search(pattern, text2, re.IGNORECASE | re.DOTALL)
print("\nTest 2 (simple return):")
if match2:
    print('  Group 1 (params):', match2.group(1))
    print('  Group 2 (return):', repr(match2.group(2)))
else:
    print('  NO MATCH')

# Test 3: PROCEDURE (no return)
text3 = 'procedure set_customer (p_customer_id in number, p_customer_name in varchar2) as'
match3 = re.search(pattern, text3, re.IGNORECASE | re.DOTALL)
print("\nTest 3 (procedure, no return):")
if match3:
    print('  Group 1 (params):', match3.group(1))
    print('  Group 2 (return):', repr(match3.group(2)))
else:
    print('  NO MATCH')
