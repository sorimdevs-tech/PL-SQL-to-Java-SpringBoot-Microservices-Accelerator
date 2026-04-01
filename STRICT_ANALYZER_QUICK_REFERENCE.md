# STRICT Analyzer - Quick Reference

## One-Liners

```bash
# Analyze repository
python strict_plsql_analyzer.py my_repo

# Save analysis
python strict_plsql_analyzer.py my_repo > analysis.json

# Generate report
python generate_report.py analysis.json --output report.md

# Chain all steps
python strict_plsql_analyzer.py my_repo > analysis.json && \
python generate_report.py analysis.json --output report.md
```

---

## What Gets Analyzed ✓

| Item | Analyzed | Notes |
|------|----------|-------|
| PROCEDURE | ✓ | Function parameters, tables, exceptions |
| FUNCTION | ✓ | Return type, tables, exceptions |
| PACKAGE | ✓ | Package spec and body |
| PACKAGE BODY | ✓ | Implementation details |
| TRIGGER | ✓ | If in .sql file |
| Type Objects | ✓ | CREATE TYPE detected |
| Schema DDL | ✓ | CREATE TABLE / ALTER TABLE |

---

## Output Fields Explained

```json
{
  "analysis_scope": "REPO",              // Scope of analysis
  "schema": {
    "status": "NOT_FOUND",               // DEFINED or NOT_FOUND
    "tables": []                         // DDL tables only
  },
  "external_tables": [],                 // DML references
  "procedures": [
    {
      "name": "proc_name",               // Object name
      "type": "PROCEDURE",               // Object type
      "parameters": [...],               // IN/OUT/IN OUT params
      "tables_used": ["T1"],             // From DML only
      "crud": ["SELECT"],                // Operations
      "business_logic": ["line 1"],      // First 10 statements
      "exceptions": [...],               // All exceptions (MANDATORY)
      "error_handling": {...},           // Filled or null
      "cursor_count": 0,                 // STRICT counting
      "retry_count": 0,                  // STRICT counting
      "file": "source.pkb"               // Source file
    }
  ]
}
```

---

## Exception Detection (MANDATORY)

**This ALWAYS runs. These patterns ALWAYS detected:**

| Pattern | Detected | Example |
|---------|----------|---------|
| `raise_application_error()` | ✓ APPLICATION_ERROR | `-20000, 'msg'` |
| `RAISE exception_name` | ✓ NAMED_EXCEPTION | `RAISE no_data_found` |
| `WHEN exception_name THEN` | ✓ EXCEPTION_HANDLER | `WHEN others THEN` |

**If code has exceptions → they WILL be found → they WILL be reported**

---

## Strict Counting Rules

### Cursors (STRICT)
```
Counted:
  ✓ CURSOR c_name IS SELECT...
  ✓ FOR rec IN (SELECT...) LOOP
  ✓ OPEN / FETCH / CLOSE

Not Counted:
  ✗ SELECT without cursor
  ✗ Implicit cursors
```

### Retry Logic (STRICT)
```
Counted:
  ✓ <<label>> LOOP...EXIT...END LOOP
  ✓ GOTO retry_point
  ✓ Exception handlers with GOTO

Not Counted:
  ✗ Regular FOR LOOP
  ✗ Implied retry
```

---

## Schema Detection (STRICT)

Only these DDL statements count as "schema definition":

```
✓ CREATE TABLE schema.table (...)
✓ ALTER TABLE schema.table ADD COLUMN ...
✓ CREATE TABLE table (...)

✗ SELECT FROM table (doesn't create schema)
✗ INSERT INTO table (doesn't create schema)
✗ References to unknown tables
```

**Result**: schema.status = "DEFINED" or "NOT_FOUND" (never guessed)

---

## Integration with Frontend

```typescript
// TypeScript usage in frontend
import { StrictAnalysis } from './types';

async function loadAnalysis() {
  const response = await fetch('/api/analysis/results');
  const data: StrictAnalysis = await response.json();
  
  // Use schema info
  console.log(data.schema.status);        // Show DDL tables
  console.log(data.external_tables);      // Show DML references
  
  // Use procedure details
  data.procedures.forEach(proc => {
    console.log(proc.exceptions);         // Show error handling
    console.log(proc.tables_used);        // Show table usage
    console.log(proc.crud);               // Show operations
  });
}
```

