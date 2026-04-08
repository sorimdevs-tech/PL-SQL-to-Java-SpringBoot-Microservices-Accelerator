# Fix Plan: Java Code Generation Validation Failures

## Problem Analysis

The semantic validator is failing generated services with these errors:
1. **SAVEPOINT/EXCEPTION semantics missing**: No row-level try/catch with continue
2. **Aggregation query misuse**: Using findBy instead of sumBy/countBy
3. **Missing control-flow structure**: Branch count mismatch

## Root Cause Identification

### Issue 1: Row-Level Try/Catch Not Generated

**Validator Check** (line 841-848 in semantic_validator.py):
```regex
(for|while)\s*\([^\)]*\)\s*\{.*?try\s*\{.*?\}\s*catch\s*\(\s*Exception[^\)]*\)\s*\{.*?continue\s*;
```

**Current Code Path**:
- File: llm_engine.py, line 2766
- Method: `_generate_business_logic_snippets()`
- Issue: `direct_invocation_mode` is set to `True` when simple SELECT/COUNT queries exist
- Result: Uses global try/catch instead of row-level (line 3074-3078)

**When It Fails**:
- Services like LoginCustomer, Employee have exception blocks + cursor/bulk operations
- These should generate row-level try/catch (line 3080-3110)
- But `direct_invocation_mode = True` bypasses that logic

### Issue 2: Aggregation Tables Using Wrong Methods

**Validator Check** (line 691 in semantic_validator.py):
```python
if re.search(rf"\b{re.escape(repository_var)}\.findBy\w+\s*\(", service_code):
    # Error: should not use findBy for aggregation
```

**Problem Locations**:
1. **llm_engine.py line 1769**: `_aggregation_method_name()` returns `sumBy{suffix}` ✅
2. **But**: If repository doesn't have sumBy method, code might fall back to findAll() + iterate
3. **Or**: LLM generation used instead of deterministic

### Issue 3:Missing Control Flow

**Validator Check** (line 575 in semantic_validator.py):
```python
expected_branch_count = int((logic_tree.get("metrics") or {}).get("branch_count") or 0)
if expected_branch_count and self._java_branch_count(service_code) < expected_branch_count:
    # Error: missing branches
```

**Problem**:
- Logic tree specifies expected branch count from PL/SQL
- Generated Java doesn't preserve all IF/ELSIF/ELSE branches
- `_generate_business_logic_snippets()` may not extract all branches

---

## Solutions Required

### FIX 1: Force Row-Level Try/Catch for Services with Exception Blocks

**File**: llm_engine.py, method `_generate_deterministic_service_from_unit()`

**Logic**:
- Check if `raw_plsql` has EXCEPTION block
- Check if `transaction.has_savepoint` is True
- If either is True: FORCE `direct_invocation_mode = False`
- Result: Generate batch loop with row-level try/catch + continue

**Location to Add**: After line 2766, before using `direct_invocation_mode`

**Code**:
```python
# FORCE batch mode if exceptions or savepoints existif has_exception_block or transaction.get('has_savepoint'):
    direct_invocation_mode = False
```

### FIX 2: Ensure Aggregation Uses Correct Repository Methods

**File**: spring_boot_generator.py (repository generation)

**Steps**:
1. Extract aggregation tables from service units
2. Generate `sumBy<Keys>()` method definitions in repositories
3. Validate service code only calls these, not findBy

**Example**:
```java
// In repository for aggregation table
@Query("SELECT SUM(amount) FROM BOOK WHERE category_id = :categoryId")
BigDecimal sumByCategory(@Param("categoryId") Long categoryId);
```

### FIX 3: Preserve All Control-Flow Branches

**File**: llm_engine.py, method `_generate_business_logic_snippets()`

**Current Logic** (line 1620):
- Only extracts IF branches that use COUNT variables
- Ignores IF/ELSIF/ELSE without COUNT conditions
- Limited to branches before first SELECT

**Required Fix**:
- Extract ALL IF/ELSIF/ELSE branches from PL/SQL
- Convert each condition to Java if/else if/else
- Maintain nesting and execution order

**Location**: Lines 1620-1700 in llm_engine.py

---

## Implementation Summary

| Issue | File | Method | Fix | Priority |
|-------|------|--------|-----|----------|
| Row-level try/catch | llm_engine.py | _generate_deterministic_service_from_unit | Force `direct_invocation_mode = False` when exceptions present | CRITICAL |
| Aggregation methods | spring_boot_generator.py  | generate_repositories | Generate sumBy methods for aggregation tables | HIGH |
| Control flow | llm_engine.py | _generate_business_logic_snippets | Extract all IF/ELSIF/ELSE branches, not just those with COUNT | HIGH |

---

## Validation Tests

After fixes, verify:
1. Row-level try/catch present when `transaction.has_savepoint || exception_block`
2. No `findBy` calls for aggregation tables
3. Java branch count ≥ PL/SQL branch count

