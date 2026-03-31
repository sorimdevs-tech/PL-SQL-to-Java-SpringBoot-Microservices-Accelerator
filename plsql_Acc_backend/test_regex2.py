import re

# Test better pattern
text1 = 'function get_customer (p_customer_id in number) return xy_customer%rowtype as'
# Better pattern: match RETURN followed by any non-keyword content
pattern_new = r'(?:PROCEDURE|FUNCTION)\s+\w+\s*\(\s*([^)]*)\s*\)\s*(?:RETURN\s+(.+?))?(?:\s*(?:AS|IS))'
match1 = re.search(pattern_new, text1, re.IGNORECASE | re.DOTALL)
print("Test 1 (with new pattern):")
if match1:
    print('  Group 1 (params):', match1.group(1))
    print('  Group 2 (return):', repr(match1.group(2)))
else:
    print('  NO MATCH')

# Test 2: Simple RETURN
text2 = 'function new_customer (p_customer_name in varchar2) return number as'
match2 = re.search(pattern_new, text2, re.IGNORECASE | re.DOTALL)
print("\nTest 2 (simple return):")
if match2:
    print('  Group 1 (params):', match2.group(1))
    print('  Group 2 (return):', repr(match2.group(2)))
else:
    print('  NO MATCH')

# Test 3: PROCEDURE  
text3 = 'procedure set_customer (p_customer_id in number, p_customer_name in varchar2) as'
match3 = re.search(pattern_new, text3, re.IGNORECASE | re.DOTALL)
print("\nTest 3 (procedure, no return):")
if match3:
    print('  Group 1 (params):', match3.group(1))
    print('  Group 2 (return):', repr(match3.group(2)))
else:
    print('  NO MATCH')
