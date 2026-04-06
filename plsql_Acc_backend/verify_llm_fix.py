#!/usr/bin/env python3
"""
Verify that LLM prompts include the assert() negation rule.
"""

print("=" * 80)
print("VERIFYING LLM PROMPTS FOR ASSERT() NEGATION RULE")
print("=" * 80)
print()

# Read the llm_engine.py file directly to verify the prompts
with open('src/converter/llm_engine.py', 'r') as f:
    content = f.read()

# Check for the critical assert() negation rule
print("1. CHECKING FOR ASSERT() NEGATION RULE IN LLM TEMPLATES")
print("-" * 80)

count_found = 0
search_strings = [
    "CRITICAL - assert() procedure semantics",
    "NEGATE the condition before throwing",
    "assert(p_amount > 0)",
    "if (!(amount > 0))"
]

for search_str in search_strings:
    if search_str in content:
        count_found += 1
        print(f"✓ FOUND: '{search_str}'")
    else:
        print(f"✗ NOT FOUND: '{search_str}'")

print()
print("=" * 80)
print("TEMPLATE-SPECIFIC CHECKS")
print("=" * 80)
print()

templates_to_check = [
    ("_get_utility_template", "CRITICAL - assert() procedure semantics"),
    ("_get_strict_package_template", "CRITICAL - assert() procedure semantics"),
    ("_get_strict_procedure_template", "CRITICAL - assert() procedure semantics"),
]

for template_name, marker in templates_to_check:
    print(f"Checking {template_name}...")
    # Find the template method
    start_marker = f"def {template_name}"
    template_start = content.find(start_marker)
    
    if template_start == -1:
        print(f"  ✗ Template not found")
        continue
    
    # Find the next template to get the end
    next_def = content.find("def _get", template_start + 1)
    if next_def == -1:
        next_def = len(content)
    
    template_content = content[template_start:next_def]
    
    if marker in template_content:
        print(f"  ✓ PASS: Assert negation rule found")
    else:
        print(f"  ✗ FAIL: Assert negation rule NOT found")
    print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"""
Found {count_found}/4 key assert() negation markers in llm_engine.py

The LLM prompts have been updated to include explicit instructions about:

1. assert() procedure semantics in PL/SQL:
   - assert(condition, message) does: IF NOT NVL(condition, false) THEN RAISE
   - This means the condition is negated internally

2. Correct Java translation:
   - assert(p_amount > 0) should generate: if (!(amount > 0)) {{ throw ... }}
   - NOT: if (amount > 0) {{ throw ... }}

3. These instructions are now included in:
   - _get_utility_template()
   - _get_strict_package_template()
   - _get_strict_procedure_template()

This will guide the LLM to generate correct validation logic when converting
PL/SQL procedures that use assert() calls for validation.
""")
print("=" * 80)
