import re

def test_inject_method_body(service_code: str, generated_method: str) -> str:
    """Test version of injection logic"""
    
    # Find the complete generated method (from 'public' to closing brace)
    gen_lines = generated_method.split('\n')
    method_start = -1
    method_end = -1
    brace_count = 0
    
    for idx, line in enumerate(gen_lines):
        if method_start == -1 and 'public' in line and '{' in line:
            method_start = idx
            brace_count = line.count('{') - line.count('}')
        elif method_start != -1:
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0 and '}' in line:
                method_end = idx
                break
    
    if method_start == -1 or method_end == -1:
        print(f"ERROR: Could not extract complete method (start={method_start}, end={method_end})")
        return service_code
    
    # Extract complete method including signature and body
    generated_complete_method = '\n'.join(gen_lines[method_start:method_end + 1])
    
    print(f"Extracted method (lines {method_start}-{method_end}):")
    print(repr(generated_complete_method))
    print()
    
    # Now find and replace the first public METHOD (not class!) in service_code
    sc_lines = service_code.split('\n')
    output_lines = []
    i = 0
    method_found = False
    inside_class_body = False  # Track if we're past the class declaration
    class_brace_depth = 0
    
    while i < len(sc_lines):
        line = sc_lines[i]
        
        # Track brace depth to know when we're inside the class body
        if 'public class' in line:
            inside_class_body = True
            class_brace_depth = line.count('{') - line.count('}')
        elif inside_class_body:
            class_brace_depth += line.count('{') - line.count('}')
        
        # Look for first public METHOD inside the class (not the class itself)
        if (not method_found and inside_class_body and class_brace_depth > 0 and 
            'public' in line and ('void' in line or 'Long' in line or 'String' in line or 
                                 'Boolean' in line or 'Integer' in line or 'BigDecimal' in line or
                                 'List' in line or 'Optional' in line)):
            method_found = True
            print(f"Found method to replace at template line {i}: {repr(line)}")
            print(f"Replacing with generated method...")
            
            # Replace with the complete generated method
            output_lines.append(generated_complete_method)
            
            # Skip the old method - find where it ends (method-level closing brace)
            brace_count = 0
            j = i
            found_opening_brace = False
            
            while j < len(sc_lines):
                current_line = sc_lines[j]
                
                # Track braces
                brace_count += current_line.count('{')
                brace_count -= current_line.count('}')
                
                if '{' in current_line:
                    found_opening_brace = True
                
                # Check if this is the closing brace of the method
                if found_opening_brace and brace_count == 0:
                    # We've skipped the old method completely
                    print(f"Old method ended at template line {j}: {repr(current_line)}")
                    i = j
                    break
                
                j += 1
        else:
            output_lines.append(line)
        
        i += 1
    
    result = '\n'.join(output_lines)
    return result


# Generate method
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

print("="*60)
print("INJECTING METHOD...")
print("="*60)
injected = test_inject_method_body(template_code, generated_method)

print("\nFINAL RESULT:")
print("-" * 60)
lines = injected.split('\n')
for i, line in enumerate(lines):
    print(f"{i}: {repr(line)}")
print("-" * 60)

if 'condition' in injected and 'errorMessage' in injected:
    print("✓ Parameters PRESENT")
else:
    print("✗ Parameters MISSING")
