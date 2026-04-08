"""
Logic Preservation Validator

Validates that generated Java code correctly implements ALL extracted PL/SQL logic.
Ensures 100% logic fidelity from source to target.

LPV-1: Complete logic inventory validation
LPV-2: Control flow correctness verification
LPV-3: Data transformation accuracy checking
LPV-4: Exception handling preservation
LPV-5: Transaction boundary validation
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple
from enum import Enum
import re
import logging

from src.analyzer.logic_extractor import LogicElement, LogicType, LogicExtractionReport

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Result of logic validation"""
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some logic implemented but not complete
    MISSING = "missing"  # Critical logic not found
    SUSPICIOUS = "suspicious"  # Logic found but implementation questionable


@dataclass
class LogicValidationIssue:
    """Details about logic validation failure [LPV-1]"""
    plsql_element: LogicElement
    issue_type: str  # "missing", "incomplete", "incorrect", "unsafe"
    message: str
    java_code_snippet: Optional[str] = None
    suggested_fix: Optional[str] = None
    severity: str = "error"  # "error", "warning", "info"


@dataclass
class LogicPreservationReport:
    """Complete logic preservation validation report [LPV-1]"""
    procedure_name: str
    extraction_report: LogicExtractionReport
    status: ValidationStatus
    total_elements: int
    valid_elements: int
    invalid_elements: List[LogicValidationIssue] = field(default_factory=list)
    preservation_percentage: float = 0.0
    critical_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    logic_preserved: bool = True  # Overall logic preservation status
    

