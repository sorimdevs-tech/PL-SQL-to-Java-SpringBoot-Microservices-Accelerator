"""
Domain-Specific Semantic Logic Validator for Java Output

Validates that Java code correctly implements the extracted domain logic:
1. Overload preservation and resolution
2. Assertion/validation logic correctness
3. Derivation rule implementation
4. Status transition correctness
5. Domain model equivalence
6. Stateful behavior equivalence
7. Error handling semantics

DSLV-1: Overload validation
DSLV-2: Assertion validation
DSLV-3: Derivation validation
DSLV-4: Status transition validation
DSLV-5: Domain model validation
DSLV-6: Stateful behavior validation
DSLV-7: Error semantics validation
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Issue severity levels"""
    CRITICAL = "critical"  # Logic completely missing
    HIGH = "high"  # Logic partial or incorrect
    MEDIUM = "medium"  # Edge case not handled
    LOW = "low"  # Minor deviation


@dataclass
class DomainValidationIssue:
    """Issue report for domain logic validation"""
    issue_id: str
    severity: ValidationSeverity
    category: str  # EDL-1 through EDL-7
    description: str
    plsql_pattern: str
    java_implementation: Optional[str]
    expected_behavior: str
    actual_behavior: Optional[str]
    fix_suggestion: str
    line_reference: Optional[str] = None


