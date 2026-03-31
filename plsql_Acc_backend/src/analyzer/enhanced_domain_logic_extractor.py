"""
Enhanced Logic Extraction for Domain-Specific Semantic Mismatches

Addresses specific logical differences:
1. Procedure overloading and overload resolution
2. Validation/assertion logic in control flow
3. Deterministic derivation rules (VAT, descriptions)
4. Status transition logic with allowed source states
5. Row-update semantics and rowtype behavior
6. Record-based domain models
7. Stateful mutable buffer behavior
8. Autonomous transaction semantics
9. Application error/assertion behavior

EDL-1: Overload pattern detection
EDL-2: Assertion/validation extraction
EDL-3: Derivation rule extraction
EDL-4: Status transition graph extraction
EDL-5: Domain model structure extraction
EDL-6: Stateful behavior extraction
EDL-7: Error semantics extraction
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OverloadPattern(Enum):
    """Overload resolution patterns [EDL-1]"""
    SAME_NAME_DIFFERENT_PARAMS = "same_name_diff_params"
    OPTIONAL_PARAMETERS = "optional_params"
    TYPE_VARIANT = "type_variant"
    ARITY_VARIANT = "arity_variant"


class AssertionType(Enum):
    """Assertion/validation patterns [EDL-2]"""
    EXISTENCE_CHECK = "exists"  # IF x NOT IN (SELECT...) THEN RAISE
    STATUS_VALIDATION = "status"  # IF status NOT IN (...) THEN RAISE
    RANGE_VALIDATION = "range"  # IF amount < 0 OR > MAX THEN RAISE
    COMPLEX_CONDITION = "complex"  # IF (cond1 AND cond2) THEN RAISE
    NULL_SAFETY = "null_check"  # IF x IS NULL THEN RAISE


class DerivationType(Enum):
    """Deterministic derivation patterns [EDL-3]"""
    LOOKUP_TABLE = "lookup"  # SELECT ... INTO var FROM table WHERE ...
    CALCULATION = "calc"  # var := formula(params)
    CASE_MAPPING = "case"  # CASE x WHEN ... THEN ... END
    FALLBACK_CHAIN = "fallback"  # x := func1() OR func2() OR default
    COMPOSITE = "composite"  # Multiple steps combined


class StatusTransition(Enum):
    """Status change patterns [EDL-4]"""
    LINEAR_PROGRESSION = "linear"  # A→B→C→D
    CONDITIONAL_BRANCH = "conditional"  # A→B OR A→C based on condition
    CYCLIC = "cyclic"  # Can transition back to prior state
    REQUIRES_EXTERNAL = "external"  # Requires external service/check
    TIME_DEPENDENT = "time"  # Depends on timestamp/duration


@dataclass
class ProcedureOverload:
    """Procedure overload variant definition [EDL-1]"""
    procedure_name: str
    variant_id: int  # Which overload (1, 2, 3...)
    parameters: List[Tuple[str, str]]  # [(name, type), ...]
    return_type: Optional[str]
    source_code: str
    line_start: int
    line_end: int
    parameter_modes: Dict[str, str] = field(default_factory=dict)  # param_name -> IN/OUT/IN OUT
    overload_resolution_logic: Optional[str] = None  # How to distinguish from other overloads


@dataclass
class ValidationAssertion:
    """Validation assertion extraction [EDL-2]"""
    assertion_name: str
    assertion_type: AssertionType
    condition: str  # The RAISE condition
    error_code: Optional[int]
    error_message: str
    checked_entity: str  # What is being checked (customer, invoice, etc.)
    source_code: str
    line_start: int
    line_end: int
    is_critical: bool = True  # Must be preserved
    
    # Override context
    overrides_conditions: List[str] = field(default_factory=list)
    fallback_behavior: Optional[str] = None


@dataclass
class DerivationRule:
    """Deterministic derivation rule [EDL-3]"""
    rule_name: str
    derivation_type: DerivationType
    input_params: List[str]
    output_var: str
    derivation_steps: List[str]  # Step-by-step logic
    fallback_cases: Dict[str, str] = field(default_factory=dict)  # condition -> result
    lookup_table: Optional[str] = None  # For lookup derivations
    source_code: str = ""
    line_start: int = 0
    line_end: int = 0


@dataclass
class StatusTransitionRule:
    """Status transition state machine [EDL-4]"""
    entity: str  # customer, invoice, payment
    current_status: str
    allowed_next_states: List[str]
    transition_condition: Optional[str]
    side_effects: List[str] = field(default_factory=list)  # What happens when transition
    required_checks: List[str] = field(default_factory=list)  # What must be verified
    source_code: str = ""


@dataclass
class DomainModel:
    """Structured domain object model [EDL-5]"""
    model_name: str
    model_type: str  # Record, Table Type, Object
    fields: Dict[str, str]  # field_name -> type
    behaviors: Dict[str, str]  # behavior_name -> implementation
    source_code: str
    is_mutable: bool = False


@dataclass
class StatefulBehavior:
    """Stateful buffer/mutable package state [EDL-6]"""
    variable_name: str
    variable_type: str  # VARCHAR2, CLOB, Table, Buffer
    initial_state: str
    mutation_operations: List[str]  # append, clear, linefeed, etc.
    spill_behavior: Optional[str]  # varchar2 to CLOB transition
    source_code: str


@dataclass
class ErrorSemantic:
    """Error handling semantics [EDL-7]"""
    error_type: str  # Application Error, Custom Exception, OTHERS
    error_code: Optional[int]
    error_message: str
    autonomous_transaction: bool  # For logging
    behavior_after_raise: Optional[str]  # Does code continue, rollback, etc.
    source_code: str


class EnhancedDomainLogicExtractor:
    """
    Extract domain-specific semantic logic that differs between
    PL/SQL and Java implementations [EDL-1 through EDL-7]
    """
    
    def __init__(self):
        self.overloads: List[ProcedureOverload] = []
        self.assertions: List[ValidationAssertion] = []
        self.derivations: List[DerivationRule] = []
        self.transitions: List[StatusTransitionRule] = []
        self.domain_models: List[DomainModel] = []
        self.stateful_behaviors: List[StatefulBehavior] = []
        self.error_semantics: List[ErrorSemantic] = []
    
    def extract_all_domain_logic(self, source: str, package_name: str = "") -> Dict[str, Any]:
        """
        [EDL-1-7] Extract all domain-specific semantic logic
        """
        logger.info(f"[EDL] Extracting domain logic from {package_name}")
        
        # Stage 1: Overload extraction
        logger.info("[EDL-1] Extracting overload patterns")
        self.overloads = self._extract_overloads(source)
        
        # Stage 2: Assertion/validation extraction
        logger.info("[EDL-2] Extracting validation assertions")
        self.assertions = self._extract_assertions(source)
        
        # Stage 3: Derivation rule extraction
        logger.info("[EDL-3] Extracting deterministic derivation rules")
        self.derivations = self._extract_derivations(source)
        
        # Stage 4: Status transition extraction
        logger.info("[EDL-4] Extracting status transition logic")
        self.transitions = self._extract_transitions(source)
        
        # Stage 5: Domain model extraction
        logger.info("[EDL-5] Extracting domain models")
        self.domain_models = self._extract_domain_models(source)
        
        # Stage 6: Stateful behavior extraction
        logger.info("[EDL-6] Extracting stateful behaviors")
        self.stateful_behaviors = self._extract_stateful_behaviors(source)
        
        # Stage 7: Error semantics extraction
        logger.info("[EDL-7] Extracting error semantics")
        self.error_semantics = self._extract_error_semantics(source)
        
        return {
            'overloads': self.overloads,
            'assertions': self.assertions,
            'derivations': self.derivations,
            'transitions': self.transitions,
            'domain_models': self.domain_models,
            'stateful_behaviors': self.stateful_behaviors,
            'error_semantics': self.error_semantics,
            'total_domain_elements': sum([
                len(self.overloads),
                len(self.assertions),
                len(self.derivations),
                len(self.transitions),
                len(self.domain_models),
                len(self.stateful_behaviors),
                len(self.error_semantics),
            ])
        }

    def _extract_overloads(self, source: str) -> List[ProcedureOverload]:
        """[EDL-1] Extract procedure overload patterns"""
        overloads = []
        
        # Find all procedure/function definitions
        proc_pattern = re.compile(
            r"(?:CREATE OR REPLACE )?(?:PROCEDURE|FUNCTION)\s+(\w+)\s*\((.*?)\)\s*(?:RETURN\s+(\w+))?",
            re.IGNORECASE | re.DOTALL
        )
        
        # Group by name to find overloads
        by_name = {}
        for match in proc_pattern.finditer(source):
            name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3)
            
            if name not in by_name:
                by_name[name] = []
            
            # Parse parameters
            params = self._parse_parameters(params_str)
            
            overload = ProcedureOverload(
                procedure_name=name,
                variant_id=len(by_name[name]) + 1,
                parameters=params,
                return_type=return_type,
                source_code=match.group(0),
                line_start=source[:match.start()].count('\n'),
                line_end=source[:match.end()].count('\n'),
            )
            
            by_name[name].append(overload)
        
        # Only return actual overloads (count > 1)
        for name, variants in by_name.items():
            if len(variants) > 1:
                logger.info(f"[EDL-1] Found {len(variants)} overloads of {name}")
                overloads.extend(variants)
        
        return overloads

    def _extract_assertions(self, source: str) -> List[ValidationAssertion]:
        """[EDL-2] Extract validation assertions and business rules"""
        assertions = []
        
        # Pattern 1: IF condition NOT IN subquery THEN RAISE
        existence_pattern = re.compile(
            r"IF\s+(\w+)\s+NOT IN\s*\((.*?)\)\s+THEN\s+RAISE\s+(\w+)\s*\((.*?)\)",
            re.IGNORECASE | re.DOTALL
        )
        
        for match in existence_pattern.finditer(source):
            checked_var = match.group(1)
            query = match.group(2)
            error_name = match.group(3)
            error_msg = match.group(4)
            
            assertion = ValidationAssertion(
                assertion_name=f"existence_{checked_var}",
                assertion_type=AssertionType.EXISTENCE_CHECK,
                condition=f"{checked_var} NOT IN ({query})",
                error_code=None,
                error_message=error_msg,
                checked_entity=checked_var,
                source_code=match.group(0),
                line_start=source[:match.start()].count('\n'),
                line_end=source[:match.end()].count('\n'),
                is_critical=True,
            )
            assertions.append(assertion)
        
        # Pattern 2: Status validation
        status_pattern = re.compile(
            r"IF\s+(\w+)\s+NOT IN\s*\((['\"][\w,\s'\"]+)\)\s+THEN\s+RAISE",
            re.IGNORECASE
        )
        
        for match in status_pattern.finditer(source):
            status_var = match.group(1)
            allowed_values = match.group(2)
            
            assertion = ValidationAssertion(
                assertion_name=f"status_check_{status_var}",
                assertion_type=AssertionType.STATUS_VALIDATION,
                condition=f"{status_var} IN ({allowed_values})",
                error_code=None,
                error_message=f"Invalid {status_var}",
                checked_entity=status_var,
                source_code=match.group(0),
                line_start=source[:match.start()].count('\n'),
                line_end=source[:match.end()].count('\n'),
                is_critical=True,
            )
            assertions.append(assertion)
        
        # Pattern 3: NULL checks
        null_pattern = re.compile(
            r"IF\s+(\w+)\s+IS\s+NULL\s+THEN\s+RAISE",
            re.IGNORECASE
        )
        
        for match in null_pattern.finditer(source):
            var_name = match.group(1)
            assertion = ValidationAssertion(
                assertion_name=f"null_check_{var_name}",
                assertion_type=AssertionType.NULL_SAFETY,
                condition=f"{var_name} IS NULL",
                error_code=None,
                error_message=f"{var_name} cannot be null",
                checked_entity=var_name,
                source_code=match.group(0),
                line_start=source[:match.start()].count('\n'),
                line_end=source[:match.end()].count('\n'),
                is_critical=True,
            )
            assertions.append(assertion)
        
        logger.info(f"[EDL-2] Found {len(assertions)} validation assertions")
        return assertions

    def _extract_derivations(self, source: str) -> List[DerivationRule]:
        """[EDL-3] Extract deterministic derivation rules"""
        derivations = []
        
        # Pattern 1: Lookup derivation
        lookup_pattern = re.compile(
            r"SELECT\s+(.*?)\s+INTO\s+(\w+)\s+FROM\s+(\w+)\s+WHERE\s+(.*?)(?:;|$)",
            re.IGNORECASE | re.DOTALL
        )
        
        for match in lookup_pattern.finditer(source):
            select_expr = match.group(1)
            output_var = match.group(2)
            table_name = match.group(3)
            where_clause = match.group(4)
            
            derivation = DerivationRule(
                rule_name=f"lookup_{output_var}",
                derivation_type=DerivationType.LOOKUP_TABLE,
                input_params=self._extract_params_from_condition(where_clause),
                output_var=output_var,
                derivation_steps=[f"SELECT {select_expr} FROM {table_name} WHERE {where_clause}"],
                lookup_table=table_name,
                source_code=match.group(0),
                line_start=source[:match.start()].count('\n'),
                line_end=source[:match.end()].count('\n'),
            )
            derivations.append(derivation)
        
        # Pattern 2: CASE derivation
        case_pattern = re.compile(
            r"CASE\s+(\w+)\s+(WHEN.*?END)",
            re.IGNORECASE | re.DOTALL
        )
        
        for match in case_pattern.finditer(source):
            input_var = match.group(1)
            case_body = match.group(2)
            
            # Extract WHEN/THEN pairs
            when_pattern = re.compile(r"WHEN\s+(.*?)\s+THEN\s+(.*?)(?=WHEN|ELSE|END)", re.IGNORECASE | re.DOTALL)
            fallbacks = {}
            for when_match in when_pattern.finditer(case_body):
                condition = when_match.group(1).strip()
                result = when_match.group(2).strip()
                fallbacks[condition] = result
            
            derivation = DerivationRule(
                rule_name=f"case_derivation_{input_var}",
                derivation_type=DerivationType.CASE_MAPPING,
                input_params=[input_var],
                output_var="case_result",
                derivation_steps=[f"CASE {input_var} {case_body}"],
                fallback_cases=fallbacks,
                source_code=match.group(0),
                line_start=source[:match.start()].count('\n'),
                line_end=source[:match.end()].count('\n'),
            )
            derivations.append(derivation)
        
        logger.info(f"[EDL-3] Found {len(derivations)} derivation rules")
        return derivations

    def _extract_transitions(self, source: str) -> List[StatusTransitionRule]:
        """[EDL-4] Extract status transition logic"""
        transitions = []
        
        # Pattern: UPDATE table SET status = 'X' WHERE status IN ('A', 'B', 'C')
        update_pattern = re.compile(
            r"UPDATE\s+(\w+)\s+SET\s+(\w+)\s*=\s*['\"]([^'\"]+)['\"]\s+WHERE\s+(\w+)\s+IN\s*\(([^)]+)\)",
            re.IGNORECASE
        )
        
        for match in update_pattern.finditer(source):
            table = match.group(1)
            status_col = match.group(2)
            new_status = match.group(3)
            where_col = match.group(4)
            where_values = match.group(5)
            
            # Parse allowed source statuses
            allowed_sources = [s.strip().strip("'\"") for s in where_values.split(',')]
            
            transition = StatusTransitionRule(
                entity=table.lower(),
                current_status="->".join(allowed_sources),
                allowed_next_states=[new_status],
                transition_condition=f"{where_col} IN ({where_values})",
                source_code=match.group(0),
            )
            transitions.append(transition)
        
        logger.info(f"[EDL-4] Found {len(transitions)} status transitions")
        return transitions

    def _extract_domain_models(self, source: str) -> List[DomainModel]:
        """[EDL-5] Extract record types and domain objects"""
        models = []
        
        # Pattern: TYPE name IS RECORD (field type, field type, ...)
        record_pattern = re.compile(
            r"TYPE\s+(\w+)\s+IS\s+RECORD\s*\((.*?)\);",
            re.IGNORECASE | re.DOTALL
        )
        
        for match in record_pattern.finditer(source):
            model_name = match.group(1)
            fields_str = match.group(2)
            
            # Parse fields
            fields = {}
            field_pattern = re.compile(r"(\w+)\s+(\w+)")
            for field_match in field_pattern.finditer(fields_str):
                field_name = field_match.group(1)
                field_type = field_match.group(2)
                fields[field_name] = field_type
            
            model = DomainModel(
                model_name=model_name,
                model_type="Record",
                fields=fields,
                behaviors={},
                source_code=match.group(0),
                is_mutable=True,  # Records can be updated
            )
            models.append(model)
        
        logger.info(f"[EDL-5] Found {len(models)} domain models")
        return models

    def _extract_stateful_behaviors(self, source: str) -> List[StatefulBehavior]:
        """[EDL-6] Extract stateful/mutable package state"""
        behaviors = []
        
        # Pattern: Package-level VARCHAR2/CLOB declarations
        var_pattern = re.compile(
            r"^\s*(\w+)\s+:\s*(VARCHAR2|CLOB|TABLE\s+OF\s+\w+)",
            re.IGNORECASE | re.MULTILINE
        )
        
        for match in var_pattern.finditer(source):
            var_name = match.group(1)
            var_type = match.group(2)
            
            # Find mutation operations on this variable
            append_pattern = re.compile(
                rf"{var_name}\s*:=\s*{var_name}\s*\|\|\s*(.*?)(?:;|$)",
                re.IGNORECASE | re.DOTALL
            )
            
            mutations = []
            for append_match in append_pattern.finditer(source):
                mutations.append(f"append: {append_match.group(1)}")
            
            behavior = StatefulBehavior(
                variable_name=var_name,
                variable_type=var_type,
                initial_state="null or empty",
                mutation_operations=mutations,
                spill_behavior="VARCHAR2 to CLOB" if var_type == "VARCHAR2" else None,
                source_code=match.group(0),
            )
            behaviors.append(behavior)
        
        logger.info(f"[EDL-6] Found {len(behaviors)} stateful behaviors")
        return behaviors

    def _extract_error_semantics(self, source: str) -> List[ErrorSemantic]:
        """[EDL-7] Extract error handling and exception semantics"""
        errors = []
        
        # Pattern 1: RAISE application error
        app_error_pattern = re.compile(
            r"RAISE_APPLICATION_ERROR\s*\((-?\d+)\s*,\s*['\"]([^'\"]+)['\"]\)",
            re.IGNORECASE
        )
        
        for match in app_error_pattern.finditer(source):
            error_code = int(match.group(1))
            error_msg = match.group(2)
            
            # Check if in autonomous transaction context
            is_autonomous = "PRAGMA AUTONOMOUS_TRANSACTION" in source[:match.start()]
            
            error = ErrorSemantic(
                error_type="Application Error",
                error_code=error_code,
                error_message=error_msg,
                autonomous_transaction=is_autonomous,
                behavior_after_raise="ROLLBACK" if not is_autonomous else "COMMIT (autonomous)",
                source_code=match.group(0),
            )
            errors.append(error)
        
        # Pattern 2: WHEN OTHERS
        others_pattern = re.compile(
            r"WHEN OTHERS THEN(.*?)(?=END|EXCEPTION)",
            re.IGNORECASE | re.DOTALL
        )
        
        for match in others_pattern.finditer(source):
            handler_code = match.group(1)
            
            error = ErrorSemantic(
                error_type="Catch-All (OTHERS)",
                error_code=None,
                error_message="Any unexpected error",
                autonomous_transaction=False,
                behavior_after_raise=handler_code.strip()[:100],
                source_code=match.group(0),
            )
            errors.append(error)
        
        logger.info(f"[EDL-7] Found {len(errors)} error semantics")
        return errors

    def _parse_parameters(self, params_str: str) -> List[Tuple[str, str]]:
        """Parse procedure parameters"""
        params = []
        param_pattern = re.compile(r"(\w+)\s+(?:(IN|OUT|IN OUT)\s+)?(\w+)")
        
        for match in param_pattern.finditer(params_str):
            name = match.group(1)
            param_type = match.group(3)
            params.append((name, param_type))
        
        return params

    def _extract_params_from_condition(self, condition: str) -> List[str]:
        """Extract parameter names from WHERE clause"""
        # Simple heuristic: find identifiers that aren't SQL keywords
        return re.findall(r"\b([a-z_]\w*)\b", condition, re.IGNORECASE)


def create_domain_logic_report(extraction: Dict[str, Any]) -> str:
    """Create human-readable extraction report"""
    
    lines = [
        "=" * 80,
        "DOMAIN-SPECIFIC SEMANTIC LOGIC EXTRACTION REPORT",
        "=" * 80,
        "",
    ]
    
    if extraction['overloads']:
        lines.append(f"[EDL-1] PROCEDURE OVERLOADS ({len(extraction['overloads'])} found)")
        for ol in extraction['overloads']:
            lines.append(f"  {ol.procedure_name} variant {ol.variant_id}: {ol.parameters}")
        lines.append("")
    
    if extraction['assertions']:
        lines.append(f"[EDL-2] VALIDATION ASSERTIONS ({len(extraction['assertions'])} found)")
        for asrt in extraction['assertions']:
            lines.append(f"  {asrt.assertion_type.value}: {asrt.assertion_name}")
            lines.append(f"    Condition: {asrt.condition}")
            if asrt.error_message:
                lines.append(f"    Error: {asrt.error_message}")
        lines.append("")
    
    if extraction['derivations']:
        lines.append(f"[EDL-3] DERIVATION RULES ({len(extraction['derivations'])} found)")
        for deriv in extraction['derivations']:
            lines.append(f"  {deriv.rule_name} [{deriv.derivation_type.value}]")
            lines.append(f"    Inputs: {deriv.input_params} → {deriv.output_var}")
        lines.append("")
    
    if extraction['transitions']:
        lines.append(f"[EDL-4] STATUS TRANSITIONS ({len(extraction['transitions'])} found)")
        for trans in extraction['transitions']:
            lines.append(f"  {trans.entity}: {trans.current_status} → {trans.allowed_next_states}")
        lines.append("")
    
    if extraction['domain_models']:
        lines.append(f"[EDL-5] DOMAIN MODELS ({len(extraction['domain_models'])} found)")
        for model in extraction['domain_models']:
            lines.append(f"  {model.model_name}: {len(model.fields)} fields")
        lines.append("")
    
    if extraction['stateful_behaviors']:
        lines.append(f"[EDL-6] STATEFUL BEHAVIORS ({len(extraction['stateful_behaviors'])} found)")
        for behavior in extraction['stateful_behaviors']:
            lines.append(f"  {behavior.variable_name} [{behavior.variable_type}]")
        lines.append("")
    
    if extraction['error_semantics']:
        lines.append(f"[EDL-7] ERROR SEMANTICS ({len(extraction['error_semantics'])} found)")
        for err in extraction['error_semantics']:
            lines.append(f"  {err.error_type}: {err.error_message}")
        lines.append("")
    
    lines.append("=" * 80)
    lines.append(f"TOTAL DOMAIN LOGIC ELEMENTS: {extraction['total_domain_elements']}")
    lines.append("=" * 80)
    
    return "\n".join(lines)
