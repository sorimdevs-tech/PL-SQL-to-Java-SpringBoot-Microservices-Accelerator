"""
Strict Extraction Validator

Validates PL/SQL extraction against 7 strict rules:
1. EXCEPTIONS - If raise_application_error exists → must record exception
2. CURSOR - If no SELECT/FOR/CURSOR keywords → cursor_count = 0
3. RETRY - If no loop/goto retry → retry_count = 0
4. ERROR HANDLING - If exception exists → fields NOT N/A
5. TABLE USAGE - If no DML → tables_used empty
6. DUPLICATES - Remove duplicate packages
7. SCOPE CONSISTENCY - Single object → analysis_scope = OBJECT
"""

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class ExtractionIssue:
    """Extraction issue found"""
    rule_number: int
    object_name: str
    issue: str
    field: str
    current_value: Any
    expected_value: Any
    correction: str


class StrictExtractionValidator:
    """Validates extraction against strict rules"""
    
    def __init__(self):
        self.issues: List[ExtractionIssue] = []
        self.corrected_data: Dict[str, Any] = {}
    
    def validate_and_correct(self, extraction_data: Any) -> Dict[str, Any]:
        """
        Validate extraction data and return corrected version.
        
        Args:
            extraction_data: Extracted JSON/dict from parser
            
        Returns:
            Corrected data with all violations fixed
        """
        self.issues = []
        self.corrected_data = extraction_data
        
        # Normalize to dict if needed
        if isinstance(extraction_data, str):
            self.corrected_data = json.loads(extraction_data)
        
        # Apply all validations
        self._validate_rule_1_exceptions()      # EXCEPTIONS
        self._validate_rule_2_cursors()         # CURSOR
        self._validate_rule_3_retries()         # RETRY
        self._validate_rule_4_error_handling()  # ERROR HANDLING
        self._validate_rule_5_table_usage()     # TABLE USAGE
        self._validate_rule_6_duplicates()      # DUPLICATES
        self._validate_rule_7_scope()           # SCOPE CONSISTENCY
        
        return self.corrected_data
    
    def _validate_rule_1_exceptions(self):
        """
        RULE 1: If raise_application_error exists but no exception recorded → ADD it
        """
        if "packages" not in self.corrected_data:
            return
        
        for pkg in self.corrected_data["packages"]:
            pkg_name = pkg.get("name", "unknown")
            source = pkg.get("source", "")
            exceptions = pkg.get("exceptions", [])
            
            # Check if source contains raise_application_error
            if "raise_application_error" in source.lower():
                if not exceptions or len(exceptions) == 0:
                    # VIOLATION: Has raise_application_error but no exception recorded
                    self.issues.append(ExtractionIssue(
                        rule_number=1,
                        object_name=pkg_name,
                        issue="raise_application_error found but no exception recorded",
                        field="exceptions",
                        current_value=exceptions,
                        expected_value=["APPLICATION_ERROR"],
                        correction="Adding APPLICATION_ERROR to exceptions"
                    ))
                    # FIX: Add exception
                    if "exceptions" not in pkg:
                        pkg["exceptions"] = []
                    pkg["exceptions"].append("APPLICATION_ERROR")
    
    def _validate_rule_2_cursors(self):
        """
        RULE 2: If no SELECT/FOR/CURSOR keywords → cursor_count MUST be 0
        """
        if "packages" not in self.corrected_data:
            return
        
        for pkg in self.corrected_data["packages"]:
            pkg_name = pkg.get("name", "unknown")
            source = pkg.get("source", "")
            cursor_count = pkg.get("cursor_count", 0)
            
            # Check if source has cursor-related keywords
            has_cursor_keywords = any(kw in source.upper() for kw in 
                                     ["SELECT", "FOR", "CURSOR", "FETCH", "OPEN"])
            
            if not has_cursor_keywords and cursor_count > 0:
                # VIOLATION: No cursor keywords but cursor_count > 0
                self.issues.append(ExtractionIssue(
                    rule_number=2,
                    object_name=pkg_name,
                    issue="No SELECT/FOR/CURSOR keywords but cursor_count > 0",
                    field="cursor_count",
                    current_value=cursor_count,
                    expected_value=0,
                    correction=f"Correcting cursor_count from {cursor_count} to 0"
                ))
                # FIX: Set to 0
                pkg["cursor_count"] = 0
    
    def _validate_rule_3_retries(self):
        """
        RULE 3: If no loop/goto retry → retry_count MUST be 0
        """
        if "packages" not in self.corrected_data:
            return
        
        for pkg in self.corrected_data["packages"]:
            pkg_name = pkg.get("name", "unknown")
            source = pkg.get("source", "")
            retry_count = pkg.get("retry_count", 0)
            
            # Check if source has retry-related keywords
            retry_keywords = ["LOOP", "GOTO", "RETRY", "CONTINUE", "REPEAT"]
            has_retry_keywords = any(kw in source.upper() for kw in retry_keywords)
            
            if not has_retry_keywords and retry_count > 0:
                # VIOLATION: No retry keywords but retry_count > 0
                self.issues.append(ExtractionIssue(
                    rule_number=3,
                    object_name=pkg_name,
                    issue="No LOOP/GOTO/RETRY keywords but retry_count > 0",
                    field="retry_count",
                    current_value=retry_count,
                    expected_value=0,
                    correction=f"Correcting retry_count from {retry_count} to 0"
                ))
                # FIX: Set to 0
                pkg["retry_count"] = 0
    
    def _validate_rule_4_error_handling(self):
        """
        RULE 4: If exception exists → fields MUST NOT be N/A
        """
        if "packages" not in self.corrected_data:
            return
        
        for pkg in self.corrected_data["packages"]:
            pkg_name = pkg.get("name", "unknown")
            exceptions = pkg.get("exceptions", [])
            
            if exceptions and len(exceptions) > 0:
                # Check critical fields are not N/A
                critical_fields = ["error_handling", "exception_behavior", "recovery_strategy"]
                for field in critical_fields:
                    value = pkg.get(field, "N/A")
                    if value == "N/A" or value is None:
                        self.issues.append(ExtractionIssue(
                            rule_number=4,
                            object_name=pkg_name,
                            issue=f"Exception exists but {field} is N/A",
                            field=field,
                            current_value=value,
                            expected_value="<value>",
                            correction=f"Setting {field} to provide details"
                        ))
                        # FIX: Provide reasonable defaults
                        if field == "error_handling":
                            pkg[field] = "EXPLICIT"
                        elif field == "exception_behavior":
                            pkg[field] = "RAISE"
                        elif field == "recovery_strategy":
                            pkg[field] = "PROPAGATE"
    
    def _validate_rule_5_table_usage(self):
        """
        RULE 5: If no DML → tables_used MUST be empty
        """
        if "packages" not in self.corrected_data:
            return
        
        for pkg in self.corrected_data["packages"]:
            pkg_name = pkg.get("name", "unknown")
            source = pkg.get("source", "")
            tables_used = pkg.get("tables_used", [])
            
            # Check if source has DML keywords
            dml_keywords = ["INSERT", "UPDATE", "DELETE", "SELECT"]
            has_dml = any(kw in source.upper() for kw in dml_keywords)
            
            if not has_dml and tables_used and len(tables_used) > 0:
                # VIOLATION: No DML but tables_used is not empty
                self.issues.append(ExtractionIssue(
                    rule_number=5,
                    object_name=pkg_name,
                    issue="No DML keywords but tables_used is not empty",
                    field="tables_used",
                    current_value=tables_used,
                    expected_value=[],
                    correction="Clearing tables_used as no DML found"
                ))
                # FIX: Clear tables_used
                pkg["tables_used"] = []
    
    def _validate_rule_6_duplicates(self):
        """
        RULE 6: Remove duplicate package entries
        """
        if "packages" not in self.corrected_data:
            return
        
        packages = self.corrected_data["packages"]
        seen_names = {}
        duplicates = []
        
        for i, pkg in enumerate(packages):
            pkg_name = pkg.get("name", f"unknown_{i}").lower()
            if pkg_name in seen_names:
                # Duplicate found
                duplicates.append(i)
                self.issues.append(ExtractionIssue(
                    rule_number=6,
                    object_name=pkg_name,
                    issue=f"Duplicate package entry (duplicate of index {seen_names[pkg_name]})",
                    field="packages",
                    current_value=pkg,
                    expected_value="<removed>",
                    correction=f"Removing duplicate package {pkg_name}"
                ))
            else:
                seen_names[pkg_name] = i
        
        # Remove duplicates (in reverse to preserve indices)
        for idx in sorted(duplicates, reverse=True):
            packages.pop(idx)
    
    def _validate_rule_7_scope(self):
        """
        RULE 7: If single object analyzed → analysis_scope = OBJECT
        """
        if "packages" not in self.corrected_data:
            return
        
        packages = self.corrected_data["packages"]
        current_scope = self.corrected_data.get("analysis_scope", "UNKNOWN")
        
        if len(packages) == 1 and current_scope != "OBJECT":
            # VIOLATION: Single object but scope is not OBJECT
            self.issues.append(ExtractionIssue(
                rule_number=7,
                object_name=packages[0].get("name", "unknown"),
                issue="Single object analyzed but analysis_scope is not OBJECT",
                field="analysis_scope",
                current_value=current_scope,
                expected_value="OBJECT",
                correction="Setting analysis_scope to OBJECT"
            ))
            # FIX: Set scope to OBJECT
            self.corrected_data["analysis_scope"] = "OBJECT"
    
    def get_issues_report(self) -> Dict[str, Any]:
        """Get report of all issues found"""
        return {
            "total_issues": len(self.issues),
            "issues_by_rule": self._group_by_rule(),
            "issues": [asdict(issue) for issue in self.issues]
        }
    
    def _group_by_rule(self) -> Dict[int, int]:
        """Group issues by rule number"""
        grouped = {}
        for issue in self.issues:
            rule = issue.rule_number
            grouped[rule] = grouped.get(rule, 0) + 1
        return grouped


