import sys
sys.path.insert(0, r'c:\projects\plsql_Accelerator\plsql_Acc_backend')

from src.parser.discovery_analyzer import _infer_implied_foreign_keys
from pathlib import Path

# Read all .pkb files from sample repo
sample_repo_dir = r'c:\projects\plsql_Accelerator\plsql_sample_repo'
all_sql = ""

for pkb_file in sorted(Path(sample_repo_dir).glob('*.pkb')):
    with open(pkb_file, 'r', encoding='utf-8', errors='ignore') as f:
        all_sql += f.read() + "\n"

# Create minimal inferred_tables dict (simulating what the engine would create)
inferred_tables = {
    'APPL_LOG': {
        'name': 'APPL_LOG',
        'columns': [
            {'name': 'LOG_DATE'},
            {'name': 'LOG_STATUS'},
            {'name': 'LOG_TEXT'}
        ]
    },
    'XY_CUSTOMER': {
        'name': 'XY_CUSTOMER',
        'columns': [
            {'name': 'CUSTOMER_ID'},
            {'name': 'CUSTOMER_NAME'},
            {'name': 'LAST_ACTIVE_DATE'}
        ]
    },
    'XY_INVOICE': {
        'name': 'XY_INVOICE',
        'columns': [
            {'name': 'INVOICE_ID'},
            {'name': 'INVOICE_AMOUNT'},
            {'name': 'INVOICE_DESCRIPTION'},
            {'name': 'INVOICE_STATUS'},
            {'name': 'VAT_AMOUNT'}
        ]
    },
    'XY_VAT': {
        'name': 'XY_VAT',
        'columns': [
            {'name': 'VAT_CODE'},
            {'name': 'VAT_RATE'}
        ]
    }
}

# Create parameters list
parameters = [
    {'name': 'P_CUSTOMER_ID', 'type': 'NUMBER', 'direction': 'IN'},
    {'name': 'P_INVOICE_ID', 'type': 'NUMBER', 'direction': 'IN'},
    {'name': 'P_VAT_CODE', 'type': 'VARCHAR2', 'direction': 'IN'},
]

print("=" * 70)
print("DIRECT FK INFERENCE TEST")
print("=" * 70)
print(f"\nAnalyzing {len(all_sql)} characters")
print(f"Tables: {list(inferred_tables.keys())}")
print(f"Parameters: {[p['name'] for p in parameters]}")

try:
    implied_fks = _infer_implied_foreign_keys(all_sql, inferred_tables, parameters)
    
    print(f"\n\nFOUND {len(implied_fks)} FK RELATIONSHIP(S)!")
    for i, fk in enumerate(implied_fks, 1):
        print(f"\n[FK {i}]")
        print(f"  {fk['from_table']}.{fk['from_column']} -> {fk['to_table']}.{fk['to_column']}")
        print(f"  Evidence: {fk.get('evidence', 'N/A')}")
        
except Exception as e:
    print(f"\nERROR during inference: {e}")
    import traceback
    traceback.print_exc()
