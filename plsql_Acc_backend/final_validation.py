#!/usr/bin/env python3
"""
Final validation: Test FK inference against actual sample PL/SQL packages
"""

from pathlib import Path
from src.parser.discovery_analyzer import analyze_sql_source, build_discovery_model


def validate_on_real_packages():
    """Test FK inference on actual plsql_sample_repo packages"""
    print("\n" + "#"*70)
    print("# FINAL VALIDATION: FK INFERENCE ON REAL PL/SQL PACKAGES")
    print("#"*70)
    
    from src.parser.discovery_analyzer import infer_tables_from_dml, _prepare_sql_text
    
    sample_repo = Path(r"c:\projects\plsql_Accelerator\plsql_sample_repo")
    
    if not sample_repo.exists():
        print(f"Sample repo not found at {sample_repo}")
        return False
    
    # Read invoice_pkg and customer_pkg
    files = {
        "invoice_pkg.pkb": sample_repo / "invoice_pkg.pkb",
        "customer_pkg.pkb": sample_repo / "customer_pkg.pkb",
    }
    
    combined_sql = ""
    for name, path in files.items():
        if path.exists():
            print(f"Loading {name}...")
            combined_sql += f"\n-- ===== {name} =====\n"
            combined_sql += path.read_text()
        else:
            print(f"  ⚠ Not found: {path}")
    
    if not combined_sql.strip():
        print("No PL/SQL files loaded!")
        return False
    
    print(f"\nAnalyzing {len(combined_sql):,} characters of PL/SQL...")
    
    # Use the FK inference directly
    try:
        cleaned = _prepare_sql_text(combined_sql)
        inferred_tables_list = infer_tables_from_dml(cleaned)
        
        print(f"\n✓ Analysis complete")
        print(f"  Tables discovered: {len(inferred_tables_list)}")
        
        # Display discovered tables and their FKs
        print(f"\nDiscovered Tables:")
        total_fks = 0
        for table in inferred_tables_list:
            table_name = table.get("name", "?")
            cols = table.get("columns", [])
            fks = table.get("foreign_keys", [])
            operations = table.get("operations", [])
            total_fks += len(fks)
            
            print(f"\n  Table: {table_name}")
            
            if cols:
                col_names = [c.get("name", "?") for c in cols if isinstance(c, dict)]
                col_display = ", ".join(col_names[:5])
                if len(col_names) > 5:
                    col_display += f" (+ {len(col_names)-5} more)"
                print(f"    Columns: {col_display}")
            
            if fks:
                print(f"    Foreign Keys ({len(fks)}):")
                for fk in fks:
                    src_col = fk.get("source_column", "?")
                    tgt_table = fk.get("target_table", "?")
                    tgt_col = fk.get("target_column", "?")
                    src = f"{table_name}.{src_col}"
                    tgt = f"{tgt_table}.{tgt_col}"
                    print(f"      • {src} → {tgt}")
            
            if operations:
                print(f"    Operations: {', '.join(operations[:3])}")
        
        # Validation checks
        print("\n" + "="*70)
        print("VALIDATION CHECKS")
        print("="*70)
        
        all_fks = []
        for table in inferred_tables_list:
            all_fks.extend(table.get("foreign_keys", []))
        
        checks = {
            "Tables detected": len(inferred_tables_list) > 0,
            "No duplicate tables": len(inferred_tables_list) == len(set(t.get("name") for t in inferred_tables_list)),
            "FKs have proper structure": all(
                all(k in fk for k in ["source_column", "target_table", "target_column"])
                for fk in all_fks
            ),
            "FKs detected": total_fks > 0,
        }
        
        all_pass = True
        for check_name, result in checks.items():
            status = "✓" if result else "✗"
            print(f"{status} {check_name}")
            if not result:
                all_pass = False
        
        print(f"\nTotal tables analyzed: {len(inferred_tables_list)}")
        print(f"Total FKs detected: {total_fks}")
        
        return all_pass
        
    except Exception as e:
        print(f"\n✗ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = validate_on_real_packages()
    
    print("\n" + "#"*70)
    if success:
        print("✓ FINAL VALIDATION PASSED")
        print("FK inference working correctly on real PL/SQL packages")
    else:
        print("✗ VALIDATION FAILED")
        print("Please review the errors above")
    print("#"*70 + "\n")
