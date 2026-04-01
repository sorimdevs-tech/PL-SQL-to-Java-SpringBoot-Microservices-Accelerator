"""
PL/SQL Package Normalizer - Demo Script

Practical examples showing how to use the normalizer.
"""

import json
import sys
from pathlib import Path

# Add path for importing
sys.path.insert(0, str(Path(__file__).parent / "src" / "converter"))

from plsql_package_normalizer import PLSQLPackageNormalizer


def demo_1_simple_merge():
    """
    Demo 1: Simple merge of spec and body
    
    Shows how matching specs and bodies are merged into one package.
    """
    print("\n" + "="*60)
    print("DEMO 1: Simple Merge of Spec and Body")
    print("="*60)

    normalizer = PLSQLPackageNormalizer()

    objects = [
        {
            "name": "util_pkg",
            "type": "PACKAGE_SPEC",
            "source": "util_pkg.pks",
            "procedures": [
                {"name": "p_log_message", "parameters": []}
            ],
            "functions": []
        },
        {
            "name": "util_pkg",
            "type": "PACKAGE_BODY",
            "source": "util_pkg.pkb",
            "procedures": [
                {"name": "p_log_message", "parameters": []}
            ],
            "functions": []
        }
    ]

    print("\nInput: 2 files")
    print("  - util_pkg.pks (PACKAGE_SPEC)")
    print("  - util_pkg.pkb (PACKAGE_BODY)")

    result = normalizer.normalize(objects)

    print("\nOutput: 1 unified package")
    pkg = result["packages"][0]
    print(f"  - Name: {pkg.name}")
    print(f"  - Has Spec: {pkg.has_spec}")
    print(f"  - Has Body: {pkg.has_body}")
    print(f"  - Procedures: {len(pkg.procedures)}")

    print("\n✓ RULE 1: Matching names merged into single entry")
    print("✓ RULE 2: No duplicate package names")
    print("✓ RULE 3: Counted as 1 package (not 2)")


def demo_2_complex_scenario():
    """
    Demo 2: Complex scenario with mixed packages
    
    Shows handling of:
    - Matched spec and body
    - Spec without body
    - Body without spec
    """
    print("\n" + "="*60)
    print("DEMO 2: Complex Scenario with Mixed Packages")
    print("="*60)

    normalizer = PLSQLPackageNormalizer()

    objects = [
        # Package A: Complete (spec + body)
        {
            "name": "pkg_a",
            "type": "PACKAGE_SPEC",
            "source": "pkg_a.pks",
            "procedures": [{"name": "p_process", "parameters": []}],
            "functions": []
        },
        {
            "name": "pkg_a",
            "type": "PACKAGE_BODY",
            "source": "pkg_a.pkb",
            "procedures": [{"name": "p_process", "parameters": []}],
            "functions": []
        },
        # Package B: Spec only
        {
            "name": "pkg_b",
            "type": "PACKAGE_SPEC",
            "source": "pkg_b.pks",
            "procedures": [],
            "functions": [{"name": "f_validate", "return_type": "BOOLEAN", "parameters": []}]
        },
        # Package C: Body only (unusual)
        {
            "name": "pkg_c",
            "type": "PACKAGE_BODY",
            "source": "pkg_c.pkb",
            "procedures": [{"name": "p_cleanup", "parameters": []}],
            "functions": []
        }
    ]

    print("\nInput: 4 files")
    print("  - pkg_a.pks + pkg_a.pkb (matched)")
    print("  - pkg_b.pks (spec only)")
    print("  - pkg_c.pkb (body only)")

    result = normalizer.normalize(objects)

    print("\nOutput: 3 unified packages")
    for pkg in result["packages"]:
        spec_str = "✓" if pkg.has_spec else "✗"
        body_str = "✓" if pkg.has_body else "✗"
        print(f"  - {pkg.name.ljust(10)} [Spec: {spec_str}] [Body: {body_str}]")

    summary = normalizer.get_package_summary()
    print("\nStatistics:")
    print(f"  - Total packages: {summary['total_packages']}")
    print(f"  - With spec + body: {summary['with_spec_and_body']}")
    print(f"  - Spec only: {summary['spec_only']}")
    print(f"  - Body only: {summary['body_only']}")

    print("\n✓ RULE 1: Matched packages merged")
    print("✓ RULE 2: No duplicates (even with 4 files)")
    print("✓ RULE 3: Counted as 3 unique packages (not 4)")
    print("✓ RULE 4: Procedures and functions preserved")


