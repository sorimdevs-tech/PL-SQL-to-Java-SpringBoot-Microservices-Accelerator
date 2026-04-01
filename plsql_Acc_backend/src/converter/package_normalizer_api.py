"""
PL/SQL Package Normalizer - Public API

Simple interface for normalizing PL/SQL packages.

Usage:
    from package_normalizer_api import normalize_packages, normalize_from_file
    
    # Method 1: Direct list
    result = normalize_packages(extracted_objects)
    
    # Method 2: From file
    result = normalize_from_file("extracted_objects.json")
"""

import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

from plsql_package_normalizer import PLSQLPackageNormalizer, UnifiedPackage

logger = logging.getLogger(__name__)


class PackageNormalizerAPI:
    """Public API for package normalization"""
    
    def __init__(self, log_unmatched: bool = True):
        """
        Initialize the API.
        
        Args:
            log_unmatched: If True, log stats about unmatched specs/bodies
        """
        self.log_unmatched = log_unmatched
        self.normalizer = None
    
    def normalize(self, objects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Normalize extracted PL/SQL objects.
        
        Args:
            objects: List of extracted package specs and bodies
            
        Returns:
            {
                "packages": [unified packages],
                "total_packages": count,
                "unmatched_specs": count,
                "unmatched_bodies": count,
                "summary": {...}
            }
        """
        self.normalizer = PLSQLPackageNormalizer()
        result = self.normalizer.normalize(objects)
        
        # Get dict format which has all counts
        full_result = self.normalizer.to_dict()
        
        # Add summary
        full_result["summary"] = self.normalizer.get_package_summary()
        
        if self.log_unmatched:
            self._log_unmatched()
        
        return full_result
    
    def normalize_from_file(self, file_path: str) -> Dict[str, Any]:
        """
        Normalize packages from a JSON file.
        
        Args:
            file_path: Path to JSON file with extracted objects
            
        Returns:
            Normalized result
        """
        with open(file_path, 'r') as f:
            objects = json.load(f)
        
        return self.normalize(objects)
    
    def to_json(self, pretty: bool = True) -> str:
        """Get JSON output of last normalization"""
        if not self.normalizer:
            raise ValueError("No normalization performed yet. Call normalize() first.")
        return self.normalizer.to_json(pretty=pretty)
    
    def to_dict(self) -> Dict[str, Any]:
        """Get dict output of last normalization"""
        if not self.normalizer:
            raise ValueError("No normalization performed yet. Call normalize() first.")
        return self.normalizer.to_dict()
    
    def get_packages(self) -> List[UnifiedPackage]:
        """Get unified packages from last normalization"""
        if not self.normalizer:
            raise ValueError("No normalization performed yet. Call normalize() first.")
        return list(self.normalizer.packages.values())
    
    def get_package_by_name(self, name: str) -> Optional[UnifiedPackage]:
        """Get specific package by name"""
        if not self.normalizer:
            raise ValueError("No normalization performed yet. Call normalize() first.")
        return self.normalizer.packages.get(name.lower())
    
    def _log_unmatched(self):
        """Log statistics about unmatched specs and bodies"""
        if not self.normalizer:
            return
        
        if self.normalizer.unmatched_specs:
            logger.warning(
                f"Found {len(self.normalizer.unmatched_specs)} unmatched specs: "
                f"{list(self.normalizer.unmatched_specs.keys())}"
            )
        
        if self.normalizer.unmatched_bodies:
            logger.warning(
                f"Found {len(self.normalizer.unmatched_bodies)} unmatched bodies: "
                f"{list(self.normalizer.unmatched_bodies.keys())}"
            )


# Convenience functions
def normalize_packages(objects: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize a list of extracted PL/SQL objects.
    
    Convenience function - creates and uses PackageNormalizerAPI internally.
    
    Args:
        objects: List of extracted package objects
        
    Returns:
        Normalized packages with metadata
        
    Example:
        >>> objects = [
        ...     {"name": "pkg1", "type": "PACKAGE_SPEC", ...},
        ...     {"name": "pkg1", "type": "PACKAGE_BODY", ...}
        ... ]
        >>> result = normalize_packages(objects)
        >>> print(result["total_packages"])
        1
    """
    api = PackageNormalizerAPI()
    return api.normalize(objects)


def normalize_from_file(file_path: str) -> Dict[str, Any]:
    """
    Normalize packages from a JSON file.
    
    Convenience function - creates and uses PackageNormalizerAPI internally.
    
    Args:
        file_path: Path to JSON file with extracted objects
        
    Returns:
        Normalized packages with metadata
        
    Example:
        >>> result = normalize_from_file("extracted_objects.json")
        >>> print(result["summary"]["total_packages"])
    """
    api = PackageNormalizerAPI()
    return api.normalize_from_file(file_path)


def filter_packages(objects: List[Dict[str, Any]], package_names: List[str]) -> List[Dict[str, Any]]:
    """
    Filter extracted objects by package names.
    
    Args:
        objects: List of extracted objects
        package_names: Names of packages to keep (case-insensitive)
        
    Returns:
        Filtered list of objects
    """
    names_lower = [n.lower() for n in package_names]
    return [
        obj for obj in objects
        if obj.get("name", "").lower() in names_lower
    ]


def get_package_stats(objects: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get statistics about extracted packages before normalization.
    
    Args:
        objects: List of extracted objects
        
    Returns:
        Stats about specs, bodies, packages
        
    Example:
        >>> stats = get_package_stats(objects)
        >>> print(stats)
        {
            'total_objects': 10,
            'specs': 5,
            'bodies': 4,
            'packages': 1,
            'orphan_specs': 1,
            'orphan_bodies': 0
        }
    """
    specs = []
    bodies = []
    packages = []
    
    for obj in objects:
        obj_type = obj.get("type", "").upper()
        if "SPEC" in obj_type:
            specs.append(obj)
        elif "BODY" in obj_type:
            bodies.append(obj)
        else:
            packages.append(obj)
    
    # Now normalize to see orphans
    api = PackageNormalizerAPI(log_unmatched=False)
    result = api.normalize(objects)
    
    return {
        "total_objects": len(objects),
        "specs": len(specs),
        "bodies": len(bodies),
        "standalone_packages": len(packages),
        "total_normalized_packages": result["total_packages"],
        "orphan_specs": result["unmatched_specs"],
        "orphan_bodies": result["unmatched_bodies"]
    }


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Example 1: Using convenience function
    print("=" * 60)
    print("Example 1: Using normalize_packages()")
    print("=" * 60)
    
    example_objects = [
        {
            "name": "util_pkg",
            "type": "PACKAGE_SPEC",
            "source": "util_pkg.pks",
            "procedures": [{"name": "p_log", "parameters": []}],
            "functions": []
        },
        {
            "name": "util_pkg",
            "type": "PACKAGE_BODY",
            "source": "util_pkg.pkb",
            "procedures": [{"name": "p_log", "parameters": []}],
            "functions": []
        },
        {
            "name": "math_pkg",
            "type": "PACKAGE_SPEC",
            "source": "math_pkg.pks",
            "procedures": [],
            "functions": [{"name": "f_add", "return_type": "NUMBER", "parameters": []}]
        }
    ]
    
    result = normalize_packages(example_objects)
    print(json.dumps(result, indent=2, default=str))
    
    # Example 2: Using API class
    print("\n" + "=" * 60)
    print("Example 2: Using PackageNormalizerAPI class")
    print("=" * 60)
    
    api = PackageNormalizerAPI()
    result = api.normalize(example_objects)
    
    print(f"\nTotal packages: {result['total_packages']}")
    print(f"Unmatched specs: {result['unmatched_specs']}")
    print(f"Unmatched bodies: {result['unmatched_bodies']}")
    
    for pkg in api.get_packages():
        print(f"\n  Package: {pkg.name}")
        print(f"    Has spec: {pkg.has_spec}")
        print(f"    Has body: {pkg.has_body}")
        print(f"    Procedures: {len(pkg.procedures)}")
        print(f"    Functions: {len(pkg.functions)}")
    
    # Example 3: Get stats
    print("\n" + "=" * 60)
    print("Example 3: Get statistics")
    print("=" * 60)
    
    stats = get_package_stats(example_objects)
    print(json.dumps(stats, indent=2))
