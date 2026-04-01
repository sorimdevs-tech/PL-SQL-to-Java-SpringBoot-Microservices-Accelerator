# Foreign Key Extraction Fix - Implementation Summary

## Problem Statement
Foreign keys were not being displayed in the frontend Schema Explorer (Stage 2 Discovery):
- Only the RENT table showed FK (1 total)
- All other tables showed "No foreign keys detected"

## Root Causes Found & Fixed

### Issue 1: PK Column Skip Bug (FIXED ✅)
**Location**: [src/parser/discovery_analyzer.py](src/parser/discovery_analyzer.py) lines ~545

The function `_infer_foreign_keys_from_naming_patterns()` was **skipping ALL primary key columns** when checking for FK naming patterns. This broke FK extraction for junction tables where columns are BOTH primary keys AND foreign keys.

### Issue 2: ALTER TABLE FK Constraints Not Extracted (FIXED ✅)
**Location**: [src/parser/discovery_analyzer.py](src/parser/discovery_analyzer.py) lines ~3088+

The real issue! FKs were being defined using **ALTER TABLE** statements instead of inline in CREATE TABLE, but the code wasn't merging these into the table structures:

```sql
ALTER TABLE Customer
ADD CONSTRAINT Customer_FK
FOREIGN KEY (cardNumber)
REFERENCES Card(cardID); -- ← Not being extracted into table!
```

The `_extract_alter_table_foreign_keys()` function existed but was only adding to relationships, never to individual tables' foreign_keys arrays.

## Solutions Applied

### Fix 1: Remove PK Column Skip
Changed `_infer_foreign_keys_from_naming_patterns()` to check ALL columns, including primary keys.

### Fix 2: Merge ALTER TABLE FKs into Tables
Added code to:
1. Extract ALTER TABLE FKs once
2. Match them to corresponding source tables  
3. Add them to each table's foreign_keys list
4. De-duplicate FKs within each table (prefer explicit_constraint over naming_pattern)

```python
# Extract ALTER TABLE FKs
alter_table_fks = _extract_alter_table_foreign_keys(cleaned)

# Merge into each table
for table in table_defs:
    table_name = table.get("name", "").upper()
    for fk in alter_table_fks:
        if fk.get("source_table", "").upper() == table_name:
            table["foreign_keys"].append(fk_data)

# De-duplicate within each table
for table in table_defs:
    fk_map = {}
    for fk in table.get("foreign_keys", []):
        key = (fk["source_column"], fk["target_table"], fk["target_column"])
        if key not in fk_map or fk["fk_type"] == "explicit_constraint":
            fk_map[key] = fk
    table["foreign_keys"] = list(fk_map.values())
```

## Test Results  

### Git Repository Analysis ✅
**Repo**: https://github.com/victorst79/PL-SQL-project

**Before Fix**:
- Total FKs: 1
- Only RENT table showed FK

**After Fix**:
- Total FKs: 9
- CUSTOMER: 1 FK (CARDNUMBER → CARD.CARDID)
- EMPLOYEE: 2 FKs (CARDNUMBER → CARD, BRANCHNAME → BRANCH)
- BRANCH: 1 FK (ADDRESS → LOCATION)
- RENT: 3 FKs (CARDID → CARD, ITEMID → BOOK, ITEMID → VIDEO)
- BOOK: 1 FK (ADDRESS → LOCATION)
- VIDEO: 1 FK (ADDRESS → LOCATION)

### Uploaded SQL File Analysis ✅
**File**: complex.sql

- Tables: 6
- Total FKs: 6
- All FK relationships correctly extracted and displayed

### Response Structure ✅
- All required fields present
- FK data correctly formatted
- API response structure validated

## Files Modified

1. [src/parser/discovery_analyzer.py](src/parser/discovery_analyzer.py)
   - Lines ~545: Remove PK skip restriction
   - Lines ~3088+: Extract and merge ALTER TABLE FKs
   - Added de-duplication logic

2. [src/api/app.py](src/api/app.py) - Debug logging (already in place)
3. [main.py](main.py) - Debug logging (already in place)

## Verification

All tests passing:
- ✅ Git repo FK extraction
- ✅ File upload FK extraction  
- ✅ API response structure validation

## Impact

The frontend now displays ALL foreign keys from the git repository:
- **9 FK relationships** instead of 1
- Multiple tables now show their FK definitions
- Schema diagram relationships will be more complete
- Accurate data model representation in Stage 2 Discovery

## How to Test

1. **In Frontend**:
   - Go to Stage 2: Discovery
   - Upload SQL file or analyze git repo: https://github.com/victorst79/PL-SQL-project (branch: master)
   - Select each table and view "Foreign Keys" section
   - Should see all FK relationships

2. **Via API**:
   ```bash
   curl -X POST http://localhost:5000/api/discovery/analyze \
     -H "Content-Type: application/json" \
     -d '{"repo_url": "https://github.com/victorst79/PL-SQL-project", "branch": "master"}'
   ```
   Returns 9 FK relationships in discovery.schema.tables[].foreign_keys[]

