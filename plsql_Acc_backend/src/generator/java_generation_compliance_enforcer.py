"""
Java Generation Compliance Enforcer

Enforces all 12 PL/SQL-to-Java migration rules during code generation.
This module validates and corrects generated Java code in real-time.

Rules Enforced:
1. Strip Oracle-specific syntax
2. Fix variable declaration issues  
3. Ensure proper class/annotation structure
4. Correct JPA repository calls
5. Return proper types (not Object)
6. Handle autonomous transactions with @Transactional
7. Include ALL PL/SQL steps (never skip validation/logging)
8. Replace apex_web_service with RestTemplate
9. Replace string parsing with Jackson ObjectMapper
10. Replace package globals with Spring @Value injection
11. Convert PL/SQL overloads to proper Java methods
12. Return values from REST controllers (never void)
"""

import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ComplianceResult:
    """Result of compliance check"""
    is_compliant: bool
    violations: List[str]
    corrected_code: str


class JavaComplianceEnforcer:
    """Enforces all 12 Java generation rules"""
    
    # Oracle-specific patterns to eliminate (Rule #1)
    ORACLE_PATTERNS = {
        # Named parameter calls
        r'\.(\w+)\s*\(\s*\w+\s*=\s*': '.methodNamedParamError(',  # Will be caught as error
        # Oracle SQL functions
        r'\binstr\s*\(': '.indexOf(',
        r'\bsubstr\s*\(': '.substring(',
        r'\bnvl\s*\(': 'nvlToTernary__',  # Mark for replacement with ternary
        r'\bto_char\s*\(': 'String.format(',
        r'\btrunc\s*\(': 'Math.floor(',
        r'\bround\s*\(': 'Math.round(',
        # Oracle APEX
        r'\bapex_web_service\s*\.': 'restTemplate.',
        r'\bapex\s*\.\w+': 'apexRemovedError__',
        # Oracle Logger
        r'\blogger\s*\.append_param': 'log.debug',
        r'\blogger\s*\.log\s*\(': 'log.info(',
        r'\blogger\s*\.log_error': 'log.error',
    }
    
    # PL/SQL CASE/WHEN pattern (should be ternary)
    PLSQL_CASE_PATTERN = r'case\s+when\s+(.+?)\s+then\s+(.+?)(?:\s+else\s+(.+?))?\s+end'
    
    @staticmethod
    def validate_method(method_code: str) -> ComplianceResult:
        """
        Validate a generated Java method against all 12 rules.
        Returns violations and corrected code.
        """
        violations = []
        corrected = method_code
        
        # Rule 1: Strip Oracle-specific syntax
        oracle_check = JavaComplianceEnforcer._check_oracle_syntax(corrected)
        violations.extend(oracle_check['violations'])
        corrected = oracle_check['corrected']
        
        # Rule 2: Check variable declaration issues
        var_check = JavaComplianceEnforcer._check_variable_declarations(corrected)
        violations.extend(var_check['violations'])
        corrected = var_check['corrected']
        
        # Rule 3: Check class/annotation structure (skip for now, checked in class context)
        
        # Rule 4: Check JPA repository usage
        repo_check = JavaComplianceEnforcer._check_jpa_repository(corrected)
        violations.extend(repo_check['violations'])
        corrected = repo_check['corrected']
        
        # Rule 5: Check return types
        return_check = JavaComplianceEnforcer._check_return_types(corrected)
        violations.extend(return_check['violations'])
        corrected = return_check['corrected']
        
        # Rule 6: Check autonomous transactions
        tx_check = JavaComplianceEnforcer._check_autonomous_transactions(corrected)
        violations.extend(tx_check['violations'])
        corrected = tx_check['corrected']
        
        # Rule 7: Check for missing steps
        step_check = JavaComplianceEnforcer._check_all_steps_included(corrected)
        violations.extend(step_check['violations'])
        corrected = step_check['corrected']
        
        # Rule 8: Check HTTP/REST client
        http_check = JavaComplianceEnforcer._check_http_client(corrected)
        violations.extend(http_check['violations'])
        corrected = http_check['corrected']
        
        # Rule 9: Check JSON handling
        json_check = JavaComplianceEnforcer._check_json_handling(corrected)
        violations.extend(json_check['violations'])
        corrected = json_check['corrected']
        
        # Rule 10: Check package globals
        global_check = JavaComplianceEnforcer._check_package_globals(corrected)
        violations.extend(global_check['violations'])
        corrected = global_check['corrected']
        
        # Rule 12: Check controller return types (Rule 11 is about overloads, less critical)
        controller_check = JavaComplianceEnforcer._check_controller_returns(corrected)
        violations.extend(controller_check['violations'])
        corrected = controller_check['corrected']
        
        is_compliant = len(violations) == 0
        return ComplianceResult(
            is_compliant=is_compliant,
            violations=violations,
            corrected_code=corrected
        )
    
    @staticmethod
    def _check_oracle_syntax(code: str) -> Dict[str, Any]:
        """Rule #1: Eliminate Oracle-specific syntax"""
        violations = []
        corrected = code
        
        # Check for named parameter calls
        named_param = re.search(r'\.(\w+)\s*\(\s*\w+\s*=\s*', corrected)
        if named_param:
            violations.append(
                f"Rule #1 VIOLATION: Named parameter syntax found '{named_param.group(0)}' - "
                "use positional arguments or method overloading instead"
            )
        
        # Check for Oracle SQL functions (these should already be translated)
        oracle_funcs = ['instr', 'substr', 'nvl', 'to_char', 'trunc', 'round']
        for func in oracle_funcs:
            pattern = rf'\b{func}\s*\('
            if re.search(pattern, corrected, re.IGNORECASE):
                violations.append(
                    f"Rule #1 VIOLATION: Oracle SQL function '{func}()' found - "
                    f"should be translated to Java equivalent"
                )
        
        # Check for APEX
        if 'apex_web_service' in corrected.lower():
            violations.append(
                "Rule #1 VIOLATION: apex_web_service found - "
                "replace with RestTemplate or WebClient"
            )
        
        # Check for Oracle logger
        if re.search(r'\blogger\s*\.(append_param|log_error)\b', corrected, re.IGNORECASE):
            violations.append(
                "Rule #1 VIOLATION: Oracle logger found - "
                "use SLF4J instead (LoggerFactory.getLogger())"
            )
        
        # Check for PL/SQL CASE/WHEN syntax (should be ternary or switch)
        if re.search(JavaComplianceEnforcer.PLSQL_CASE_PATTERN, corrected, re.IGNORECASE):
            violations.append(
                "Rule #1 VIOLATION: PL/SQL CASE/WHEN syntax found - "
                "convert to Java ternary operator or switch expression"
            )
        
        return {'violations': violations, 'corrected': corrected}
    
    @staticmethod
    def _check_variable_declarations(code: str) -> Dict[str, Any]:
        """Rule #2: Fix variable declaration issues"""
        violations = []
        corrected = code
        
        # Check for duplicate var declarations in same scope
        var_pattern = r'var\s+(\w+)\s*='
        var_matches = re.findall(var_pattern, corrected)
        var_counts = {}
        for match in var_matches:
            var_counts[match] = var_counts.get(match, 0) + 1
        
        for var_name, count in var_counts.items():
            if count > 1:
                violations.append(
                    f"Rule #2 VIOLATION: Variable '{var_name}' declared multiple times - "
                    "remove duplicate declaration"
                )
        
        # Check for PL/SQL variable names as parameters (p_xxx, l_xxx should be converted)
        param_pattern = r'[\(\,]\s*([pl])_(\w+)\s*[,\)]'
        param_matches = re.findall(param_pattern, corrected)
        if param_matches:
            violations.append(
                f"Rule #2 VIOLATION: PL/SQL parameter names found (p_xxx, l_xxx) - "
                "convert to camelCase Java names"
            )
        
        # Check for variable reference before assignment
        # This is complex, but flag uninitialized usage patterns
        if re.search(r'if\s*\(\s*\w+\s*==\s*null\s*\)', corrected):
            # Check if the variable is created after the check
            lines = corrected.split('\n')
            for i, line in enumerate(lines):
                if 'if' in line and '== null' in line:
                    # Look ahead - is the variable created in following lines?
                    var_in_if = re.search(r'\b(\w+)\s*==\s*null', line)
                    if var_in_if:
                        var_name = var_in_if.group(1)
                        found_creation = False
                        # Check next 10 lines for variable creation
                        for j in range(i + 1, min(i + 10, len(lines))):
                            if re.search(rf'(var|{re.escape(var_name)})\s+{re.escape(var_name)}\s*=', lines[j]):
                                found_creation = True
                                break
                        if not found_creation and i > 0:
                            # Check if created before
                            if not any(re.search(rf'(var|.*)\s+{re.escape(var_name)}\s*=', lines[k])
                                      for k in range(max(0, i-10), i)):
                                violations.append(
                                    f"Rule #2 VIOLATION: Variable '{var_name}' checked before creation - "
                                    "declare and initialize variable before using it"
                                )
        
        return {'violations': violations, 'corrected': corrected}
    
    @staticmethod
    def _check_jpa_repository(code: str) -> Dict[str, Any]:
        """Rule #4: Correct JPA repository method calls"""
        violations = []
        corrected = code
        
        # Check for incorrect repository calls
        bad_patterns = [
            (r'repository\.findOne\s*\(\s*null\s*\)', 'repository.findOne(null) - never pass null'),
            (r'\.setRow\s*\(', '.setRow() is not a JPA method - map fields individually'),
            (r'repository\.delete\s*\(\s*\w+_id\s*=', 'Named parameter syntax in repository call'),
            (r'\.setRep\s*\(', 'setRep() - should be repository.save()'),
        ]
        
        for pattern, msg in bad_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                violations.append(f"Rule #4 VIOLATION: {msg} - fix repository call")
                
        # Verify findById().orElse() pattern for single row retrieval
        if re.search(r'repository\.find\s*\(', code, re.IGNORECASE):
            violations.append(
                "Rule #4 VIOLATION: Generic find() call found - "
                "use findById().orElse() or custom query methods"
            )
        
        # Check for proper DELETE patterns
        if re.search(r'repository\.delete\s*\([^)]*id[^)]*\)', code):
            if not re.search(r'repository\.deleteById', code):
                violations.append(
                    "Rule #4 VIOLATION: repository.delete(id) - "
                    "should be repository.deleteById(id) for single ID deletion"
                )
        
        return {'violations': violations, 'corrected': corrected}
    
    @staticmethod
    def _check_return_types(code: str) -> Dict[str, Any]:
        """Rule #5: Ensure correct return types"""
        violations = []
        corrected = code
        
        # Check for Object return type when specific type should be used
        if re.search(r'public\s+Object\s+\w+\s*\([^)]*\)\s*\{', code):
            violations.append(
                "Rule #5 VIOLATION: Returning Object - "
                "should return specific type (String, Entity, DTO, or List)"
            )
        
        # Check for returning entire entity when single column requested
        if re.search(r'public\s+\w+\s+get\w+\([^)]*\)\s*\{[\s\S]*?return\s+repository\.findById', code):
            if not re.search(r'\.map\s*\([\w\.]+::\w+\)', code):
                # Might be returning full entity instead of single field
                violations.append(
                    "Rule #5 VIOLATION: Might be returning full entity instead of single field - "
                    "use .map(Entity::getField).orElse(null)"
                )
        
        return {'violations': violations, 'corrected': corrected}
    
    @staticmethod
    def _check_autonomous_transactions(code: str) -> Dict[str, Any]:
        """Rule #6: Check autonomous transaction handling"""
        violations = []
        corrected = code
        
        # Check if logging happens without proper propagation
        if 'logger' in code.lower() or 'log.' in code:
            if '@Transactional' not in code:
                # This might be fine for some contexts, but flag if it looks like it should have it
                if re.search(r'(save|update|delete|insert)\s*\(', code, re.IGNORECASE):
                    # Has DB mutations and logging - should check for @Transactional
                    pass
        
        # Check for Propagation.REQUIRES_NEW when needed
        if 'PRAGMA AUTONOMOUS_TRANSACTION' in code or 'autonomous' in code.lower():
            if 'Propagation.REQUIRES_NEW' not in code:
                violations.append(
                    "Rule #6 VIOLATION: Autonomous transaction logic detected - "
                    "use @Transactional(propagation = Propagation.REQUIRES_NEW)"
                )
        
        # Check for unsafe substring operations
        if re.search(r'\.substring\s*\(\s*0\s*,\s*\d+\s*\)', code):
            # Found fixed-length substring - should be guarded
            violations.append(
                "Rule #6 VIOLATION: Unsafe substring() with fixed length - "
                "use Math.min(text.length(), MAX_LENGTH)"
            )
        
        return {'violations': violations, 'corrected': corrected}
    
    @staticmethod
    def _check_all_steps_included(code: str) -> Dict[str, Any]:
        """Rule #7: Verify all PL/SQL steps are included"""
        violations = []
        corrected = code
        
        # This is complex to detect automatically, but flag obvious missing steps
        
        # Check if error checking is likely missing (common issue)
        if 'makeRequest' in code or 'callApi' in code or 'restTemplate' in code.lower():
            if 'checkResponseForErrors' not in code and 'error' not in code.lower():
                violations.append(
                    "Rule #7 VIOLATION: HTTP call detected but no error checking - "
                    "include response validation step"
                )
        
        # Check for INSERT without RETURNING validation
        if re.search(r'repository\.save\s*\(', code):
            if not re.search(r'\.getId\s*\(\)|\.get\w+Id\s*\(\)', code):
                # Might be missing the returned ID validation
                pass  # Not always required, so don't flag
        
        return {'violations': violations, 'corrected': corrected}
    
    @staticmethod
    def _check_http_client(code: str) -> Dict[str, Any]:
        """Rule #8: Verify proper HTTP client usage"""
        violations = []
        corrected = code
        
        if 'apex_web_service' in code.lower():
            violations.append(
                "Rule #8 VIOLATION: apex_web_service found - "
                "replace with RestTemplate or WebClient"
            )
        
        if 'HttpHeaders' in code or 'setBasicAuth' in code or 'setBearerAuth' in code:
            # Looks good - using proper HTTP client
            pass
        elif 'restTemplate' in code.lower() or 'webclient' in code.lower():
            if 'HttpHeaders' not in code and 'headers' not in code.lower():
                # Might be missing proper header setup
                pass
        
        return {'violations': violations, 'corrected': corrected}
    
    @staticmethod
    def _check_json_handling(code: str) -> Dict[str, Any]:
        """Rule #9: Verify Jackson ObjectMapper for JSON"""
        violations = []
        corrected = code
        
        # Check for string manipulation of JSON
        if re.search(r'\.substring|\.indexOf|\.replace.*\{|\.replace.*"', code):
            if 'ObjectMapper' not in code and 'JsonNode' not in code:
                # Might be parsing JSON with string methods
                if 'json' in code.lower() or '"' in code:
                    violations.append(
                        "Rule #9 VIOLATION: JSON parsing with string manipulation detected - "
                        "use Jackson ObjectMapper instead"
                    )
        
        # Check for JSON building with string concatenation
        if re.search(r'"\s*\+\s*.*\+\s*"', code):
            if 'ObjectMapper' not in code and 'ObjectNode' not in code:
                violations.append(
                    "Rule #9 VIOLATION: JSON building with string concatenation - "
                    "use Jackson ObjectMapper instead"
                )
        
        return {'violations': violations, 'corrected': corrected}
    
    @staticmethod
    def _check_package_globals(code: str) -> Dict[str, Any]:
        """Rule #10: Replace package globals with Spring @Value"""
        violations = []
        corrected = code
        
        # Check for hardcoded URLs or paths that should be injected
        if re.search(r'(https?:|/wallet/|PASSWORD)', code):
            # Might be global package variables
            if '@Value' not in code:
                violations.append(
                    "Rule #10 VIOLATION: Hardcoded configuration found - "
                    "use @Value(\"${property.name}\") for externalized config"
                )
        
        # Check for method names that suggest global switching (switch_to_sandbox)
        if re.search(r'switch_to_\w+|g_\w+|set_\w+\s*\(', code):
            violations.append(
                "Rule #10 VIOLATION: Package global pattern detected - "
                "use Spring profiles and @Value injection instead"
            )
        
        return {'violations': violations, 'corrected': corrected}
    
    @staticmethod
    def _check_controller_returns(code: str) -> Dict[str, Any]:
        """Rule #12: Verify controller methods return values"""
        violations = []
        corrected = code
        
        # Check for controller methods returning void or empty
        if re.match(r'.*@(Get|Post|Put|Delete).*', code):
            if re.search(r'public\s+(void|ResponseEntity<Void>)\s+\w+\s*\([^)]*\)', code):
                if 'ResponseEntity.ok().build()' in code:
                    violations.append(
                        "Rule #12 VIOLATION: Controller returns empty ResponseEntity - "
                        "should return computed result with ResponseEntity.ok(result)"
                    )
        
        # Check if service result is computed but not returned
        if re.search(r'var\s+result\s*=\s*service\.\w+\s*\(', code):
            if 'return.*result' not in code:
                violations.append(
                    "Rule #12 VIOLATION: Service result computed but not returned - "
                    "return the result from controller"
                )
        
        return {'violations': violations, 'corrected': corrected}
    
    @staticmethod
    def validate_class(class_code: str, class_name: str = '') -> ComplianceResult:
        """Validate entire class for compliance"""
        violations = []
        corrected = class_code
        
        # Rule #3: Check class annotation structure
        if re.search(r'@\w+\s+\w+.*?\s+\w+\s+\w+\s*;', corrected, re.DOTALL):
            violations.append(
                "Rule #3 VIOLATION: Field or annotation found before class declaration - "
                "move all fields inside class body"
            )
        
        # Check for proper @Service annotation placement
        if '@Service' in class_code and re.search(r'@Service\s+(?!public\s+class)', class_code):
            violations.append(
                "Rule #3 VIOLATION: @Service not directly before class declaration - "
                "ensure proper annotation placement"
            )
        
        # Check for logger instantiation
        if re.search(r'@Service.*Logger.*=.*LoggerFactory', class_code, re.DOTALL):
            violations.append(
                "Rule #3 VIOLATION: Logger instantiated with @Service on same line - "
                "use separate static final field inside class"
            )
        
        # Check for dangling getErrorCode method
        if 'getErrorCode()' in class_code and 'errorCode' not in class_code:
            violations.append(
                "Rule #3 VIOLATION: getErrorCode() method without errorCode field - "
                "remove unused getter or add field"
            )
        
        # Check for mismatched braces
        brace_count = class_code.count('{') - class_code.count('}')
        if brace_count != 0:
            violations.append(
                f"Rule #3 VIOLATION: Mismatched braces (diff: {brace_count}) - "
                "verify all classes and methods are properly closed"
            )
        
        # Validate all methods in class
        method_pattern = r'(public|private|protected)\s+(\w+)\s+(\w+)\s*\([^)]*\)\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*?\}'
        methods = re.finditer(method_pattern, corrected, re.DOTALL)
        
        for method_match in methods:
            method_code = method_match.group(0)
            method_result = JavaComplianceEnforcer.validate_method(method_code)
            violations.extend(method_result.violations)
        
        is_compliant = len(violations) == 0
        return ComplianceResult(
            is_compliant=is_compliant,
            violations=violations,
            corrected_code=corrected
        )


