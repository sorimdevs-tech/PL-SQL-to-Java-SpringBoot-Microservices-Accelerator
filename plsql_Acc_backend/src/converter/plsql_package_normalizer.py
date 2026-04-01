"""
PL/SQL Package Normalizer

Merges package specifications (.pks) and package bodies (.pkb) 
into unified logical packages with proper metadata.

RULES:
1. If names match → Combine into single entry with has_spec/has_body flags
2. NO duplicate package names
3. Count packages uniquely
4. Preserve procedures/functions under unified package
"""

import json
from typing import List, Dict, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict, field


@dataclass
class ProcedureFunction:
    """Represents a procedure or function"""
    name: str
    type: str  # "PROCEDURE" or "FUNCTION"
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    return_type: Optional[str] = None
    source: str = ""  # "SPEC" or "BODY"


@dataclass
class UnifiedPackage:
    """Represents a unified package (spec + body)"""
    name: str
    type: str = "PACKAGE"
    has_spec: bool = False
    has_body: bool = False
    procedures: List[ProcedureFunction] = field(default_factory=list)
    functions: List[ProcedureFunction] = field(default_factory=list)
    spec_source: Optional[str] = None
    body_source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary output"""
        return {
            "name": self.name,
            "type": self.type,
            "has_spec": self.has_spec,
            "has_body": self.has_body,
            "procedures": [asdict(p) for p in self.procedures],
            "functions": [asdict(f) for f in self.functions],
            "spec_source": self.spec_source,
            "body_source": self.body_source
        }


class PLSQLPackageNormalizer:
    """
    Normalizes extracted PL/SQL objects by merging specs and bodies.
    
    Usage:
        normalizer = PLSQLPackageNormalizer()
        normalized = normalizer.normalize(extracted_objects)
        output = normalizer.to_json()
    """

    def __init__(self):
        self.packages: Dict[str, UnifiedPackage] = {}
        self.unmatched_specs: Dict[str, Any] = {}
        self.unmatched_bodies: Dict[str, Any] = {}

    def normalize(self, extracted_objects: List[Dict[str, Any]]) -> Dict[str, List[UnifiedPackage]]:
        """
        Normalize list of extracted objects into unified packages.
        
        Args:
            extracted_objects: List of extracted PL/SQL objects from parser
                Expected format: [
                    {
                        "name": "pkg_name",
                        "type": "PACKAGE_SPEC" | "PACKAGE_BODY" | "PACKAGE",
                        "procedures": [...],
                        "functions": [...],
                        "source": "file_path"
                    }
                ]
        
        Returns:
            Dict with "packages" key containing unified packages
        """
        # Reset state
        self.packages = {}
        self.unmatched_specs = {}
        self.unmatched_bodies = {}

        # First pass: separate specs and bodies
        specs = []
        bodies = []
        packages = []

        for obj in extracted_objects:
            obj_type = obj.get("type", "").upper()
            
            if "SPEC" in obj_type or obj_type == "PACKAGE_SPEC":
                specs.append(obj)
            elif "BODY" in obj_type or obj_type == "PACKAGE_BODY":
                bodies.append(obj)
            elif obj_type == "PACKAGE":
                packages.append(obj)
            else:
                # Unknown type, treat as package
                packages.append(obj)

        # Second pass: merge matching specs and bodies
        self._merge_specs_and_bodies(specs, bodies)

        # Third pass: add standalone packages
        for pkg in packages:
            pkg_name = pkg.get("name", "unknown").lower()
            if pkg_name not in self.packages:
                unified = self._create_unified_package(pkg, is_spec=False, is_body=False)
                self.packages[pkg_name] = unified

        return {
            "packages": list(self.packages.values())
        }

    def _merge_specs_and_bodies(self, specs: List[Dict], bodies: List[Dict]) -> None:
        """
        RULE 1: Merge specs and bodies with matching names.
        RULE 2-3: Ensure no duplicates and unique counting.
        """
        # Track which specs and bodies have been merged
        merged_specs = set()
        merged_bodies = set()

        # Match specs with bodies
        for spec in specs:
            spec_name = spec.get("name", "unknown").lower()
            spec_idx = specs.index(spec)

            # Find matching body
            matched = False
            for body_idx, body in enumerate(bodies):
                body_name = body.get("name", "unknown").lower()

                if spec_name == body_name:
                    # RULE 1: Combine into single entry
                    unified = self._merge_spec_and_body(spec, body)
                    self.packages[spec_name] = unified
                    merged_specs.add(spec_idx)
                    merged_bodies.add(body_idx)
                    matched = True
                    break

            if not matched:
                # No matching body found - add spec only
                unified = self._create_unified_package(spec, is_spec=True, is_body=False)
                self.packages[spec_name] = unified
                merged_specs.add(spec_idx)
                self.unmatched_specs[spec_name] = spec

        # Add unmatched bodies
        for body_idx, body in enumerate(bodies):
            if body_idx not in merged_bodies:
                body_name = body.get("name", "unknown").lower()
                unified = self._create_unified_package(body, is_spec=False, is_body=True)
                self.packages[body_name] = unified
                self.unmatched_bodies[body_name] = body

    def _merge_spec_and_body(self, spec: Dict[str, Any], body: Dict[str, Any]) -> UnifiedPackage:
        """
        Merge a spec and body into a unified package.
        """
        pkg_name = spec.get("name", "unknown")
        
        unified = UnifiedPackage(
            name=pkg_name,
            type="PACKAGE",
            has_spec=True,
            has_body=True,
            spec_source=spec.get("source"),
            body_source=body.get("source")
        )

        # Extract procedures and functions from spec
        spec_procedures = spec.get("procedures", [])
        spec_functions = spec.get("functions", [])

        for proc in spec_procedures:
            unified.procedures.append(ProcedureFunction(
                name=proc.get("name", "unknown"),
                type="PROCEDURE",
                parameters=proc.get("parameters", []),
                source="SPEC"
            ))

        for func in spec_functions:
            unified.functions.append(ProcedureFunction(
                name=func.get("name", "unknown"),
                type="FUNCTION",
                parameters=func.get("parameters", []),
                return_type=func.get("return_type"),
                source="SPEC"
            ))

        # Extract procedures and functions from body
        body_procedures = body.get("procedures", [])
        body_functions = body.get("functions", [])

        for proc in body_procedures:
            proc_name = proc.get("name", "unknown")
            # Check if already in spec
            if not any(p.name == proc_name for p in unified.procedures):
                unified.procedures.append(ProcedureFunction(
                    name=proc_name,
                    type="PROCEDURE",
                    parameters=proc.get("parameters", []),
                    source="BODY"
                ))

        for func in body_functions:
            func_name = func.get("name", "unknown")
            # Check if already in spec
            if not any(f.name == func_name for f in unified.functions):
                unified.functions.append(ProcedureFunction(
                    name=func_name,
                    type="FUNCTION",
                    parameters=func.get("parameters", []),
                    return_type=func.get("return_type"),
                    source="BODY"
                ))

        return unified

    def _create_unified_package(
        self,
        obj: Dict[str, Any],
        is_spec: bool = False,
        is_body: bool = False
    ) -> UnifiedPackage:
        """
        Create a unified package from a single object (spec-only or body-only).
        """
        pkg_name = obj.get("name", "unknown")
        source = obj.get("source")

        unified = UnifiedPackage(
            name=pkg_name,
            type="PACKAGE",
            has_spec=is_spec,
            has_body=is_body,
            spec_source=source if is_spec else None,
            body_source=source if is_body else None
        )

        # Extract procedures
        for proc in obj.get("procedures", []):
            unified.procedures.append(ProcedureFunction(
                name=proc.get("name", "unknown"),
                type="PROCEDURE",
                parameters=proc.get("parameters", []),
                source="SPEC" if is_spec else "BODY"
            ))

        # Extract functions
        for func in obj.get("functions", []):
            unified.functions.append(ProcedureFunction(
                name=func.get("name", "unknown"),
                type="FUNCTION",
                parameters=func.get("parameters", []),
                return_type=func.get("return_type"),
                source="SPEC" if is_spec else "BODY"
            ))

        return unified

    def to_json(self, pretty: bool = True) -> str:
        """
        Convert normalized packages to JSON output.
        
        RULE 2: NEVER output duplicate package names.
        RULE 3: Count packages uniquely.
        """
        output = {
            "packages": [pkg.to_dict() for pkg in self.packages.values()],
            "total_packages": len(self.packages),
            "unmatched_specs": len(self.unmatched_specs),
            "unmatched_bodies": len(self.unmatched_bodies)
        }

        if pretty:
            return json.dumps(output, indent=2)
        else:
            return json.dumps(output)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary format.
        """
        return {
            "packages": [pkg.to_dict() for pkg in self.packages.values()],
            "total_packages": len(self.packages),
            "unmatched_specs": len(self.unmatched_specs),
            "unmatched_bodies": len(self.unmatched_bodies)
        }

    def get_package_summary(self) -> Dict[str, Any]:
        """
        Get a summary of normalized packages.
        """
        summary = {
            "total_packages": len(self.packages),
            "with_spec_and_body": 0,
            "spec_only": 0,
            "body_only": 0,
            "total_procedures": 0,
            "total_functions": 0,
            "packages": []
        }

        for pkg in self.packages.values():
            pkg_entry = {
                "name": pkg.name,
                "has_spec": pkg.has_spec,
                "has_body": pkg.has_body,
                "procedure_count": len(pkg.procedures),
                "function_count": len(pkg.functions)
            }
            summary["packages"].append(pkg_entry)
            summary["total_procedures"] += len(pkg.procedures)
            summary["total_functions"] += len(pkg.functions)

            if pkg.has_spec and pkg.has_body:
                summary["with_spec_and_body"] += 1
            elif pkg.has_spec:
                summary["spec_only"] += 1
            elif pkg.has_body:
                summary["body_only"] += 1

        return summary


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_usage():
    """
    Demonstrates how to use the normalizer.
    """
    # Example extracted objects
    extracted_objects = [
        {
            "name": "appl_error_pkg",
            "type": "PACKAGE_SPEC",
            "source": "appl_error_pkg.pks",
            "procedures": [
                {"name": "p_log_error", "type": "PROCEDURE", "parameters": []}
            ],
            "functions": []
        },
        {
            "name": "appl_error_pkg",
            "type": "PACKAGE_BODY",
            "source": "appl_error_pkg.pkb",
            "procedures": [
                {"name": "p_log_error", "type": "PROCEDURE", "parameters": []}
            ],
            "functions": []
        },
        {
            "name": "util_pkg",
            "type": "PACKAGE_SPEC",
            "source": "util_pkg.pks",
            "procedures": [],
            "functions": [
                {"name": "f_get_date", "type": "FUNCTION", "return_type": "DATE", "parameters": []}
            ]
        }
    ]

    # Normalize
    normalizer = PLSQLPackageNormalizer()
    result = normalizer.normalize(extracted_objects)

    # Output
    print("=== NORMALIZED PACKAGES ===")
    print(normalizer.to_json())

    print("\n=== SUMMARY ===")
    summary = normalizer.get_package_summary()
    print(json.dumps(summary, indent=2))

    return result


if __name__ == "__main__":
    example_usage()