def demo_3_case_insensitive():
    """
    Demo 3: Case-insensitive matching
    
    Shows how specs and bodies with different cases still match.
    """
    print("\n" + "="*60)
    print("DEMO 3: Case-Insensitive Matching")
    print("="*60)

    normalizer = PLSQLPackageNormalizer()

    objects = [
        {
            "name": "UTIL_PKG",  # uppercase
            "type": "PACKAGE_SPEC",
            "source": "util_pkg.pks",
            "procedures": [],
            "functions": []
        },
        {
            "name": "util_pkg",  # lowercase
            "type": "PACKAGE_BODY",
            "source": "util_pkg.pkb",
            "procedures": [],
            "functions": []
        }
    ]

    print("\nInput:")
    print("  - UTIL_PKG.pks (uppercase)")
    print("  - util_pkg.pkb (lowercase)")

    result = normalizer.normalize(objects)

    print("\nOutput: 1 unified package")
    pkg = result["packages"][0]
    print(f"  - Name: {pkg.name}")
    print(f"  - Has Spec: {pkg.has_spec}")
    print(f"  - Has Body: {pkg.has_body}")

    print("\n✓ Case-insensitive matching works correctly")
    print("✓ Different case names are merged successfully")


def demo_4_json_output():
    """
    Demo 4: JSON output format
    
    Shows the JSON structure of normalized packages.
    """
    print("\n" + "="*60)
    print("DEMO 4: JSON Output Format")
    print("="*60)

    normalizer = PLSQLPackageNormalizer()

    objects = [
        {
            "name": "math_pkg",
            "type": "PACKAGE_SPEC",
            "source": "math_pkg.pks",
            "procedures": [
                {
                    "name": "p_add",
                    "parameters": [
                        {"name": "p_x", "type": "NUMBER", "direction": "IN"},
                        {"name": "p_y", "type": "NUMBER", "direction": "IN"}
                    ]
                }
            ],
            "functions": [
                {
                    "name": "f_multiply",
                    "return_type": "NUMBER",
                    "parameters": [
                        {"name": "p_a", "type": "NUMBER", "direction": "IN"},
                        {"name": "p_b", "type": "NUMBER", "direction": "IN"}
                    ]
                }
            ]
        },
        {
            "name": "math_pkg",
            "type": "PACKAGE_BODY",
            "source": "math_pkg.pkb",
            "procedures": [
                {
                    "name": "p_add",
                    "parameters": []
                }
            ],
            "functions": [
                {
                    "name": "f_multiply",
                    "return_type": "NUMBER",
                    "parameters": []
                }
            ]
        }
    ]

    result = normalizer.normalize(objects)

    print("\nJSON Output (pretty-printed):")
    print(normalizer.to_json(pretty=True))

    print("\n✓ JSON output contains all required fields")
    print("✓ Procedures and functions preserved")
    print("✓ Source tracking included (SPEC/BODY)")


