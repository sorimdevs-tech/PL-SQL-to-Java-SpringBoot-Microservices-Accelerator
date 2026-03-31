#!/usr/bin/env python3
"""
Service Code Validation and Correction System

This module validates generated Java service code against extracted PL/SQL logic
and applies corrections to ensure:
1. Return types match function signatures
2. Validation logic is correct (not hallucinated)
3. No PL/SQL syntax mixed with Java
4. Repository methods are valid
5. All field references exist
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass


@dataclass
class ValidationIssue:
    """Represents a validation issue found in generated code"""
    severity: str  # "error", "warning"
    category: str  # "signature", "logic", "syntax", "repository", "entity"
    location: str  # line reference or field name
    message: str
    suggestion: str
    code_snippet: Optional[str] = None


class ServiceCodeValidator:
    """Validates generated Java service against extracted PL/SQL logic"""
    
    def __init__(self):
        self.issues: List[ValidationIssue] = []
        
    def validate_service_code(
        self,
        java_code: str,
        extracted_logic: Dict[str, Any],
        class_name: str
    ) -> List[ValidationIssue]:
        """
        Validate generated Java service code against extracted PL/SQL logic.
        
        Args:
            java_code: Generated Java service code
            extracted_logic: Extracted logic from PL/SQL parser (with error_assertions, validations, etc.)
            class_name: Name of the service class
            
        Returns:
            List of validation issues found
        """
        self.issues = []
        
        # Extract key information from Java code
        method_sig = self._extract_method_signature(java_code)
        method_body = self._extract_method_body(java_code)
        
        # Validation checks
        self._validate_return_type(method_sig, extracted_logic, class_name)
        self._validate_validation_logic(method_body, extracted_logic)
        self._validate_plsql_syntax_in_java(method_body)
        self._validate_repository_methods(method_body)
        self._validate_field_references(method_body, extracted_logic)
        
        return self.issues
    
    def _extract_method_signature(self, code: str) -> Dict[str, str]:
        """Extract return type and parameter types from method signature"""
        # Pattern: public <returnType> <methodName>(<params>)
        pattern = r'public\s+(\w+)\s+(\w+)\s*\((.*?)\)'
        match = re.search(pattern, code)
        if not match:
            return {}
        
        return {
            'return_type': match.group(1),
            'method_name': match.group(2),
            'parameters': match.group(3)
        }
    
    def _extract_method_body(self, code: str) -> str:
        """Extract the method body from Java code"""
        # Find the first { after public <returnType>
        start = code.find('public')
        if start == -1:
            return ""
        
        brace_start = code.find('{', start)
        if brace_start == -1:
            return ""
        
        # Find matching closing brace
        brace_count = 1
        pos = brace_start + 1
        while pos < len(code) and brace_count > 0:
            if code[pos] == '{':
                brace_count += 1
            elif code[pos] == '}':
                brace_count -= 1
            pos += 1
        
        return code[brace_start:pos]
    
    def _validate_return_type(
        self,
        method_sig: Dict[str, str],
        extracted_logic: Dict[str, Any],
        class_name: str
    ):
        """Validate that return type matches function vs procedure"""
        if not method_sig:
            return
        
        return_type = method_sig.get('return_type', 'void')
        
        # Determine what the return type should be
        # If there are success_returns in the logic, it should NOT be void
        success_returns = extracted_logic.get('success_returns', [])
        
        if success_returns and return_type == 'void':
            self.issues.append(ValidationIssue(
                severity='error',
                category='signature',
                location='method signature',
                message=f'Method {method_sig["method_name"]} should not return void for a function',
                suggestion=f'Change return type from void to the appropriate type (Long, String, Object, etc.)',
                code_snippet=f'public {return_type} {method_sig["method_name"]}(...)'
            ))
    
    def _validate_validation_logic(self, body: str, extracted_logic: Dict[str, Any]):
        """Validate that extracted validation logic is correct, not hallucinated"""
        error_assertions = extracted_logic.get('error_assertions', [])
        validations = extracted_logic.get('validations', [])
        
        # Count IF/THROW patterns in the body
        throw_count = len(re.findall(r'if\s*\([^)]+\)\s*{[^}]*throw', body, re.IGNORECASE))
        expected_throw_count = len(error_assertions) + len(validations)
        
        # If there are more throw statements than extracted validations, some might be hallucinated
        if throw_count > expected_throw_count and expected_throw_count > 0:
            self.issues.append(ValidationIssue(
                severity='warning',
                category='logic',
                location='validation layer',
                message=f'Found {throw_count} throw statements but only {expected_throw_count} validations extracted',
                suggestion='Review validation logic - may contain LLM-hallucinated conditions',
                code_snippet=None
            ))
    
    def _validate_plsql_syntax_in_java(self, body: str):
        """Check for PL/SQL syntax that shouldn't be in Java"""
        plsql_patterns = {
            r':=': "PL/SQL assignment operator",
            r'case\s+\w+\s+when': "PL/SQL CASE/WHEN statement",
            r"\b\w+\s*=\s*\w+\s*[,)]": "Named parameter syntax (PL/SQL)",
            r"'[^']*'(?=\s*[,\)])": "Single-quoted string (should be double-quoted)",
            r"\.\.\.$": "Placeholder ellipsis",
            r"\w+_pkg\.": "Package-qualified reference",
            r"'[^']*'\s*\)": "String argument with single quotes",
        }
        
        for pattern, description in plsql_patterns.items():
            if re.search(pattern, body, re.IGNORECASE | re.MULTILINE):
                # Find the matching line
                for i, line in enumerate(body.split('\n')):
                    if re.search(pattern, line, re.IGNORECASE):
                        self.issues.append(ValidationIssue(
                            severity='error',
                            category='syntax',
                            location=f'line {i}',
                            message=f'PL/SQL syntax found: {description}',
                            suggestion=f'Replace with equivalent Java syntax',
                            code_snippet=line.strip()
                        ))
                        break
    
    def _validate_repository_methods(self, body: str):
        """Check for invalid repository method calls"""
        invalid_patterns = {
            r'findOne\(\.\.\.\)': 'Placeholder findOne() - needs implementation',
            r'deleteByCondition': 'Non-standard repository method',
            r'\w+Repository\.\w+\s*\(\s*\)': 'Repository method with no parameters - likely incomplete',
        }
        
        for pattern, description in invalid_patterns.items():
            matches = re.finditer(pattern, body)
            for match in matches:
                self.issues.append(ValidationIssue(
                    severity='error',
                    category='repository',
                    location=f'repository call',
                    message=f'Invalid repository call: {description}',
                    suggestion='Implement proper repository method',
                    code_snippet=match.group(0)
                ))
    
    def _validate_field_references(self, body: str, extracted_logic: Dict[str, Any]):
        """Check for undefined field references"""
        # Extract variable references like customer.getCustomerStatus()
        field_refs = re.findall(r'(\w+)\.get\w+\(\)', body)
        
        # These should match parameters or variables declared in the method
        parameters = extracted_logic.get('parameters', [])
        param_names = {p.get('name', '').lower() for p in parameters if isinstance(p, dict)}
        
        for ref in field_refs:
            if ref.lower() not in param_names and ref.lower() not in ['this', 'logger']:
                # Check if it's declared in the method
                if not re.search(rf'var\s+{ref}\s*=', body):
                    self.issues.append(ValidationIssue(
                        severity='warning',
                        category='entity',
                        location=f'field reference: {ref}',
                        message=f'Undefined variable reference: {ref}',
                        suggestion=f'Declare {ref} or get it from a parameter',
                        code_snippet=f'{ref}.get*()'
                    ))