---

## Common Filters

```python
import json

data = json.load(open('analysis.json'))

# Procedures with exceptions
has_exceptions = [p for p in data['procedures'] if p['exceptions']]

# Procedures using specific table
uses_customer = [p for p in data['procedures'] if 'CUSTOMER' in p['tables_used']]

# Procedures with INSERT operations
has_inserts = [p for p in data['procedures'] if 'INSERT' in p['crud']]

# Procedures with retry logic
has_retry = [p for p in data['procedures'] if p['retry_count'] > 0]

# Count total exceptions
total_exceptions = sum(len(p['exceptions']) for p in data['procedures'])

# Get all tables
all_tables = set()
for p in data['procedures']:
    all_tables.update(p['tables_used'])
```

---

## STRICT Rules Checklist

- [ ] RULE 1: Scope marked as REPO or OBJECT
- [ ] RULE 2: Schema DEFINED only if CREATE TABLE/ALTER TABLE present
- [ ] RULE 3: No external_tables if no DDL (zero hallucination)
- [ ] RULE 4: External tables from DML (SELECT, INSERT, UPDATE, DELETE)
- [ ] RULE 5: Usage arrays tracking operations per table
- [ ] RULE 6: Never mix DDL and DML tables
- [ ] RULE 7: Both DDL+DML → schema, not external_tables
- [ ] BONUS: Exceptions detected (MANDATORY)
- [ ] BONUS: Cursor/retry counting STRICT (no guessing)

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No files found | Check `.sql`, `.pkb`, `.pks` extensions |
| Exceptions missing | Verify patterns: `raise_application_error()`, `RAISE`, `WHEN...THEN` |
| Schema empty | Expected if no `CREATE TABLE` in code |
| Cursor count 0 | Expected if no explicit `CURSOR` or `FOR...IN` |
| Retry count 0 | Expected if no `LOOP` with `EXIT` or `GOTO` |
| Invalid JSON | Check error log: `2> errors.log` |

---

## Performance Tips

| Scenario | Action |
|----------|--------|
| 10-20 files | Just run it - < 1 second |
| 100+ files | Still fast - pattern based |
| Large files | Memory efficient - streams |
| CI/CD pipeline | Add timeout: wrap in script |

---

## File Discovery Algorithm

```
For each path in repository:
  ├─ *.sql          → Include
  ├─ *.pkb          → Include (Package Body)
  ├─ *.pks          → Include (Package Spec)
  ├─ *.pkg          → Include (Package)
  ├─ *.prc          → Include (Procedure)
  ├─ *.fnc          → Include (Function)
  ├─ *.trg          → Include (Trigger)
  └─ other          → Skip

For each included file:
  ├─ Extract: CREATE PROCEDURE (.*?)
  ├─ Extract: CREATE FUNCTION (.*?)
  ├─ Extract: CREATE PACKAGE (.*?)
  └─ Analyze each object
```

---

## Output Validation

JSON schema validation:

```python
import json
from jsonschema import validate

schema = {
  "type": "object",
  "required": ["analysis_scope", "schema", "procedures"],
  "properties": {
    "analysis_scope": {"enum": ["REPO", "OBJECT"]},
    "schema": {
      "properties": {
        "status": {"enum": ["DEFINED", "NOT_FOUND"]},
        "tables": {"type": "array"}
      }
    },
    "procedures": {
      "type": "array",
      "items": {
        "required": ["name", "type", "exceptions"]
      }
    }
  }
}

data = json.load(open('analysis.json'))
validate(instance=data, schema=schema)
print("✓ Valid output")
```

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✓ | Will be detected/analyzed |
| ✗ | Will NOT be detected/analyzed |
| → | Leads to |
| ≡ | Equals/means |
| ... | More items |
| [] | Array/list |

---

**Quick Links**:
- Full Guide: [STRICT_ANALYZER_USAGE_GUIDE.md](STRICT_ANALYZER_USAGE_GUIDE.md)
- Analysis Report: [PLSQL_ANALYSIS_REPORT.md](PLSQL_ANALYSIS_REPORT.md)
- Implementation: [strict_plsql_analyzer.py](strict_plsql_analyzer.py)