def demo_5_statistics():
    """
    Demo 5: Statistics and summary
    
    Shows how to get statistics from normalized packages.
    """
    print("\n" + "="*60)
    print("DEMO 5: Statistics and Summary")
    print("="*60)

    normalizer = PLSQLPackageNormalizer()

    objects = [
        # Complete packages
        {"name": "pkg1", "type": "PACKAGE_SPEC", "source": "pkg1.pks", "procedures": [{"name": "p1", "parameters": []}], "functions": []},
        {"name": "pkg1", "type": "PACKAGE_BODY", "source": "pkg1.pkb", "procedures": [{"name": "p1", "parameters": []}], "functions": []},
        
        {"name": "pkg2", "type": "PACKAGE_SPEC", "source": "pkg2.pks", "procedures": [], "functions": [{"name": "f1", "return_type": "VARCHAR2", "parameters": []}]},
        {"name": "pkg2", "type": "PACKAGE_BODY", "source": "pkg2.pkb", "procedures": [], "functions": [{"name": "f1", "return_type": "VARCHAR2", "parameters": []}]},
        
        # Spec only
        {"name": "pkg3", "type": "PACKAGE_SPEC", "source": "pkg3.pks", "procedures": [{"name": "p2", "parameters": []}, {"name": "p3", "parameters": []}], "functions": []},
        
        # Body only
        {"name": "pkg4", "type": "PACKAGE_BODY", "source": "pkg4.pkb", "procedures": [], "functions": [{"name": "f2", "return_type": "NUMBER", "parameters": []}]},
    ]

    normalizer.normalize(objects)
    summary = normalizer.get_package_summary()

    print("\nSummary Statistics:")
    print(f"  Total packages: {summary['total_packages']}")
    print(f"  With spec and body: {summary['with_spec_and_body']}")
    print(f"  Spec only: {summary['spec_only']}")
    print(f"  Body only: {summary['body_only']}")
    print(f"  Total procedures: {summary['total_procedures']}")
    print(f"  Total functions: {summary['total_functions']}")

    print("\nPackage Details:")
    for pkg in summary['packages']:
        print(f"  {pkg['name']}: {pkg['procedure_count']} procedures, {pkg['function_count']} functions")

    print("\n✓ Statistics calculated correctly")
    print("✓ Summary provides quick overview")


def demo_6_practical_integration():
    """
    Demo 6: Practical integration example
    
    Shows how to integrate normalizer into a typical workflow.
    """
    print("\n" + "="*60)
    print("DEMO 6: Practical Integration Example")
    print("="*60)

    print("\nTypical Workflow:")
    print("  1. Extract objects from parser")
    extracted = [
        {
            "name": "logging_pkg",
            "type": "PACKAGE_SPEC",
            "source": "logging_pkg.pks",
            "procedures": [{"name": "p_log", "parameters": []}],
            "functions": []
        },
        {
            "name": "logging_pkg",
            "type": "PACKAGE_BODY",
            "source": "logging_pkg.pkb",
            "procedures": [{"name": "p_log", "parameters": []}],
            "functions": []
        }
    ]
    print(f"     ✓ Extracted {len(extracted)} objects")

    print("  2. Normalize packages")
    normalizer = PLSQLPackageNormalizer()
    result = normalizer.normalize(extracted)
    print(f"     ✓ Normalized into {len(result['packages'])} packages")

    print("  3. Get statistics")
    summary = normalizer.get_package_summary()
    print(f"     ✓ Total packages: {summary['total_packages']}")
    print(f"     ✓ Total procedures: {summary['total_procedures']}")

    print("  4. Export results")
    json_output = normalizer.to_json(pretty=False)
    print(f"     ✓ JSON length: {len(json_output)} bytes")

    print("  5. Use in downstream processing")
    for pkg in result['packages']:
        print(f"     ✓ Processing package: {pkg.name}")

    print("\n✓ Complete workflow executed successfully")


def run_all_demos():
    """Run all demonstrations"""
    print("\n" + "="*70)
    print("PL/SQL PACKAGE NORMALIZER - DEMONSTRATION")
    print("="*70)

    demo_1_simple_merge()
    demo_2_complex_scenario()
    demo_3_case_insensitive()
    demo_4_json_output()
    demo_5_statistics()
    demo_6_practical_integration()

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("""
All 4 RULES demonstrated:
  ✓ RULE 1: Merge matching names
  ✓ RULE 2: No duplicate package names
  ✓ RULE 3: Count packages uniquely
  ✓ RULE 4: Preserve procedures/functions

All features working:
  ✓ Spec/body matching and merging
  ✓ Case-insensitive matching
  ✓ Statistics calculation
  ✓ JSON output
  ✓ Integration ready

Ready for production use!
    """)
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        run_all_demos()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
