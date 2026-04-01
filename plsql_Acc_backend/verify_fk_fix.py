#!/usr/bin/env python
"""Simple verification that FK extraction fix is working."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from parser.discovery_analyzer import build_discovery_model

# Test case: Junction table with composite primary key that are also FKs
sql = """
CREATE TABLE RENT (
    CARDID NUMBER,
    ITEMID NUMBER,
    APPORPRIATIONDATE DATE,
    RETURNDATE DATE,
    CONSTRAINT Rent_PK PRIMARY KEY (CARDID, ITEMID)
);

CREATE TABLE CARD (
    CARDID NUMBER PRIMARY KEY
);

CREATE TABLE BOOK (
    BOOKID NUMBER PRIMARY KEY
);

CREATE TABLE VIDEO (
    VIDEOID NUMBER PRIMARY KEY
);
"""

print("="*80)
print("FK EXTRACTION FIX VERIFICATION")
print("="*80)
print("\nTest Scenario:")
print("- RENT table has composite PK: (CARDID, ITEMID)")
print("- CARDID should be inferred as FK to CARD.CARDID")
print("- ITEMID should try to match to... ITEM/ITEMID (not found)")
print()

model = build_discovery_model(sql)
schema = model.get("schema", {})
tables = schema.get("tables", [])

print("Results:")
for table in tables:
    fks = table.get("foreign_keys", [])
    status = table.get("fk_extraction_status", "UNKNOWN")
    
    print(f"\n{table.get('name')}")
    print(f"  Columns: {[c['name'] for c in table.get('columns', [])]}")
    print(f"  Primary Keys: {table.get('primary_keys', [])}")
    print(f"  Status: {status}")
    print(f"  FKs: {len(fks)}")
    
    if fks:
        for fk in fks:
            src_col = fk.get('source_column')
            tgt_tbl = fk.get('target_table')
            src = fk.get('fk_source')
            print(f"    ✓ {src_col} → {tgt_tbl} ({src})")

rent_table = next((t for t in tables if t.get('name') == 'RENT'), None)
if rent_table:
    rent_fks = rent_table.get('foreign_keys', [])
    if rent_fks and any(fk.get('source_column') == 'CARDID' for fk in rent_fks):
        print("\n" + "="*80)
        print("✓ SUCCESS: PK column CARDID is now being checked for FK patterns!")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("✗ FAILED: CARDID not detected as FK")
        print("="*80)
