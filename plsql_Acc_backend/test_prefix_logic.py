available_tables = {"DEPARTMENT", "EMPLOYEE"}
available_tables_upper = {t.upper(): t for t in available_tables}

print(f"available_tables_upper: {available_tables_upper}")

col_name = "DEPT_ID"
prefix = col_name.rsplit("_ID", 1)[0]
print(f"Column: {col_name}")
print(f"Prefix: {prefix}")
print(f"Prefix in available_tables_upper: {prefix in available_tables_upper}")

# Check for prefix match
for table_upper, table_orig in available_tables_upper.items():
    print(f"  Checking if {table_upper} starts with {prefix}: {table_upper.startswith(prefix)}")
    if table_upper.startswith(prefix):
        print(f"    -> MATCH! {table_upper}")