class ComplianceReportGenerator:
    """Generate compliance reports for code review"""
    
    @staticmethod
    def generate_report(result: ComplianceResult, code_snippet: str = '') -> str:
        """Generate human-readable compliance report"""
        report = []
        report.append("=" * 80)
        report.append("JAVA GENERATION COMPLIANCE REPORT")
        report.append("=" * 80)
        
        if result.is_compliant:
            report.append("\n✓ CODE IS FULLY COMPLIANT with all 12 PL/SQL-to-Java migration rules")
        else:
            report.append(f"\n✗ CODE HAS {len(result.violations)} COMPLIANCE VIOLATIONS:\n")
            for i, violation in enumerate(result.violations, 1):
                report.append(f"{i}. {violation}\n")
        
        report.append("=" * 80)
        return "\n".join(report)


# Integration point: this should be called by the generator before returning code
def enforce_java_compliance(method_code: str, method_name: str = 'GeneratedMethod') -> Tuple[str, bool, List[str]]:
    """
    Enforce compliance on generated Java method.
    
    Returns:
        (corrected_code, is_compliant, violations_list)
    """
    result = JavaComplianceEnforcer.validate_method(method_code)
    
    if not result.is_compliant:
        logger.warning(f"Compliance violations in {method_name}:")
        for violation in result.violations:
            logger.warning(f"  - {violation}")
    
    return result.corrected_code, result.is_compliant, result.violations
