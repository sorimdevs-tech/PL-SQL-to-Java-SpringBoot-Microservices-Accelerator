from src.parser.discovery_analyzer import build_discovery_model
import json

sql = '''
CREATE TABLE DEPARTMENT (
    DEPTID NUMBER(10) PRIMARY KEY,
    NAME VARCHAR2(100)
);

CREATE TABLE EMPLOYEE (
    EMPID NUMBER(10) PRIMARY KEY,
    DEPT_ID NUMBER(10),
    SALARY NUMBER(10,2)
);
'''

model = build_discovery_model(sql)
schema = model['schema']

for table in schema['tables']:
    print(f"Table: {table.get('name')}")
    print(f"Columns: {[c['name'] for c in table.get('columns', [])]}")
    print(f"FKs: {len(table.get('foreign_keys', []))}")
    for fk in table.get('foreign_keys', []):
        print(f"  - {fk.get('source_table')}.{fk.get('source_column')} -> {fk.get('target_table')}.{fk.get('target_column')}")
    print()
