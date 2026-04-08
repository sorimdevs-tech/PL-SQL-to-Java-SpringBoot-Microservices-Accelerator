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
from difflib import get_close_matches
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
    def correct_service_code_logic(
        code: str,
        repositories: Optional[Dict[str, str]] = None,
        entity_name: str = "",
        lookup_keys: Optional[List[str]] = None,
    ) -> str:
        """
        Repair invalid Java service code using actual repository contracts.

        Fixes:
        1. Invalid repository method names such as sumBy...
        2. Mismatched method names/casing versus repository declarations
        3. Placeholder or missing repository method calls
        4. Missing try/catch blocks around service methods
        """
        corrected = ServiceCodeCorrector.correct_plsql_syntax(code)
        repository_contracts = ServiceCodeCorrector._extract_repository_contracts(repositories or {})
        corrected = ServiceCodeCorrector._repair_repository_calls(
            corrected,
            repository_contracts,
            entity_name=entity_name,
            lookup_keys=lookup_keys or [],
        )
        corrected = ServiceCodeCorrector._ensure_repository_invocation(
            corrected,
            repository_contracts,
            entity_name=entity_name,
            lookup_keys=lookup_keys or [],
        )
        corrected = ServiceCodeCorrector.ensure_try_catch(corrected)
        return corrected
    
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
        lookup_keys: List[str],
        repositories: Optional[Dict[str, str]] = None,
    ) -> str:
        """Fill in placeholder repository method calls"""
        return ServiceCodeCorrector.correct_service_code_logic(
            code,
            repositories=repositories,
            entity_name=entity_name,
            lookup_keys=lookup_keys,
        )

    @staticmethod
    def ensure_try_catch(code: str) -> str:
        """Wrap public method bodies in try/catch when exception handling is missing."""
        search_pos = 0
        while True:
            match = re.search(
                r'((?:public|protected)\s+(?!class\b)[\w<>\[\],\s]+\s+\w+\s*\([^)]*\)\s*\{)',
                code[search_pos:],
                flags=re.MULTILINE,
            )
            if not match:
                return code

            method_start = search_pos + match.start(1)
            brace_start = code.find('{', method_start)
            brace_end = ServiceCodeCorrector._find_matching_brace(code, brace_start)
            if brace_start == -1 or brace_end == -1:
                return code

            method_body = code[brace_start + 1:brace_end]
            if re.search(r'\btry\s*\{', method_body) and re.search(r'\bcatch\s*\(', method_body):
                search_pos = brace_end + 1
                continue

            indented_body = ServiceCodeCorrector._indent_block(method_body.strip('\n'), 8)
            if indented_body:
                indented_body = "\n" + indented_body + "\n    "
            wrapped = (
                "{\n"
                "        try {"
                f"{indented_body}"
                "        } catch (Exception e) {\n"
                '            throw new RuntimeException("Service operation failed", e);\n'
                "        }\n"
                "    }"
            )
            code = code[:brace_start] + wrapped + code[brace_end + 1:]
            search_pos = method_start + len(wrapped)

    @staticmethod
    def _extract_repository_contracts(repositories: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """Extract repository method names and signatures from generated repository interfaces."""
        contracts: Dict[str, Dict[str, Any]] = {}
        method_pattern = re.compile(
            r"^\s*(?:public\s+)?(?:default\s+)?[\w<>\[\], ?.]+\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*;",
            flags=re.MULTILINE,
        )

        for filename, repo_code in (repositories or {}).items():
            interface_name = Path(filename).stem
            methods: Dict[str, List[int]] = {}
            for match in method_pattern.finditer(repo_code or ""):
                method_name = match.group(1)
                arg_count = ServiceCodeCorrector._count_method_parameters(match.group(2))
                methods.setdefault(method_name, []).append(arg_count)
            contracts[interface_name] = {
                "methods": methods,
                "code": repo_code or "",
            }
        return contracts

    @staticmethod
    def _repair_repository_calls(
        code: str,
        repository_contracts: Dict[str, Dict[str, Any]],
        entity_name: str = "",
        lookup_keys: Optional[List[str]] = None,
    ) -> str:
        """Rewrite invalid repository calls to match actual repository methods."""
        repo_vars = ServiceCodeCorrector._extract_repository_variables(code)
        if not repo_vars:
            return code

        call_pattern = re.compile(r'\b(\w+)\.(\w+)\s*\((.*?)\)', flags=re.DOTALL)
        lookup_keys = lookup_keys or []
        result: List[str] = []
        last_end = 0

        for match in call_pattern.finditer(code):
            repo_var, method_name, arg_blob = match.group(1), match.group(2), match.group(3)
            repo_type = repo_vars.get(repo_var)
            contract = repository_contracts.get(repo_type or "")
            if not contract:
                continue

            args = ServiceCodeCorrector._split_call_arguments(arg_blob)
            replacement_method = ServiceCodeCorrector._choose_repository_method(
                invalid_method=method_name,
                args=args,
                contract=contract,
                entity_name=entity_name,
                lookup_keys=lookup_keys,
            )
            if replacement_method == method_name:
                continue

            result.append(code[last_end:match.start()])
            result.append(f"{repo_var}.{replacement_method}({arg_blob})")
            last_end = match.end()

        repaired = "".join(result) + code[last_end:]
        repaired = ServiceCodeCorrector._repair_missing_parentheses(repaired, repo_vars, repository_contracts)
        return repaired

    @staticmethod
    def _ensure_repository_invocation(
        code: str,
        repository_contracts: Dict[str, Dict[str, Any]],
        entity_name: str = "",
        lookup_keys: Optional[List[str]] = None,
    ) -> str:
        """Replace obvious placeholders/TODOs with safe repository calls when possible."""
        repo_vars = ServiceCodeCorrector._extract_repository_variables(code)
        if not repo_vars:
            return code
        if any(re.search(rf'\b{re.escape(repo_var)}\.\w+\s*\(', code) for repo_var in repo_vars):
            return code

        lookup_keys = lookup_keys or []
        repo_var, repo_type = next(iter(repo_vars.items()))
        contract = repository_contracts.get(repo_type or "")
        if not contract:
            return code

        replacement = ServiceCodeCorrector._fallback_repository_call(
            repo_var=repo_var,
            contract=contract,
            entity_name=entity_name,
            lookup_keys=lookup_keys,
        )
        if not replacement:
            return code

        placeholder_pattern = re.compile(r'//\s*TODO[^\n]*|/\*\s*TODO[\s\S]*?\*/|return\s+null\s*;')
        match = placeholder_pattern.search(code)
        if not match:
            return code
        return code[:match.start()] + replacement + code[match.end():]

    @staticmethod
    def _extract_repository_variables(code: str) -> Dict[str, str]:
        """Map repository field/variable names to repository types."""
        repo_vars: Dict[str, str] = {}
        for repo_type, repo_var in re.findall(
            r'\b([A-Z]\w*Repository)\s+(\w+)\s*(?:;|[,)=])',
            code,
        ):
            repo_vars[repo_var] = repo_type
        return repo_vars

    @staticmethod
    def _choose_repository_method(
        invalid_method: str,
        args: List[str],
        contract: Dict[str, Any],
        entity_name: str = "",
        lookup_keys: Optional[List[str]] = None,
    ) -> str:
        """Pick the closest valid repository method for an invalid call."""
        methods: Dict[str, List[int]] = contract.get("methods", {})
        if invalid_method in methods:
            return invalid_method

        arg_count = len(args)
        lookup_keys = lookup_keys or []

        exact_case_insensitive = next(
            (method for method in methods if method.lower() == invalid_method.lower()),
            None,
        )
        if exact_case_insensitive:
            return exact_case_insensitive

        if ServiceCodeCorrector._looks_like_invalid_aggregation_method(invalid_method):
            aggregation = ServiceCodeCorrector._find_aggregation_method(methods, invalid_method, arg_count)
            if aggregation:
                return aggregation

        preferred = {
            "findOne": "findById" if arg_count == 1 and "findById" in methods else "",
            "remove": "deleteById" if arg_count == 1 and "deleteById" in methods else "delete",
            "update": "save" if "save" in methods else "",
            "insert": "save" if "save" in methods else "",
            "deleteByCondition": "deleteById" if arg_count == 1 and "deleteById" in methods else "delete",
        }
        for prefix, candidate in preferred.items():
            if invalid_method == prefix or invalid_method.startswith(prefix):
                if candidate and ServiceCodeCorrector._method_supports_arg_count(methods, candidate, arg_count):
                    return candidate

        if invalid_method.startswith("findBy"):
            suffix = invalid_method[6:]
            candidates = [
                method for method, counts in methods.items()
                if method.startswith("findBy") and arg_count in counts
            ]
            matched = ServiceCodeCorrector._best_suffix_match(suffix, candidates)
            if matched:
                return matched

        close_matches = get_close_matches(invalid_method, list(methods.keys()), n=1, cutoff=0.6)
        if close_matches and ServiceCodeCorrector._method_supports_arg_count(methods, close_matches[0], arg_count):
            return close_matches[0]

        fallback = ServiceCodeCorrector._fallback_repository_method(
            methods=methods,
            entity_name=entity_name,
            lookup_keys=lookup_keys,
            arg_count=arg_count,
        )
        return fallback or invalid_method

    @staticmethod
    def _find_aggregation_method(methods: Dict[str, List[int]], invalid_method: str, arg_count: int) -> Optional[str]:
        suffix = ServiceCodeCorrector._aggregation_suffix(invalid_method)
        candidates = [
            method for method, counts in methods.items()
            if arg_count in counts and (method.startswith("getTotal") or method.startswith("getSum"))
        ]
        return ServiceCodeCorrector._best_suffix_match(suffix, candidates)

    @staticmethod
    def _looks_like_invalid_aggregation_method(method_name: str) -> bool:
        normalized = (method_name or "").strip()
        return normalized.startswith(("sumBy", "getTotalBy", "getTotalValueBy", "avgBy"))

    @staticmethod
    def _aggregation_suffix(method_name: str) -> str:
        normalized = (method_name or "").strip()
        for prefix in ("sumBy", "getTotalValueBy", "getTotalBy", "avgBy"):
            if normalized.startswith(prefix):
                return normalized[len(prefix):]
        if normalized.startswith("getTotal") and "By" in normalized:
            return normalized[len("getTotal"):]
        if normalized.startswith("getSum") and "By" in normalized:
            return normalized[len("getSum"):]
        return normalized

    @staticmethod
    def _best_suffix_match(suffix: str, candidates: List[str]) -> Optional[str]:
        if not candidates:
            return None
        normalized_suffix = re.sub(r'[^A-Za-z0-9]', '', suffix or '').lower()
        ranked: List[Tuple[int, int, str]] = []
        for candidate in candidates:
            candidate_suffix = re.sub(r'^(findBy|getTotal|getSum|getCount)', '', candidate)
            normalized_candidate = re.sub(r'[^A-Za-z0-9]', '', candidate_suffix).lower()
            overlap = len(set(normalized_suffix.split("by")) & set(normalized_candidate.split("by")))
            contains = int(normalized_suffix in normalized_candidate or normalized_candidate in normalized_suffix)
            ranked.append((contains, overlap, candidate))
        ranked.sort(reverse=True)
        return ranked[0][2] if ranked else None

    @staticmethod
    def _fallback_repository_method(
        methods: Dict[str, List[int]],
        entity_name: str,
        lookup_keys: List[str],
        arg_count: int,
    ) -> Optional[str]:
        """Choose a compile-safe repository method when a custom method is missing."""
        if arg_count == 1:
            for name in ("findById", "deleteById", "delete", "save"):
                if ServiceCodeCorrector._method_supports_arg_count(methods, name, arg_count):
                    return name
        for name in ("save", "findAll", "findById", "deleteById"):
            if ServiceCodeCorrector._method_supports_arg_count(methods, name, arg_count):
                return name
        if entity_name:
            entity_pascal = entity_name[0].upper() + entity_name[1:] if entity_name else ""
            preferred_custom = [
                method for method in methods
                if entity_pascal and entity_pascal.lower() in method.lower()
                and ServiceCodeCorrector._method_supports_arg_count(methods, method, arg_count)
            ]
            if preferred_custom:
                return preferred_custom[0]
        if lookup_keys:
            preferred_key = lookup_keys[0].lower()
            key_matches = [
                method for method in methods
                if preferred_key in method.lower()
                and ServiceCodeCorrector._method_supports_arg_count(methods, method, arg_count)
            ]
            if key_matches:
                return key_matches[0]
        return None

    @staticmethod
    def _fallback_repository_call(
        repo_var: str,
        contract: Dict[str, Any],
        entity_name: str,
        lookup_keys: List[str],
    ) -> Optional[str]:
        methods: Dict[str, List[int]] = contract.get("methods", {})
        if lookup_keys and ServiceCodeCorrector._method_supports_arg_count(methods, "findById", 1):
            return f"return {repo_var}.findById({lookup_keys[0]});"
        if entity_name and ServiceCodeCorrector._method_supports_arg_count(methods, "save", 1):
            entity_var = entity_name[0].lower() + entity_name[1:]
            return f"return {repo_var}.save({entity_var});"
        if ServiceCodeCorrector._method_supports_arg_count(methods, "findAll", 0):
            return f"return {repo_var}.findAll();"
        return None

    @staticmethod
    def _repair_missing_parentheses(
        code: str,
        repo_vars: Dict[str, str],
        repository_contracts: Dict[str, Dict[str, Any]],
    ) -> str:
        """Fix references like repo.findAll; to repo.findAll()."""
        for repo_var, repo_type in repo_vars.items():
            methods = repository_contracts.get(repo_type, {}).get("methods", {})
            zero_arg_methods = [name for name, counts in methods.items() if 0 in counts]
            for method_name in zero_arg_methods:
                code = re.sub(
                    rf'\b{re.escape(repo_var)}\.{re.escape(method_name)}\s*;',
                    f'{repo_var}.{method_name}();',
                    code,
                )
        return code

    @staticmethod
    def _method_supports_arg_count(methods: Dict[str, List[int]], method_name: str, arg_count: int) -> bool:
        counts = methods.get(method_name, [])
        return arg_count in counts

    @staticmethod
    def _count_method_parameters(param_blob: str) -> int:
        text = (param_blob or "").strip()
        if not text:
            return 0
        return len(ServiceCodeCorrector._split_call_arguments(text))

    @staticmethod
    def _split_call_arguments(args_blob: str) -> List[str]:
        args: List[str] = []
        text = (args_blob or "").strip()
        if not text:
            return args

        depth = 0
        token: List[str] = []
        for ch in text:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth = max(0, depth - 1)
            if ch == ',' and depth == 0:
                value = ''.join(token).strip()
                if value:
                    args.append(value)
                token = []
                continue
            token.append(ch)

        tail = ''.join(token).strip()
        if tail:
            args.append(tail)
        return args

    @staticmethod
    def _find_matching_brace(code: str, brace_start: int) -> int:
        if brace_start < 0 or brace_start >= len(code) or code[brace_start] != '{':
            return -1
        depth = 1
        pos = brace_start + 1
        while pos < len(code):
            if code[pos] == '{':
                depth += 1
            elif code[pos] == '}':
                depth -= 1
                if depth == 0:
                    return pos
            pos += 1
        return -1

    @staticmethod
    def _indent_block(text: str, spaces: int) -> str:
        indent = ' ' * spaces
        lines = text.splitlines()
        return '\n'.join(f"{indent}{line}" if line.strip() else "" for line in lines)


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
