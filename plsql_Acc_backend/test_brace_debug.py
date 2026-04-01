from src.generator.improved_plsql_extractor import ImprovedPLSQLExtractor
from src.generator.plsql_to_java_converter import PLSQLtoJavaConverter

plsql_body = '''
procedure assert (p_condition in boolean, p_error_message in varchar2) as
begin
  if not nvl(p_condition, false) then
    raise_application_error (-20000, p_error_message);
  end if;
end assert;
'''

logic = ImprovedPLSQLExtractor.extract_all_logic(plsql_body)
java_code = PLSQLtoJavaConverter.generate_java_method('assert', logic)

# Count opening and closing braces
open_count = java_code.count('{')
close_count = java_code.count('}')

print(f"Generated code ({len(java_code)} chars, {open_count} open, {close_count} close):")
print("-" * 60)
lines = java_code.split('\n')
for i, line in enumerate(lines):
    o = line.count('{')
    c = line.count('}')
    braces = f" [{o}open,{c}close]" if (o or c) else ""
    print(f"{i}: {repr(line)}{braces}")
print("-" * 60)
print(f"Brace balance: {open_count - close_count} (should be 0)")
