from src.generator.improved_plsql_extractor import ImprovedPLSQLExtractor
from src.generator.plsql_to_java_converter import PLSQLtoJavaConverter
from src.generator.spring_boot_generator import SpringBootGenerator

# Generate method
plsql_body = '''
procedure assert (p_condition in boolean, p_error_message in varchar2) as
begin
  if not nvl(p_condition, false) then
    raise_application_error (-20000, p_error_message);
  end if;
end assert;
'''

logic = ImprovedPLSQLExtractor.extract_all_logic(plsql_body)
generated_method = PLSQLtoJavaConverter.generate_java_method('assert', logic)

# Template with stub method
template_code = '''package com.example;

import org.springframework.stereotype.Service;

@Service
public class ApplErrorPkgAssertService {
    public ApplErrorPkgAssertService() {
    }

    public void assertMethod() {
    }
}
'''

print("GENERATED METHOD:")
print("-" * 60)
print(generated_method)
print("-" * 60)

# Test injection
sbg = SpringBootGenerator()
injected = sbg._inject_method_body(template_code, generated_method)

print("\nINJECTED RESULT:")
print("-" * 60)
lines = injected.split('\n')
for i, line in enumerate(lines):
    print(f"{i}: {repr(line)}")
print("-" * 60)

# Check if parameters are present
if 'condition' in injected and 'errorMessage' in injected:
    print("✓ Parameters PRESENT in injected code")
else:
    print("✗ Parameters MISSING in injected code")
    print(f"  'condition' in code: {'condition' in injected}")
    print(f"  'errorMessage' in code: {'errorMessage' in injected}")
