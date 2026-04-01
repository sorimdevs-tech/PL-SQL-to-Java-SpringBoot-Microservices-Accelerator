"""
PL/SQL Package Normalizer - Test Suite

Tests for the package normalizer with various scenarios.
"""

import json
import pytest
from plsql_package_normalizer import (
    PLSQLPackageNormalizer,
    UnifiedPackage,
    ProcedureFunction
)


class TestPackageNormalizer:
    """Test suite for PLSQLPackageNormalizer"""

    def setup_method(self):
        """Setup test fixtures"""
        self.normalizer = PLSQLPackageNormalizer()

    def test_merge_matching_spec_and_body(self):
        """
        RULE 1: If names match → Combine into single entry with has_spec/has_body flags
        
        Expected: Single package with has_spec=True, has_body=True
        """
        objects = [
            {
                "name": "appl_error_pkg",
                "type": "PACKAGE_SPEC",
                "source": "appl_error_pkg.pks",
                "procedures": [{"name": "p_log_error", "parameters": []}],
                "functions": []
            },
            {
                "name": "appl_error_pkg",
                "type": "PACKAGE_BODY",
                "source": "appl_error_pkg.pkb",
                "procedures": [{"name": "p_log_error", "parameters": []}],
                "functions": []
            }
        ]

        result = self.normalizer.normalize(objects)
        packages = result["packages"]

        # RULE 2: NEVER output duplicate package names
        assert len(packages) == 1, "Should have exactly one package"

        pkg = packages[0]
        assert pkg.name == "appl_error_pkg"
        assert pkg.has_spec is True
        assert pkg.has_body is True
        assert pkg.type == "PACKAGE"

    def test_no_duplicate_package_names(self):
        """
        RULE 2: NEVER output duplicate package names.
        
        Expected: No duplicate entries in output
        """
        objects = [
            {
                "name": "util_pkg",
                "type": "PACKAGE_SPEC",
                "source": "util_pkg.pks",
                "procedures": [],
                "functions": [{"name": "f_get_date", "return_type": "DATE", "parameters": []}]
            },
            {
                "name": "util_pkg",
                "type": "PACKAGE_BODY",
                "source": "util_pkg.pkb",
                "procedures": [],
                "functions": []
            }
        ]

        result = self.normalizer.normalize(objects)
        packages = result["packages"]

        # Extract package names
        pkg_names = [pkg.name for pkg in packages]

        # Check for duplicates
        assert len(pkg_names) == len(set(pkg_names)), "Should have no duplicate names"
        assert len(packages) == 1

    def test_unique_package_counting(self):
        """
        RULE 3: Count packages uniquely.
        
        Expected: 2 packages (not 4 from 2 specs + 2 bodies)
        """
        objects = [
            {
                "name": "pkg1",
                "type": "PACKAGE_SPEC",
                "source": "pkg1.pks",
                "procedures": [],
                "functions": []
            },
            {
                "name": "pkg1",
                "type": "PACKAGE_BODY",
                "source": "pkg1.pkb",
                "procedures": [],
                "functions": []
            },
            {
                "name": "pkg2",
                "type": "PACKAGE_SPEC",
                "source": "pkg2.pks",
                "procedures": [],
                "functions": []
            },
            {
                "name": "pkg2",
                "type": "PACKAGE_BODY",
                "source": "pkg2.pkb",
                "procedures": [],
                "functions": []
            }
        ]

        result = self.normalizer.normalize(objects)
        packages = result["packages"]

        # RULE 3: Count uniquely
        assert len(packages) == 2, "Should count each package once"
        assert self.normalizer.to_dict()["total_packages"] == 2

    def test_preserve_procedures_and_functions(self):
        """
        RULE 4: Preserve procedures/functions under the unified package.
        
        Expected: All procedures and functions present in unified package
        """
        objects = [
            {
                "name": "math_pkg",
                "type": "PACKAGE_SPEC",
                "source": "math_pkg.pks",
                "procedures": [
                    {"name": "p_add", "parameters": []}
                ],
                "functions": [
                    {"name": "f_multiply", "return_type": "NUMBER", "parameters": []}
                ]
            },
            {
                "name": "math_pkg",
                "type": "PACKAGE_BODY",
                "source": "math_pkg.pkb",
                "procedures": [
                    {"name": "p_add", "parameters": []}
                ],
                "functions": [
                    {"name": "f_multiply", "return_type": "NUMBER", "parameters": []}
                ]
            }
        ]

        result = self.normalizer.normalize(objects)
        pkg = result["packages"][0]

        # Verify procedures
        assert len(pkg.procedures) >= 1, "Should have procedures"
        assert any(p.name == "p_add" for p in pkg.procedures)

        # Verify functions
        assert len(pkg.functions) >= 1, "Should have functions"
        assert any(f.name == "f_multiply" for f in pkg.functions)

    def test_spec_only_package(self):
        """
        Test case: Spec without matching body
        
        Expected: Package with has_spec=True, has_body=False
        """
        objects = [
            {
                "name": "interface_pkg",
                "type": "PACKAGE_SPEC",
                "source": "interface_pkg.pks",
                "procedures": [],
                "functions": []
            }
        ]

        result = self.normalizer.normalize(objects)
        packages = result["packages"]

        assert len(packages) == 1
        pkg = packages[0]
        assert pkg.has_spec is True
        assert pkg.has_body is False

    def test_body_only_package(self):
        """
        Test case: Body without matching spec (unusual but possible)
        
        Expected: Package with has_spec=False, has_body=True
        """
        objects = [
            {
                "name": "orphan_pkg",
                "type": "PACKAGE_BODY",
                "source": "orphan_pkg.pkb",
                "procedures": [],
                "functions": []
            }
        ]

        result = self.normalizer.normalize(objects)
        packages = result["packages"]

        assert len(packages) == 1
        pkg = packages[0]
        assert pkg.has_spec is False
        assert pkg.has_body is True

    def test_multiple_packages_mixed(self):
        """
        Test case: Multiple packages with various combinations
        
        Scenario:
        - pkg_a: spec + body (matched)
        - pkg_b: spec only
        - pkg_c: body only
        - pkg_d: spec + body (matched)
        
        Expected: 4 unique packages, correct flags
        """
        objects = [
            {
                "name": "pkg_a",
                "type": "PACKAGE_SPEC",
                "source": "pkg_a.pks",
                "procedures": [],
                "functions": []
            },
            {
                "name": "pkg_a",
                "type": "PACKAGE_BODY",
                "source": "pkg_a.pkb",
                "procedures": [],
                "functions": []
            },
            {
                "name": "pkg_b",
                "type": "PACKAGE_SPEC",
                "source": "pkg_b.pks",
                "procedures": [],
                "functions": []
            },
            {
                "name": "pkg_c",
                "type": "PACKAGE_BODY",
                "source": "pkg_c.pkb",
                "procedures": [],
                "functions": []
            },
            {
                "name": "pkg_d",
                "type": "PACKAGE_SPEC",
                "source": "pkg_d.pks",
                "procedures": [],
                "functions": []
            },
            {
                "name": "pkg_d",
                "type": "PACKAGE_BODY",
                "source": "pkg_d.pkb",
                "procedures": [],
                "functions": []
            }
        ]

        result = self.normalizer.normalize(objects)
        packages = result["packages"]

        # Should have 4 unique packages
        assert len(packages) == 4

        # Find each package and verify flags
        pkg_a = next((p for p in packages if p.name == "pkg_a"), None)
        assert pkg_a is not None
        assert pkg_a.has_spec is True
        assert pkg_a.has_body is True

        pkg_b = next((p for p in packages if p.name == "pkg_b"), None)
        assert pkg_b is not None
        assert pkg_b.has_spec is True
        assert pkg_b.has_body is False

        pkg_c = next((p for p in packages if p.name == "pkg_c"), None)
        assert pkg_c is not None
        assert pkg_c.has_spec is False
        assert pkg_c.has_body is True

        pkg_d = next((p for p in packages if p.name == "pkg_d"), None)
        assert pkg_d is not None
        assert pkg_d.has_spec is True
        assert pkg_d.has_body is True

    def test_case_insensitive_matching(self):
        """
        Test case: Package names with different cases should match
        
        Expected: Spec "UTIL_PKG" and body "util_pkg" should merge
        """
        objects = [
            {
                "name": "UTIL_PKG",
                "type": "PACKAGE_SPEC",
                "source": "util_pkg.pks",
                "procedures": [],
                "functions": []
            },
            {
                "name": "util_pkg",
                "type": "PACKAGE_BODY",
                "source": "util_pkg.pkb",
                "procedures": [],
                "functions": []
            }
        ]

        result = self.normalizer.normalize(objects)
        packages = result["packages"]

        # Should merge into one package
        assert len(packages) == 1
        pkg = packages[0]
        assert pkg.has_spec is True
        assert pkg.has_body is True

    def test_json_output_format(self):
        """
        Test case: JSON output matches expected format
        
        Expected:
        {
          "packages": [
            {
              "name": "...",
              "type": "PACKAGE",
              "has_spec": true/false,
              "has_body": true/false,
              ...
            }
          ]
        }
        """
        objects = [
            {
                "name": "test_pkg",
                "type": "PACKAGE_SPEC",
                "source": "test_pkg.pks",
                "procedures": [{"name": "p_test", "parameters": []}],
                "functions": []
            },
            {
                "name": "test_pkg",
                "type": "PACKAGE_BODY",
                "source": "test_pkg.pkb",
                "procedures": [{"name": "p_test", "parameters": []}],
                "functions": []
            }
        ]

        result = self.normalizer.normalize(objects)
        json_str = self.normalizer.to_json()
        parsed = json.loads(json_str)

        # Verify JSON structure
        assert "packages" in parsed
        assert isinstance(parsed["packages"], list)
        assert len(parsed["packages"]) == 1

        pkg = parsed["packages"][0]
        assert pkg["name"] == "test_pkg"
        assert pkg["type"] == "PACKAGE"
        assert pkg["has_spec"] is True
        assert pkg["has_body"] is True

    def test_summary_statistics(self):
        """
        Test case: Summary statistics are calculated correctly
        
        Expected: Summary includes counts of spec-only, body-only, and matched packages
        """
        objects = [
            {
                "name": "pkg1",
                "type": "PACKAGE_SPEC",
                "source": "pkg1.pks",
                "procedures": [],
                "functions": []
            },
            {
                "name": "pkg1",
                "type": "PACKAGE_BODY",
                "source": "pkg1.pkb",
                "procedures": [],
                "functions": []
            },
            {
                "name": "pkg2",
                "type": "PACKAGE_SPEC",
                "source": "pkg2.pks",
                "procedures": [],
                "functions": []
            },
            {
                "name": "pkg3",
                "type": "PACKAGE_BODY",
                "source": "pkg3.pkb",
                "procedures": [],
                "functions": []
            }
        ]

        result = self.normalizer.normalize(objects)
        summary = self.normalizer.get_package_summary()

        # Verify summary
        assert summary["total_packages"] == 3
        assert summary["with_spec_and_body"] == 1
        assert summary["spec_only"] == 1
        assert summary["body_only"] == 1


def run_tests_verbose():
    """Run tests with verbose output"""
    print("=" * 60)
    print("PL/SQL Package Normalizer - Test Suite")
    print("=" * 60)

    test = TestPackageNormalizer()

    tests = [
        ("test_merge_matching_spec_and_body", "RULE 1: Merge matching names"),
        ("test_no_duplicate_package_names", "RULE 2: No duplicates"),
        ("test_unique_package_counting", "RULE 3: Count uniquely"),
        ("test_preserve_procedures_and_functions", "RULE 4: Preserve procedures/functions"),
        ("test_spec_only_package", "Spec without body"),
        ("test_body_only_package", "Body without spec"),
        ("test_multiple_packages_mixed", "Multiple packages mixed"),
        ("test_case_insensitive_matching", "Case-insensitive matching"),
        ("test_json_output_format", "JSON output format"),
        ("test_summary_statistics", "Summary statistics"),
    ]

    passed = 0
    failed = 0

    for test_method, description in tests:
        try:
            test.setup_method()
            getattr(test, test_method)()
            print(f"✓ {description}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {description}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {description}: Unexpected error - {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)


if __name__ == "__main__":
    run_tests_verbose()