def validate_file(file_path: str) -> Dict[str, Any]:
    """Validate extraction from file"""
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    validator = StrictExtractionValidator()
    corrected = validator.validate_and_correct(data)
    
    return {
        "corrected_data": corrected,
        "validation_report": validator.get_issues_report()
    }


def validate_string(json_string: str) -> Dict[str, Any]:
    """Validate extraction from JSON string"""
    data = json.loads(json_string)
    
    validator = StrictExtractionValidator()
    corrected = validator.validate_and_correct(data)
    
    return {
        "corrected_data": corrected,
        "validation_report": validator.get_issues_report()
    }


# Example usage
if __name__ == "__main__":
    example_data = {
        "analysis_scope": "PACKAGE",
        "packages": [
            {
                "name": "error_pkg",
                "source": "CREATE PACKAGE error_pkg AS raise_application_error(-20001, 'error'); END;",
                "exceptions": [],  # VIOLATION: has raise_application_error but no exception
                "cursor_count": 1,  # VIOLATION: no SELECT/FOR/CURSOR in source
                "retry_count": 1,   # VIOLATION: no LOOP/GOTO/RETRY in source
                "error_handling": "N/A",  # VIOLATION: exception exists but N/A
                "tables_used": ["t1", "t2"],  # OK if DML exists
                "analysis_scope": "PACKAGE"
            },
            {
                "name": "error_pkg",  # VIOLATION: duplicate
                "source": "...",
                "exceptions": [],
                "cursor_count": 0,
                "retry_count": 0,
                "tables_used": []
            }
        ]
    }
    
    validator = StrictExtractionValidator()
    corrected = validator.validate_and_correct(example_data)
    
    print("=== VALIDATION REPORT ===")
    print(json.dumps(validator.get_issues_report(), indent=2))
    
    print("\n=== CORRECTED DATA ===")
    print(json.dumps(corrected, indent=2))