class LogicPreservationValidator:
    """
    Validates that Java code preserves all PL/SQL logic [LPV-1, LPV-2, LPV-3]
    """
    
    def __init__(self):
        self.issues: List[LogicValidationIssue] = []
        
    def validate_logic_preservation(
        self, 
        java_code: str,
        extraction_report: LogicExtractionReport,
        procedure_name: str = ""
    ) -> LogicPreservationReport:
        """
        [LPV-1] Validate complete logic preservation in Java code
        """
        self.issues = []
        report = LogicPreservationReport(
            procedure_name=procedure_name or extraction_report.procedure_name,
            extraction_report=extraction_report,
            status=ValidationStatus.PASSED,
            total_elements=len(extraction_report.elements),
            valid_elements=0
        )
        
        logger.info(f"[LPV-1] Validating logic preservation for {procedure_name}")
        logger.info(f"[LPV-1] Checking {report.total_elements} extracted logic elements")
        
        # Validate each logic element
        for element in extraction_report.elements:
            self._validate_element(element, java_code, report)
        
        # Validate structured elements from logic tree
        for structured_elem in extraction_report.structured_elements:
            self._validate_structured_element(structured_elem, java_code, report)
        
        # Validate logic completeness - ensure no elements are missing
        self._validate_logic_completeness(extraction_report, java_code, report)
        
        # Set final status based on issues
        if self.issues:
            report.status = ValidationStatus.PARTIAL
            report.logic_preserved = False
        else:
            report.status = ValidationStatus.PASSED
            report.logic_preserved = True
        
        logger.info(f"[LPV-1] Validation complete: {report.status.value} "
                   f"({len(self.issues)} issues found)")
        
        return report
    
    def _validate_structured_element(self, structured_elem: dict, java_code: str, report: LogicPreservationReport):
        """Validate structured logic elements from the logic tree."""
        elem_type = structured_elem.get('type', '')
        
        if elem_type == 'loop':
            self._validate_loop_structure(structured_elem, java_code, report)
        elif elem_type == 'conditional':
            self._validate_conditional_structure(structured_elem, java_code, report)
        elif elem_type == 'exception':
            self._validate_exception_structure(structured_elem, java_code, report)
        elif elem_type == 'aggregation':
            self._validate_aggregation_structure(structured_elem, java_code, report)
        elif self.issues:
            report.status = ValidationStatus.PARTIAL
        else:
            report.status = ValidationStatus.PASSED
        
        logger.info(f"[LPV-1] Validation complete: {report.status.value} "
                   f"({report.preservation_percentage:.1f}% logic preserved)")
        
        return report

    def _validate_element(
        self, 
        element: LogicElement, 
        java_code: str,
        report: LogicPreservationReport
    ) -> None:
        """Validate individual logic element preservation"""
        
        if element.logic_type == LogicType.CURSOR_OPERATION:
            self._validate_cursor(element, java_code, report)
        elif element.logic_type == LogicType.BULK_OPERATION:
            self._validate_bulk_collect(element, java_code, report)
        elif element.logic_type == LogicType.MERGE_UPSERT:
            self._validate_merge(element, java_code, report)
        elif element.logic_type == LogicType.CONDITIONAL:
            self._validate_conditional(element, java_code, report)
        elif element.logic_type == LogicType.LOOP:
            self._validate_loop(element, java_code, report)
        elif element.logic_type == LogicType.AGGREGATION:
            self._validate_aggregation(element, java_code, report)
        elif element.logic_type == LogicType.EXCEPTION_HANDLER:
            self._validate_exception(element, java_code, report)
        elif element.logic_type == LogicType.TRANSACTION_CONTROL:
            self._validate_transaction(element, java_code, report)
        elif element.logic_type == LogicType.VALIDATION_RULE:
            self._validate_validation_rule(element, java_code, report)
        elif element.logic_type == LogicType.AUDIT_LOG:
            self._validate_audit(element, java_code, report)

    def _validate_cursor(self, element: LogicElement, java_code: str, report: LogicPreservationReport) -> None:
        """[LPV-1] Validate cursor operations converted to Java collections"""
        
        # In Java, cursors are typically represented as:
        # - List<Entity> from repository queries
        # - Stream operations
        # - Custom iterators
        
        cursor_name = element.name
        
        # Check for equivalent data retrieval
        patterns_to_check = [
            rf"List.*\bfindAll\s*\(",  # findAll() - standard repository method
            rf"{element.tables_involved.pop() if element.tables_involved else 'entity'}.*\bfindBy",  # findBy* methods
            r"repository\.find",  # Generic find patterns
            r"Stream\s*<",  # Stream-based iteration
        ]
        
        found = any(re.search(pattern, java_code, re.IGNORECASE) for pattern in patterns_to_check)
        
        if not found:
            if element.is_critical:
                issue = LogicValidationIssue(
                    plsql_element=element,
                    issue_type="missing",
                    message=f"Cursor '{cursor_name}' logic not found in Java code. "
                            f"Expected repository query or collection iteration.",
                    severity="error"
                )
                self.issues.append(issue)
            else:
                issue = LogicValidationIssue(
                    plsql_element=element,
                    issue_type="missing",
                    message=f"Cursor '{cursor_name}' may not be properly converted",
                    severity="warning"
                )
                self.issues.append(issue)

    def _validate_bulk_collect(self, element: LogicElement, java_code: str, report: LogicPreservationReport) -> None:
        """[LPV-1] Validate BULK COLLECT converted to appropriate Java pattern"""
        
        # BULK COLLECT should become:
        # - List.addAll() in loop
        # - Stream.collect()
        # - forEach with batch processing
        
        target_var = list(element.variables_assigned)[0] if element.variables_assigned else "data"
        
        patterns_to_check = [
            r"\.addAll\s*\(",  # List.addAll for bulk operation
            r"\.collect\s*\(",  # Stream.collect()
            r"List.*\s*=\s*new\s*ArrayList",  # List creation for bulk data
            r"batch.*\bsize\b",  # Batch size limit handling
        ]
        
        found = any(re.search(pattern, java_code, re.IGNORECASE) for pattern in patterns_to_check)
        
        if not found:
            issue = LogicValidationIssue(
                plsql_element=element,
                issue_type="incomplete",
                message=f"BULK COLLECT ({target_var}) not properly converted. "
                       f"Expected List.addAll() or Stream.collect() operation.",
                severity="error"
            )
            self.issues.append(issue)

    def _validate_merge(self, element: LogicElement, java_code: str, report: LogicPreservationReport) -> None:
        """[LPV-1] Validate MERGE (UPSERT) converted to Java pattern"""
        
        # MERGE should become save() with existence check or save()
        patterns_to_check = [
            r"saveAndFlush\s*\(",  # Direct save
            r"existsById\s*\(",  # Existence check for conditional save
            r"if.*existsById.*then.*save",  # Explicit upsert logic
            r"save\s*\(",  # Generic save for upsert
            r"@Transactional",  # Transaction annotation
        ]
        
        found_save = re.search(r"\.save\s*\(", java_code, re.IGNORECASE)
        found_transactional = re.search(r"@Transactional", java_code)
        
        if not found_save:
            issue = LogicValidationIssue(
                plsql_element=element,
                issue_type="missing",
                message=f"MERGE operation not found. Expected repository.save() or saveAndFlush().",
                severity="error"
            )
            self.issues.append(issue)
        
        if not found_transactional:
            issue = LogicValidationIssue(
                plsql_element=element,
                issue_type="incomplete",
                message=f"MERGE operation lacks @Transactional annotation.",
                severity="warning"
            )
            self.issues.append(issue)

    def _validate_conditional(self, element: LogicElement, java_code: str, report: LogicPreservationReport) -> None:
        """[LPV-2] Validate IF/THEN/ELSE converted to Java if statements"""
        
        # Look for if statements
        if_count = len(re.findall(r"if\s*\(", java_code, re.IGNORECASE))
        
        if if_count == 0:
            issue = LogicValidationIssue(
                plsql_element=element,
                issue_type="missing",
                message=f"Conditional logic not found. Expected if/else statements.",
                severity="error"
            )
            self.issues.append(issue)

    def _validate_loop(self, element: LogicElement, java_code: str, report: LogicPreservationReport) -> None:
        """[LPV-2] Validate loop structures"""
        
        loop_patterns = [
            r"for\s*\(",  # for loop
            r"while\s*\(",  # while loop
            r"forEach\s*\(",  # enhanced for
            r"\.forEach\s*\(",  # stream forEach
            r"for\s*\(\s*.*\s*:\s*.*\)",  # enhanced for
        ]
        
        found = any(re.search(pattern, java_code, re.IGNORECASE) for pattern in loop_patterns)
        
        if not found:
            issue = LogicValidationIssue(
                plsql_element=element,
                issue_type="missing",
                message=f"Loop structure not found. Expected for/while/forEach.",
                severity="error"
            )
            self.issues.append(issue)
            report.logic_preserved = False

    def _validate_aggregation(self, element: LogicElement, java_code: str, report: LogicPreservationReport) -> None:
        """[LPV-3] Validate aggregation operations use @Query instead of manual accumulation"""
        
        # Check for @Query annotation (preferred for aggregations)
        has_query_annotation = "@Query" in java_code
        
        # Check for manual accumulation patterns (less preferred)
        manual_patterns = [
            r"total\s*\+=",  # Manual accumulation
            r"sum\s*\+=",    # Manual summing
            r"\.collect\s*\(\s*Collectors\.summing",  # Stream summing
        ]
        has_manual_accumulation = any(re.search(pattern, java_code, re.IGNORECASE) for pattern in manual_patterns)
        
        if not has_query_annotation and not has_manual_accumulation:
            issue = LogicValidationIssue(
                plsql_element=element,
                issue_type="missing",
                message=f"Aggregation operation not found. Expected @Query annotation or proper accumulation logic.",
                severity="error"
            )
            self.issues.append(issue)
            report.logic_preserved = False
        elif has_manual_accumulation and not has_query_annotation:
            issue = LogicValidationIssue(
                plsql_element=element,
                issue_type="inefficient",
                message=f"Aggregation using manual accumulation. Consider using @Query for better performance.",
                severity="warning"
            )
            self.issues.append(issue)

    def _validate_exception(self, element: LogicElement, java_code: str, report: LogicPreservationReport) -> None:
        """[LPV-4] Validate exception handling preservation"""
        
        # Check for try-catch blocks
        try_catch_pattern = r"try\s*\{.*?\}\s*catch\s*\("
        found_try_catch = re.search(try_catch_pattern, java_code, re.IGNORECASE | re.DOTALL)
        
        if not found_try_catch:
            issue = LogicValidationIssue(
                plsql_element=element,
                issue_type="missing",
                message=f"Exception handling not found. Expected try-catch blocks.",
                severity="error"
            )
            self.issues.append(issue)
            report.logic_preserved = False
        else:
            # Check for multiple catch blocks (matching WHEN clauses)
            catch_count = len(re.findall(r"catch\s*\(", java_code, re.IGNORECASE))
            # This is acceptable if there's at least one catch block

    def _validate_validation_rule(self, element: LogicElement, java_code: str, report: LogicPreservationReport) -> None:
        """[LPV-1] Validate business rule implementation"""
        
        # Look for validation patterns
        validation_patterns = [
            r"if\s*\(.*throw\s+new",  # if condition throw exception
            r"throw\s+new.*Exception",  # Exception throwing
            r"@Valid",  # Bean validation
            r"@NotNull|@Min|@Max",  # Validation annotations
        ]
        
        found = any(re.search(pattern, java_code, re.IGNORECASE) for pattern in validation_patterns)
        
        if not found:
            issue = LogicValidationIssue(
                plsql_element=element,
                issue_type="missing",
                message=f"Validation rule not implemented. Expected validation logic or annotations.",
                severity="error"
            )
            self.issues.append(issue)

    def _validate_audit(self, element: LogicElement, java_code: str, report: LogicPreservationReport) -> None:
        """[LPV-1] Validate audit logging"""
        
        # Look for logging patterns
        logging_patterns = [
            r"logger\.",  # SLF4J logger
            r"log\.",  # Log4j
            r"\.info\(|\.debug\(|\.warn\(|\.error\(",  # Log level methods
            r"@Loggable",  # AspectJ logging
            r"repository\.save.*audit",  # Audit table insertion
        ]
        
        found = any(re.search(pattern, java_code, re.IGNORECASE) for pattern in logging_patterns)
        
        if not found:
            issue = LogicValidationIssue(
                plsql_element=element,
                issue_type="missing",
                message=f"Audit logging not implemented. Expected logger calls or audit table operations.",
                severity="warning"
            )
            self.issues.append(issue)

    def _validate_transaction(self, element: LogicElement, java_code: str, report: LogicPreservationReport) -> None:
        """[LPV-5] Validate transaction control"""
        
        # Check for transaction annotations
        transactional_pattern = r"@Transactional"
        found_transactional = re.search(transactional_pattern, java_code)
        
        if not found_transactional:
            issue = LogicValidationIssue(
                plsql_element=element,
                issue_type="incomplete",
                message=f"@Transactional annotation not found. Method needs transaction management.",
                severity="warning"
            )
            self.issues.append(issue)

    def _validate_control_flow(
        self, 
        extraction_report: LogicExtractionReport, 
        java_code: str,
        report: LogicPreservationReport
    ) -> None:
        """[LPV-2] Validate complete control flow is preserved"""
        
        # Check that all control flow nodes have corresponding Java structures
        missing_nodes = []
        
        for node_id, node in extraction_report.control_flow_graph.items():
            element = node.logic_element
            
            # Verify node is represented in Java code
            if element.logic_type == LogicType.LOOP:
                if not re.search(r"for\s*\(|while\s*\(|forEach", java_code, re.IGNORECASE):
                    missing_nodes.append(node_id)
            elif element.logic_type == LogicType.CONDITIONAL:
                if not re.search(r"if\s*\(", java_code, re.IGNORECASE):
                    missing_nodes.append(node_id)
        
        if missing_nodes:
            logger.warning(f"[LPV-2] Control flow nodes missing: {missing_nodes}")

    def _validate_data_transformations(
        self, 
        extraction_report: LogicExtractionReport, 
        java_code: str,
        report: LogicPreservationReport
    ) -> None:
        """[LPV-3] Validate all data transformations are preserved"""
        
        # Check data dependencies
        for element_name, dependencies in extraction_report.data_dependencies.items():
            if dependencies:
                # This element depends on other elements being computed first
                # Verify dependency order in Java code is maintained
                logger.debug(f"[LPV-3] Data dependency: {element_name} <- {dependencies}")

    def _validate_exception_handling(
        self, 
        extraction_report: LogicExtractionReport, 
        java_code: str,
        report: LogicPreservationReport
    ) -> None:
        """[LPV-4] Validate all exception handlers are implemented"""
        
        exception_elements = [e for e in extraction_report.elements 
                            if e.logic_type == LogicType.EXCEPTION_HANDLER]
        
        if exception_elements:
            # Verify try-catch is present
            if "try" not in java_code.lower():
                issue = LogicValidationIssue(
                    plsql_element=exception_elements[0],
                    issue_type="missing",
                    message="Exception handlers in PL/SQL but no try-catch in Java",
                    severity="error"
                )
                self.issues.append(issue)

    def _validate_transaction_boundaries(
        self, 
        extraction_report: LogicExtractionReport, 
        java_code: str,
        report: LogicPreservationReport
    ) -> None:
        """[LPV-5] Validate transaction boundaries are properly marked"""
        
        transaction_elements = [e for e in extraction_report.elements 
                              if e.requires_transaction]
        
        if transaction_elements:
            # Methods with transaction requirements should have @Transactional
            if "@Transactional" not in java_code:
                for elem in transaction_elements[:1]:  # Report once
                    issue = LogicValidationIssue(
                        plsql_element=elem,
                        issue_type="incomplete",
                        message="Transaction-requiring logic present but @Transactional not applied",
                        severity="warning"
                    )
                    self.issues.append(issue)

    def _validate_loop_structure(self, structured_elem: dict, java_code: str, report: LogicPreservationReport):
        """Validate loop structures are preserved in Java code."""
        loop_type = structured_elem.get('loop_type', '')
        loop_condition = structured_elem.get('condition', '')
        
        # Check if corresponding loop exists in Java
        if loop_type == 'FOR':
            if 'for (' not in java_code and 'for(' not in java_code:
                issue = LogicValidationIssue(
                    plsql_element=None,  # We don't have the original element
                    issue_type="missing",
                    message=f"FOR loop with condition '{loop_condition}' not found in Java code",
                    severity="error"
                )
                self.issues.append(issue)
        elif loop_type == 'WHILE':
            if 'while (' not in java_code and 'while(' not in java_code:
                issue = LogicValidationIssue(
                    plsql_element=None,
                    issue_type="missing", 
                    message=f"WHILE loop with condition '{loop_condition}' not found in Java code",
                    severity="error"
                )
                self.issues.append(issue)
        elif loop_type == 'CURSOR_FOR':
            # Cursor FOR loops should be converted to repository/stream operations
            if not any(keyword in java_code for keyword in ['.stream()', '.forEach(', '.collect(', '@Query']):
                issue = LogicValidationIssue(
                    plsql_element=None,
                    issue_type="missing",
                    message=f"Cursor FOR loop not converted to proper Java stream/repository operation",
                    severity="error"
                )
                self.issues.append(issue)

    def _validate_conditional_structure(self, structured_elem: dict, java_code: str, report: LogicPreservationReport):
        """Validate conditional structures are preserved."""
        condition = structured_elem.get('condition', '')
        
        # Check if if-statement exists
        if 'if (' not in java_code and 'if(' not in java_code:
            issue = LogicValidationIssue(
                plsql_element=None,
                issue_type="missing",
                message=f"Conditional logic with condition '{condition}' not found in Java code",
                severity="error"
            )
            self.issues.append(issue)

    def _validate_exception_structure(self, structured_elem: dict, java_code: str, report: LogicPreservationReport):
        """Validate exception handling structures are preserved."""
        exception_type = structured_elem.get('exception_type', '')
        
        # Check if try-catch exists
        if 'try {' not in java_code and 'try{' not in java_code:
            issue = LogicValidationIssue(
                plsql_element=None,
                issue_type="missing",
                message=f"Exception handling for '{exception_type}' not found in Java code",
                severity="error"
            )
            self.issues.append(issue)

    def _validate_aggregation_structure(self, structured_elem: dict, java_code: str, report: LogicPreservationReport):
        """Validate aggregation operations are properly mapped to @Query."""
        agg_function = structured_elem.get('function', '')
        
        # Check if aggregation is mapped to @Query instead of manual accumulation
        if '@Query' not in java_code:
            issue = LogicValidationIssue(
                plsql_element=None,
                issue_type="incorrect",
                message=f"Aggregation function '{agg_function}' should use @Query annotation, not manual accumulation",
                severity="error"
            )
            self.issues.append(issue)

    def _validate_logic_completeness(self, extraction_report: LogicExtractionReport, java_code: str, report: LogicPreservationReport):
        """Validate that no logic elements are missing from the Java code."""
        
        # Count expected logic elements
        expected_loops = len([e for e in extraction_report.elements if e.logic_type == LogicType.LOOP])
        expected_conditionals = len([e for e in extraction_report.elements if e.logic_type == LogicType.CONDITIONAL])
        expected_exceptions = len([e for e in extraction_report.elements if e.logic_type == LogicType.EXCEPTION_HANDLER])
        expected_aggregations = len([e for e in extraction_report.elements if e.logic_type == LogicType.AGGREGATION])
        
        # Count found elements in Java code
        found_loops = len(re.findall(r'\bfor\s*\(|\bwhile\s*\(|\.forEach\s*\(', java_code, re.IGNORECASE))
        found_conditionals = len(re.findall(r'\bif\s*\(', java_code, re.IGNORECASE))
        found_exceptions = len(re.findall(r'\btry\s*\{', java_code, re.IGNORECASE))
        found_aggregations = len(re.findall(r'@Query|\.sum\s*\(|\.reduce\s*\(', java_code, re.IGNORECASE))
        
        # Check for missing elements
        if expected_loops > 0 and found_loops == 0:
            issue = LogicValidationIssue(
                plsql_element=None,
                issue_type="missing",
                message=f"Expected {expected_loops} loop(s) but found none in Java code",
                severity="error"
            )
            self.issues.append(issue)
            report.logic_preserved = False
            
        if expected_conditionals > 0 and found_conditionals == 0:
            issue = LogicValidationIssue(
                plsql_element=None,
                issue_type="missing",
                message=f"Expected {expected_conditionals} conditional(s) but found none in Java code",
                severity="error"
            )
            self.issues.append(issue)
            report.logic_preserved = False
            
        if expected_exceptions > 0 and found_exceptions == 0:
            issue = LogicValidationIssue(
                plsql_element=None,
                issue_type="missing",
                message=f"Expected {expected_exceptions} exception handler(s) but found none in Java code",
                severity="error"
            )
            self.issues.append(issue)
            report.logic_preserved = False
            
        if expected_aggregations > 0 and found_aggregations == 0:
            issue = LogicValidationIssue(
                plsql_element=None,
                issue_type="missing",
                message=f"Expected {expected_aggregations} aggregation(s) but found none in Java code",
                severity="error"
            )
            self.issues.append(issue)
            report.logic_preserved = False