class ServiceCodeCorrector:
    """Applies corrections to generated Java service code"""
    
    @staticmethod
    def correct_return_type(
        code: str,
        expected_return_type: str,
        method_name: str
    ) -> str:
        """Correct the return type of a method"""
        pattern = rf'public\s+void\s+({method_name}\s*\([^)]*\))'
        replacement = rf'public {expected_return_type} \1'
        return re.sub(pattern, replacement, code, flags=re.IGNORECASE)
    
    @staticmethod
    def correct_plsql_syntax(code: str) -> str:
        """Remove PL/SQL syntax and convert to proper Java"""
        # Replace assignment operator
        code = re.sub(r':=', '=', code)
        
        # Replace single quotes with double quotes (except in SQL strings)
        # This is tricky - only replace in non-SQL contexts
        lines = []
        for line in code.split('\n'):
            # Skip lines that look like SQL or string literals in method calls
            if 'SELECT' in line or 'WHERE' in line or '// ' in line:
                lines.append(line)
            else:
                # Replace single quotes with double quotes
                line = re.sub(r"'([^']*)'", r'"\1"', line)
                lines.append(line)
        code = '\n'.join(lines)
        
        # Replace PL/SQL named parameter syntax
        code = re.sub(r'(\w+)\s*=\s*(\w+)\s*,', r'\1: \2,', code)  # Partial fix
        code = re.sub(r'(\w+)\s*=\s*(\w+)\s*\)', r'\1: \2)', code)
        
        # Remove package-qualified references if they don't exist
        code = re.sub(r'(\w+)_pkg\.(\w+)', r'\2', code)
        
        return code
    
    @staticmethod
    def fill_placeholder_repository_methods(
        code: str,
        entity_name: str,
        lookup_keys: List[str]
    ) -> str:
        """Fill in placeholder repository method calls"""
        # Replace findOne(...) with actual method call
        if lookup_keys and entity_name:
            key_var = lookup_keys[0] if lookup_keys else 'id'
            key_getter = f'get{key_var[0].upper()}{key_var[1:]}'
            
            code = re.sub(
                r'findOne\(\.\.\.\)',
                f'findBy{key_var[0].upper()}{key_var[1:]}({key_var})',
                code
            )
        
        return code


