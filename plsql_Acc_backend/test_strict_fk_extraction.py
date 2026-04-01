#!/usr/bin/env python
"""Test strict foreign key extraction with multiple sources."""

from src.parser.discovery_analyzer import build_discovery_model
import json

# Test case with multiple FK sources
test_sql = """
CREATE TABLE CARD (
    CARDID NUMBER(10) PRIMARY KEY,
    CARDHOLDER VARCHAR2(100),
    BALANCE NUMBER(10,2)
);

CREATE TABLE RENT (
    RENTID NUMBER(10) PRIMARY KEY,
    CARDID NUMBER(10) REFERENCES CARD(CARDID),
    PROPERTY_ID NUMBER(10),
    AMOUNT NUMBER(10,2),
    FOREIGN KEY (PROPERTY_ID) REFERENCES PROPERTY(PROPERTYID)
);

CREATE TABLE PROPERTY (
    PROPERTYID NUMBER(10) PRIMARY KEY,
    ADDRESS VARCHAR2(200),
    RENT_ID NUMBER(10) REFERENCES RENT(RENTID)
);

CREATE TABLE PAYMENT (
    PAYMENTID NUMBER(10) PRIMARY KEY,
    CARD_ID NUMBER(10),
    RENT_ID NUMBER(10),
    AMOUNT NUMBER(10,2)
);
"""

print("=" * 80)
print("STRICT FOREIGN KEY EXTRACTION TEST")
print("=" * 80)

model = build_discovery_model(test_sql)
schema = model['schema']

print("\n" + "[TABLES DETECTED]".center(80))
for table in schema['tables']:
    print(f"\nTable: {table['name']}")
    print(f"  Columns: {[c['name'] for c in table['columns']]}")
    print(f"  FK Extraction Status: {table.get('fk_extraction_status', 'UNKNOWN')}")
    print(f"  Foreign Keys ({len(table['foreign_keys'])}): ")
    if table['foreign_keys']:
        for fk in table['foreign_keys']:
            source = fk.get('fk_source', 'unknown')
            print(f"    - {fk['source_table']}.{fk['source_column']}")
            print(f"      -> {fk['target_table']}.{fk['target_column']}")
            print(f"      [Source: {source}]")
    else:
        print(f"    (none)")

print("\n" + "[VERIFICATION CHECKS]".center(80))

checks = {
    "CARD.CARDID is PK": schema['tables'][0]['primary_keys'] == ['CARDID'],
    "RENT has 2 FKs": len([t for t in schema['tables'] if t['name'] == 'RENT'][0]['foreign_keys']) == 2,
    "RENT.CARDID -> CARD.CARDID (explicit)": any(
        fk['source_column'] == 'CARDID' and fk['target_table'] == 'CARD'
        for fk in [t for t in schema['tables'] if t['name'] == 'RENT'][0]['foreign_keys']
    ),
    "RENT.PROPERTY_ID -> PROPERTY.PROPERTYID (constraint)": any(
        fk['source_column'] == 'PROPERTY_ID' and fk['target_table'] == 'PROPERTY'
        for fk in [t for t in schema['tables'] if t['name'] == 'RENT'][0]['foreign_keys']
    ),
    "PAYMENT has pattern-inferred FKs": any(
        fk.get('fk_source') == 'naming_pattern' 
        for fk in [t for t in schema['tables'] if t['name'] == 'PAYMENT'][0]['foreign_keys']
    ),
    "FK extraction status tracked": all(
        t.get('fk_extraction_status') in ['SUCCESS', 'PARTIAL']
        for t in schema['tables']
    ),
}

all_pass = True
for check_name, result in checks.items():
    status = "[OK]" if result else "[XX]"
    print(f"  {status} {check_name}: {result}")
    if not result:
        all_pass = False

print("\n" + "=" * 80)
if all_pass:
    print("RESULT: STRICT FK EXTRACTION WORKING CORRECTLY")
    print("  - Explicit REFERENCES clauses extracted")
    print("  - Column-level REFERENCES extracted")
    print("  - Naming pattern inference working")
    print("  - source_table field included")
    print("  - fk_extraction_status tracked")
else:
    print("RESULT: ISSUES DETECTED")
print("=" * 80)