@dataclass
class DomainValidationReport:
    """Full validation report"""
    extraction_id: str
    java_service_name: str
    validation_status: str  # PASSED, FAILED, PARTIAL
    total_domain_elements: int
    validated_elements: int
    validation_success_rate: float  # 0.0-1.0
    critical_issues: List[DomainValidationIssue] = field(default_factory=list)
    high_issues: List[DomainValidationIssue] = field(default_factory=list)
    all_issues: List[DomainValidationIssue] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class DomainSemanticLogicValidator:
    """Validate Java implementations against domain logic specifications"""
    
    def __init__(self):
        self.issues: List[DomainValidationIssue] = []
    
    def validate_domain_implementation(
        self,
        extracted_domain_logic: Dict[str, Any],
        java_service_code: str,
        service_name: str
    ) -> DomainValidationReport:
        """
        [DSLV-1-7] Validate Java implementation against domain logic
        """
        logger.info(f"[DSLV] Validating domain logic in {service_name}")
        self.issues = []
        
        # Stage 1: Validate overloads
        logger.info("[DSLV-1] Validating procedure overloads")
        self._validate_overloads(
            extracted_domain_logic.get('overloads', []),
            java_service_code,
            service_name
        )
        
        # Stage 2: Validate assertions
        logger.info("[DSLV-2] Validating assertions")
        self._validate_assertions(
            extracted_domain_logic.get('assertions', []),
            java_service_code,
            service_name
        )
        
        # Stage 3: Validate derivations
        logger.info("[DSLV-3] Validating derivation rules")
        self._validate_derivations(
            extracted_domain_logic.get('derivations', []),
            java_service_code,
            service_name
        )
        
        # Stage 4: Validate transitions
        logger.info("[DSLV-4] Validating status transitions")
        self._validate_transitions(
            extracted_domain_logic.get('transitions', []),
            java_service_code,
            service_name
        )
        
        # Stage 5: Validate domain models
        logger.info("[DSLV-5] Validating domain models")
        self._validate_domain_models(
            extracted_domain_logic.get('domain_models', []),
            java_service_code,
            service_name
        )
        
        # Stage 6: Validate stateful behavior
        logger.info("[DSLV-6] Validating stateful behavior")
        self._validate_stateful_behavior(
            extracted_domain_logic.get('stateful_behaviors', []),
            java_service_code,
            service_name
        )
        
        # Stage 7: Validate error semantics
        logger.info("[DSLV-7] Validating error semantics")
        self._validate_error_semantics(
            extracted_domain_logic.get('error_semantics', []),
            java_service_code,
            service_name
        )
        
        # Build report
        total_elements = extracted_domain_logic.get('total_domain_elements', 0)
        validated = total_elements - len([i for i in self.issues if i.severity == ValidationSeverity.CRITICAL])
        success_rate = validated / total_elements if total_elements > 0 else 0.0
        
        # Separator
        critical = [i for i in self.issues if i.severity == ValidationSeverity.CRITICAL]
        high = [i for i in self.issues if i.severity == ValidationSeverity.HIGH]
        
        status = "PASSED" if len(critical) == 0 else ("PARTIAL" if len(high) == 0 else "FAILED")
        
        recommendations = self._generate_recommendations(self.issues)
        
        return DomainValidationReport(
            extraction_id=service_name,
            java_service_name=service_name,
            validation_status=status,
            total_domain_elements=total_elements,
            validated_elements=validated,
            validation_success_rate=success_rate,
            critical_issues=critical,
            high_issues=high,
            all_issues=self.issues,
            recommendations=recommendations,
        )

    def _validate_overloads(self, overloads: List[Any], java_code: str, service_name: str):
        """[DSLV-1] Validate procedure overload preservation"""
        
        for overload in overloads:
            proc_name_java = self._to_java_method_name(overload.procedure_name)
            
            # Check for method with same name
            method_pattern = re.compile(
                rf"(public|private)\s+\w+\s+{proc_name_java}\s*\(",
                re.IGNORECASE
            )
            
            if not method_pattern.search(java_code):
                self.issues.append(DomainValidationIssue(
                    issue_id=f"OVL-{overload.procedure_name}-missing",
                    severity=ValidationSeverity.CRITICAL,
                    category="EDL-1",
                    description=f"Procedure {overload.procedure_name} not found in Java",
                    plsql_pattern=overload.source_code,
                    java_implementation=None,
                    expected_behavior=f"Method {proc_name_java} with parameters {overload.parameters}",
                    actual_behavior="Method not found",
                    fix_suggestion=f"Add method {proc_name_java} with signature matching PL/SQL parameters",
                ))
            else:
                # Check parameter count matches
                match = method_pattern.search(java_code)
                if match:
                    method_start = match.start()
                    # Find matching closing paren
                    depth = 0
                    param_end = method_start
                    for i, char in enumerate(java_code[method_start:]):
                        if char == '(':
                            depth += 1
                        elif char == ')':
                            depth -= 1
                            if depth == 0:
                                param_end = method_start + i
                                break
                    
                    param_section = java_code[match.end()-1:param_end+1]
                    expected_param_count = len(overload.parameters)
                    
                    # Count commas to estimate parameter count
                    actual_param_count = param_section.count(',') + (1 if 'void' not in param_section.lower() else 0)
                    
                    if actual_param_count != expected_param_count:
                        self.issues.append(DomainValidationIssue(
                            issue_id=f"OVL-{overload.procedure_name}-param-mismatch",
                            severity=ValidationSeverity.HIGH,
                            category="EDL-1",
                            description=f"Parameter count mismatch for {overload.procedure_name}",
                            plsql_pattern=overload.source_code,
                            java_implementation=param_section,
                            expected_behavior=f"{expected_param_count} parameters",
                            actual_behavior=f"{actual_param_count} parameters",
                            fix_suggestion=f"Adjust method signature to match {expected_param_count} parameters",
                        ))

    def _validate_assertions(self, assertions: List[Any], java_code: str, service_name: str):
        """[DSLV-2] Validate assertion and validation logic"""
        
        for assertion in assertions:
            # Look for equivalent validation
            entity = assertion.checked_entity
            
            # Pattern: Look for if-throw or validation method call
            validation_patterns = [
                rf"if\s*\([^)]*!?\s*contains\([^)]*{entity}[^)]*\)\s*throw",
                rf"if\s*\([^)]*!?\s*exists[({]",
                rf"if\s*\([^)]*{entity}.*==\s*null.*throw",
                rf"{entity}.*validate\(",
                rf"throw.*{entity}",
            ]
            
            found = False
            for pattern in validation_patterns:
                if re.search(pattern, java_code, re.IGNORECASE):
                    found = True
                    break
            
            if not found:
                self.issues.append(DomainValidationIssue(
                    issue_id=f"ASN-{assertion.assertion_name}",
                    severity=ValidationSeverity.CRITICAL,
                    category="EDL-2",
                    description=f"Validation assertion {assertion.assertion_name} not found in Java",
                    plsql_pattern=assertion.source_code,
                    java_implementation=None,
                    expected_behavior=f"Validation: IF {assertion.condition} THEN RAISE",
                    actual_behavior="No validation found",
                    fix_suggestion=f"Add validation check: if (!...) throw new {assertion.error_message.replace(' ', '')}Exception();",
                ))

    def _validate_derivations(self, derivations: List[Any], java_code: str, service_name: str):
        """[DSLV-3] Validate derivation rule implementation"""
        
        for derivation in derivations:
            output_var = derivation.output_var
            
            # Check if output variable is computed
            patterns = [
                rf"{output_var}\s*=\s*",
                rf"\.get{output_var[0].upper() + output_var[1:]}()",
                rf"derive.*{output_var}",
            ]
            
            found = False
            for pattern in patterns:
                if re.search(pattern, java_code, re.IGNORECASE):
                    found = True
                    break
            
            if not found:
                self.issues.append(DomainValidationIssue(
                    issue_id=f"DRV-{derivation.rule_name}",
                    severity=ValidationSeverity.HIGH,
                    category="EDL-3",
                    description=f"Derivation rule {derivation.rule_name} may not be implemented",
                    plsql_pattern="\n".join(derivation.derivation_steps),
                    java_implementation=None,
                    expected_behavior=f"Derive {output_var} with inputs {derivation.input_params}",
                    actual_behavior="Derivation logic not found",
                    fix_suggestion=f"Implement derivation method: {output_var} = derive{derivation.rule_name.title()}({', '.join(derivation.input_params)});",
                ))

    def _validate_transitions(self, transitions: List[Any], java_code: str, service_name: str):
        """[DSLV-4] Validate status transition logic"""
        
        for transition in transitions:
            entity = transition.entity
            
            # Look for status update logic
            patterns = [
                rf"set.*[Ss]tatus\(",
                rf"[Ss]tatus\s*=\s*",
                rf"transition.*[Ss]tatus",
            ]
            
            found = False
            for pattern in patterns:
                if re.search(pattern, java_code, re.IGNORECASE):
                    found = True
                    break
            
            if not found and entity in service_name.lower():
                self.issues.append(DomainValidationIssue(
                    issue_id=f"TRN-{entity}-transition",
                    severity=ValidationSeverity.HIGH,
                    category="EDL-4",
                    description=f"Status transition for {entity} not fully implemented",
                    plsql_pattern=transition.source_code,
                    java_implementation=None,
                    expected_behavior=f"Transition: {transition.current_status} → {transition.allowed_next_states}",
                    actual_behavior="No status transition implementation",
                    fix_suggestion=f"Implement status transition with allowed states: {transition.allowed_next_states}",
                ))

    def _validate_domain_models(self, models: List[Any], java_code: str, service_name: str):
        """[DSLV-5] Validate domain model structure"""
        
        for model in models:
            class_name = self._to_java_class_name(model.model_name)
            
            # Look for class definition
            if f"class {class_name}" not in java_code and f"class {class_name}" not in java_code.replace(' ', ''):
                self.issues.append(DomainValidationIssue(
                    issue_id=f"MDL-{model.model_name}",
                    severity=ValidationSeverity.CRITICAL,
                    category="EDL-5",
                    description=f"Domain model {model.model_name} class not found",
                    plsql_pattern=model.source_code,
                    java_implementation=None,
                    expected_behavior=f"Class {class_name} with fields: {list(model.fields.keys())}",
                    actual_behavior="Class not found",
                    fix_suggestion=f"Create class {class_name} with @Data or getter/setter for fields: {', '.join(model.fields.keys())}",
                ))
            else:
                # Check if required fields are present
                for field_name, field_type in model.fields.items():
                    field_pattern = re.compile(
                        rf"(private|public)\s+\w+\s+{field_name}",
                        re.IGNORECASE
                    )
                    if not field_pattern.search(java_code):
                        self.issues.append(DomainValidationIssue(
                            issue_id=f"MDL-{model.model_name}-{field_name}",
                            severity=ValidationSeverity.MEDIUM,
                            category="EDL-5",
                            description=f"Field {field_name} missing from {class_name}",
                            plsql_pattern=f"{field_name} {field_type}",
                            java_implementation=None,
                            expected_behavior=f"Field {field_name}: {field_type}",
                            actual_behavior="Field not found",
                            fix_suggestion=f"Add field: private {self._map_plsql_type_to_java(field_type)} {field_name};",
                        ))

    def _validate_stateful_behavior(self, behaviors: List[Any], java_code: str, service_name: str):
        """[DSLV-6] Validate stateful/mutable behavior"""
        
        for behavior in behaviors:
            var_name = behavior.variable_name
            
            # Look for mutable state handling
            patterns = [
                rf"(StringBuilder|StringBuffer|List|Buffer|\.append|\.add|\.add.*).*{var_name}",
                rf"{var_name}\s*(\.append|\.add|\.clear)",
            ]
            
            found = False
            for pattern in patterns:
                if re.search(pattern, java_code, re.IGNORECASE):
                    found = True
                    break
            
            if not found:
                self.issues.append(DomainValidationIssue(
                    issue_id=f"SFB-{var_name}",
                    severity=ValidationSeverity.HIGH,
                    category="EDL-6",
                    description=f"Stateful behavior for {var_name} not properly implemented",
                    plsql_pattern=behavior.source_code,
                    java_implementation=None,
                    expected_behavior=f"Mutable {behavior.variable_type} with operations: {behavior.mutation_operations}",
                    actual_behavior="No mutable state handling",
                    fix_suggestion=f"Use StringBuilder/List for {var_name}; implement append/clear/spill operations",
                ))

    def _validate_error_semantics(self, errors: List[Any], java_code: str, service_name: str):
        """[DSLV-7] Validate error handling semantics"""
        
        for error in errors:
            if error.error_type == "Application Error" and error.error_code:
                # Look for error code handling
                error_code_pattern = re.compile(
                    rf"({error.error_code}|{error.error_message[:20]})",
                    re.IGNORECASE
                )
                
                if not error_code_pattern.search(java_code):
                    self.issues.append(DomainValidationIssue(
                        issue_id=f"ERR-{error.error_code}",
                        severity=ValidationSeverity.MEDIUM,
                        category="EDL-7",
                        description=f"Error code {error.error_code} not found in error handling",
                        plsql_pattern=error.source_code,
                        java_implementation=None,
                        expected_behavior=f"Throw exception with code {error.error_code}: {error.error_message}",
                        actual_behavior="Error code not referenced",
                        fix_suggestion=f"Throw new ApplicationException({error.error_code}, \"{error.error_message}\");",
                    ))
            
            # Check for autonomous transaction equivalent (if needed)
            if error.autonomous_transaction:
                if "@Transactional(propagation = Propagation.REQUIRES_NEW)" not in java_code:
                    logger.warning(f"[DSLV-7] Autonomous transaction not found for {error.error_type}")

    def _to_java_method_name(self, plsql_name: str) -> str:
        """Convert PL/SQL procedure name to Java method name"""
        parts = plsql_name.lower().split('_')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:])

    def _to_java_class_name(self, plsql_name: str) -> str:
        """Convert PL/SQL type name to Java class name"""
        parts = plsql_name.lower().split('_')
        return ''.join(p.capitalize() for p in parts)

    def _map_plsql_type_to_java(self, plsql_type: str) -> str:
        """Map PL/SQL types to Java"""
        mapping = {
            'VARCHAR2': 'String',
            'NUMBER': 'BigDecimal',
            'DATE': 'LocalDate',
            'TIMESTAMP': 'LocalDateTime',
            'BOOLEAN': 'Boolean',
            'CLOB': 'String',
            'BLOB': 'byte[]',
        }
        return mapping.get(plsql_type.upper(), 'Object')

    def _generate_recommendations(self, issues: List[DomainValidationIssue]) -> List[str]:
        """Generate recommendations based on issues"""
        recommendations = []
        
        critical = [i for i in issues if i.severity == ValidationSeverity.CRITICAL]
        high = [i for i in issues if i.severity == ValidationSeverity.HIGH]
        
        if critical:
            recommendations.append(
                f"CRITICAL: {len(critical)} critical issues must be fixed before production. "
                f"These are missing core logic elements."
            )
        
        if high:
            recommendations.append(
                f"HIGH PRIORITY: {len(high)} high-severity issues should be addressed. "
                f"These may affect business logic correctness."
            )
        
        categories = set(i.category for i in issues)
        if 'EDL-2' in categories:
            recommendations.append(
                "Ensure all validation assertions from PL/SQL are preserved. "
                "Use @Validated, @NotNull, custom validators."
            )
        
        if 'EDL-3' in categories:
            recommendations.append(
                "Verify derivation rules implement exact same logic paths, including fallback behavior."
            )
        
        if 'EDL-4' in categories:
            recommendations.append(
                "Implement state machine for status transitions with allowed state verification."
            )
        
        if 'EDL-6' in categories:
            recommendations.append(
                "Review stateful behavior: ensure StringBuilder/Collections are used correctly "
                "for appending, clearing, and spillover operations."
            )
        
        return recommendations