def generate_correction_report(issues: List[ValidationIssue]) -> str:
    """Generate a human-readable report of issues and corrections"""
    if not issues:
        return "✅ No validation issues found!"
    
    report = f"""
VALIDATION REPORT
{'=' * 80}

Total Issues: {len(issues)}
Errors:   {len([i for i in issues if i.severity == 'error'])}
Warnings: {len([i for i in issues if i.severity == 'warning'])}

""" 
    
    # Group by category
    by_category = {}
    for issue in issues:
        if issue.category not in by_category:
            by_category[issue.category] = []
        by_category[issue.category].append(issue)
    
    for category, cat_issues in sorted(by_category.items()):
        report += f"\n{category.upper()}\n{'-' * 40}\n"
        for issue in cat_issues:
            report += f"""
  [{issue.severity.upper()}] {issue.message}
    Location: {issue.location}
    Suggestion: {issue.suggestion}
    {"Code: " + issue.code_snippet if issue.code_snippet else ""}
"""
    
    return report


if __name__ == "__main__":
    # Example usage
    validator = ServiceCodeValidator()
    
    # Test with extracted logic
    test_logic = {
        'error_assertions': [
            {'condition': 'p_customer_id IS NOT NULL', 'message': 'Customer ID required'},
        ],
        'validations': [],
        'success_returns': [{'type': 'Long', 'value': 'invoice_id'}],
        'parameters': [
            {'name': 'customerId', 'type': 'Long'},
        ]
    }
    
    test_code = """
    public Long createInvoice(Long customerId) {
        if (!(customerId != null)) {
            throw new BusinessException("Customer ID required");
        }
        return lReturnvalue;
    }
    """
    
    issues = validator.validate_service_code(test_code, test_logic, "CreateInvoiceService")
    print(generate_correction_report(issues))
