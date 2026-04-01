from src.parser.discovery_analyzer import _infer_foreign_keys_from_naming_patterns

# Test data
available_tables = {"DEPARTMENT", "EMPLOYEE"}
columns = [
    {"name": "EMPID"},
    {"name": "DEPT_ID"},
    {"name": "SALARY"}
]

result = _infer_foreign_keys_from_naming_patterns("EMPLOYEE", columns, available_tables)
print(f"Available tables: {available_tables}")
print(f"Columns: {[c['name'] for c in columns]}")
print(f"Inferred FKs: {result}")