def create_domain_validation_report_text(report: DomainValidationReport) -> str:
    """Create human-readable validation report"""
    
    lines = [
        "=" * 100,
        "DOMAIN-SPECIFIC SEMANTIC LOGIC VALIDATION REPORT",
        "=" * 100,
        f"Service: {report.java_service_name}",
        f"Status: {report.validation_status}",
        f"Domain Elements Validated: {report.validated_elements}/{report.total_domain_elements}",
        f"Success Rate: {report.validation_success_rate * 100:.1f}%",
        "",
    ]
    
    if report.critical_issues:
        lines.append(f"CRITICAL ISSUES ({len(report.critical_issues)}):")
        lines.append("-" * 100)
        for issue in report.critical_issues:
            lines.append(f"  [{issue.category}] {issue.description}")
            lines.append(f"    Expected: {issue.expected_behavior}")
            lines.append(f"    Actual: {issue.actual_behavior or '(not found)'}")
            lines.append(f"    Fix: {issue.fix_suggestion}")
            lines.append("")
    
    if report.high_issues:
        lines.append(f"HIGH-SEVERITY ISSUES ({len(report.high_issues)}):")
        lines.append("-" * 100)
        for issue in report.high_issues:
            lines.append(f"  [{issue.category}] {issue.description}")
            lines.append(f"    Fix: {issue.fix_suggestion}")
        lines.append("")
    
    if report.recommendations:
        lines.append("RECOMMENDATIONS:")
        lines.append("-" * 100)
        for rec in report.recommendations:
            lines.append(f"  • {rec}")
        lines.append("")
    
    lines.append("=" * 100)
    
    return "\n".join(lines)
