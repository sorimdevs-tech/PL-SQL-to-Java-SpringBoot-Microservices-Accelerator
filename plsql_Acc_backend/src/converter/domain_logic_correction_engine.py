"""
Domain-Specific Logic Correction Engine

Auto-generates fixes for domain logic mismatches:
1. Overload method creation
2. Assertion implementation
3. Derivation rule implementation
4. Status transition implementation
5. Domain model enhancement
6. Stateful behavior correction
7. Error handling improvement

DSLC-1: Overload correction templates
DSLC-2: Assertion correction templates
DSLC-3: Derivation correction templates
DSLC-4: Status transition correction templates
DSLC-5: Domain model correction templates
DSLC-6: Stateful behavior correction templates
DSLC-7: Error handling correction templates
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class CodeFix:
    """A corrective code change"""
    fix_id: str
    category: str  # DSLC-1 through DSLC-7
    target_class: str
    location: str  # method, class level, etc
    code_template: str
    explanation: str
    required_imports: List[str] = None


class DomainLogicCorrectionEngine:
    """
    Generate corrective code patterns for domain logic mismatches
    """
    
    def __init__(self):
        self.fixes: List[CodeFix] = []
    
    def generate_corrections(
        self,
        validation_issues: List[Any],
        service_name: str,
        package_name: str
    ) -> Dict[str, Any]:
        """
        [DSLC-1-7] Generate corrections for all validation issues
        """
        logger.info(f"[DSLC] Generating corrections for {service_name}")
        
        self.fixes = []
        
        for issue in validation_issues:
            if issue.category == "EDL-1":
                self._generate_overload_fix(issue, service_name, package_name)
            elif issue.category == "EDL-2":
                self._generate_assertion_fix(issue, service_name, package_name)
            elif issue.category == "EDL-3":
                self._generate_derivation_fix(issue, service_name, package_name)
            elif issue.category == "EDL-4":
                self._generate_transition_fix(issue, service_name, package_name)
            elif issue.category == "EDL-5":
                self._generate_domain_model_fix(issue, service_name, package_name)
            elif issue.category == "EDL-6":
                self._generate_stateful_behavior_fix(issue, service_name, package_name)
            elif issue.category == "EDL-7":
                self._generate_error_semantics_fix(issue, service_name, package_name)
        
        return {
            'total_fixes': len(self.fixes),
            'fixes_by_category': self._group_by_category(),
            'fixes': self.fixes,
        }
    
    def _generate_overload_fix(self, issue: Any, service_name: str, package_name: str):
        """[DSLC-1] Generate overload method fix"""
        
        # Extract method name from issue
        method_name = issue.issue_id.split('-')[1]
        
        template = f'''
    /**
     * [DSLC-1] Overload variant of {method_name}
     * Corresponds to PL/SQL procedure {method_name}
     * Preserves overload semantics from original
     */
    public void {self._to_camel_case(method_name)}(/* parameters from PL/SQL */) {{
        // CRITICAL: Implement exact parameter handling and return type
        // Match PL/SQL parameter modes (IN, OUT, IN OUT)
        
        // Placeholder: Replace with actual implementation
        logger.info("[DSLC-1] {method_name} overload invoked");
        throw new UnsupportedOperationException(
            "DSLC-1: Overload for {method_name} must be implemented with correct semantics"
        );
    }}
'''
        
        fix = CodeFix(
            fix_id=issue.issue_id,
            category="EDL-1",
            target_class=service_name,
            location="class",
            code_template=template,
            explanation="Add overload method with correct parameter handling and return type",
            required_imports=[
                "org.slf4j.Logger",
                "org.slf4j.LoggerFactory",
            ]
        )
        self.fixes.append(fix)

    def _generate_assertion_fix(self, issue: Any, service_name: str, package_name: str):
        """[DSLC-2] Generate assertion/validation fix"""
        
        entity = issue.plsql_pattern.split()[-1] if issue.plsql_pattern else "entity"
        
        template = f'''
    /**
     * [DSLC-2] Validation assertion from PL/SQL
     * Error message: {issue.expected_behavior}
     */
    private void validate{self._to_pascal_case(entity)}(/* parameters */) {{
        // CRITICAL: This validation must pass or the operation must fail
        
        // Pattern 1: Existence check
        if (!repository.existsBy{self._to_pascal_case(entity)}(/* id */)) {{
            throw new BusinessRuleViolationException(
                "BUSINESS_RULE_001",
                "{issue.expected_behavior}"
            );
        }}
        
        // Pattern 2: Status validation
        // if (status != null && !ALLOWED_STATUSES.contains(status)) {{ throw ... }}
        
        // Pattern 3: Null safety
        // if (entity == null) {{ throw new ValidationException(...); }}
        
        logger.info("[DSLC-2] Validation for {{}} passed", {entity}Id);
    }}
'''
        
        fix = CodeFix(
            fix_id=issue.issue_id,
            category="EDL-2",
            target_class=service_name,
            location="method",
            code_template=template,
            explanation="Add validation method with business rule enforcement",
            required_imports=[
                "org.springframework.stereotype.Component",
                "lombok.extern.slf4j.Slf4j",
            ]
        )
        self.fixes.append(fix)

    def _generate_derivation_fix(self, issue: Any, service_name: str, package_name: str):
        """[DSLC-3] Generate derivation rule fix"""
        
        output_var = issue.expected_behavior.split()[-1] if issue.expected_behavior else "result"
        
        template = f'''
    /**
     * [DSLC-3] Deterministic derivation rule from PL/SQL
     * Rule: {issue.expected_behavior}
     * This must produce IDENTICAL results to PL/SQL logic
     */
    private String derive{self._to_pascal_case(output_var)}(Map<String, Object> params) {{
        
        // Step 1: Lookup from table/cache
        // String {output_var} = lookupTable.get(params.get("key"));
        // if ({output_var} != null) return {output_var};
        
        // Step 2: Calculate/Case mapping
        // switch (params.get("type")) {{
        //     case "A": return "VALUE_A";
        //     case "B": return "VALUE_B";
        //     default: return getDefaultValue();
        // }}
        
        // Step 3: Fallback chain
        // return deriveFirstOption(params)
        //     .orElse(deriveSecondOption(params))
        //     .orElse(getDefaultValue());
        
        logger.info("[DSLC-3] Derived {{}} = {{}}", "{output_var}", {output_var});
        return {output_var};
    }}
    
    private Optional<String> deriveFirstOption(Map<String, Object> params) {{
        // Attempt first derivation path
        return Optional.empty();
    }}
    
    private Optional<String> deriveSecondOption(Map<String, Object> params) {{
        // Attempt second derivation path (fallback)
        return Optional.empty();
    }}
    
    private String getDefaultValue() {{
        // Return default if all derivations fail
        return null;
    }}
'''
        
        fix = CodeFix(
            fix_id=issue.issue_id,
            category="EDL-3",
            target_class=service_name,
            location="method",
            code_template=template,
            explanation="Implement deterministic derivation with exact fallback logic",
            required_imports=[
                "java.util.Optional",
                "java.util.Map",
            ]
        )
        self.fixes.append(fix)

    def _generate_transition_fix(self, issue: Any, service_name: str, package_name: str):
        """[DSLC-4] Generate status transition fix"""
        
        entity = issue.expected_behavior.split(':')[0].strip() if ':' in issue.expected_behavior else "entity"
        
        template = f'''
    /**
     * [DSLC-4] Status transition logic from PL/SQL
     * Ensures only valid state transitions are allowed
     * {issue.expected_behavior}
     */
    public void transitionStatus(Long {entity}Id, String newStatus) {{
        
        {self._to_pascal_case(entity)} {entity} = repository.findById({entity}Id)
            .orElseThrow(() -> new EntityNotFoundException("{self._to_pascal_case(entity)} not found"));
        
        // GET current status
        String currentStatus = {entity}.getStatus();
        
        // VALIDATE: Is this transition allowed?
        Set<String> allowedTransitions = getAllowedTransitions(currentStatus);
        if (!allowedTransitions.contains(newStatus)) {{
            throw new InvalidStateTransitionException(
                "Cannot transition from " + currentStatus + " to " + newStatus
            );
        }}
        
        // PERFORM: Apply transition with side effects
        {entity}.setStatus(newStatus);
        {entity}.setStatusChangeDate(LocalDateTime.now());
        
        // EXECUTE: Any side effects (audit, logging, notifications)
        auditLog({entity}Id, currentStatus, newStatus);
        
        // PERSIST: Save the new state
        repository.save({entity});
        
        logger.info("[DSLC-4] Transitioned {{}} from {{}} to {{}}", 
            {entity}Id, currentStatus, newStatus);
    }}
    
    private Set<String> getAllowedTransitions(String currentStatus) {{
        Map<String, Set<String>> stateGraph = Map.ofEntries(
            Map.entry("DRAFT", Set.of("SUBMITTED")),
            Map.entry("SUBMITTED", Set.of("APPROVED", "REJECTED")),
            Map.entry("APPROVED", Set.of("COMPLETED")),
            Map.entry("REJECTED", Set.of("DRAFT"))
        );
        return stateGraph.getOrDefault(currentStatus, Set.of());
    }}
    
    private void auditLog(Long {entity}Id, String oldStatus, String newStatus) {{
        logger.info("[DSLC-4-AUDIT] {{}} status changed: {{}} → {{}}", 
            {entity}Id, oldStatus, newStatus);
    }}
'''
        
        fix = CodeFix(
            fix_id=issue.issue_id,
            category="EDL-4",
            target_class=service_name,
            location="method",
            code_template=template,
            explanation="Implement state machine with validation of allowed transitions",
            required_imports=[
                "java.util.Set",
                "java.util.Map",
                "java.time.LocalDateTime",
            ]
        )
        self.fixes.append(fix)

    def _generate_domain_model_fix(self, issue: Any, service_name: str, package_name: str):
        """[DSLC-5] Generate domain model enhancement"""
        
        model_name = issue.issue_id.split('-')[1]
        field_list = issue.expected_behavior.split("fields:")[-1].strip() if "fields:" in issue.expected_behavior else ""
        
        template = f'''
/**
 * [DSLC-5] Domain model from PL/SQL record type-
 * Equivalent to PL/SQL {model_name} record
 * All fields and behaviors preserved from source
 */
@Data
@Entity
@Table(name = "{self._to_snake_case(model_name)}")
public class {self._to_pascal_case(model_name)} {{
    
    @Id
    private Long id;
    
    // Record fields from PL/SQL
    // CRITICAL: Add all fields from PL/SQL TYPE definition
    // private String fieldName;
    // private BigDecimal amount;
    // private LocalDate createdDate;
    
    // Behaviors/methods from PL/SQL record usage
    
    // Audit fields
    @CreationTimestamp
    private LocalDateTime createdAt;
    
    @UpdateTimestamp
    private LocalDateTime updatedAt;
    
    @Version
    private Long version;  // For optimistic locking
    
    // Constructor
    public {self._to_pascal_case(model_name)}(/* parameters */) {{
        // Initialize all required fields
    }}
    
    // Validation
    @PrePersist
    @PreUpdate
    private void validate() {{
        // Implement domain-level validation
    }}
    
    // [DSLC-5] Override equals/hashCode if mutable rowtype behavior needed
    @Override
    public boolean equals(Object o) {{
        // Rowtype equality checking
        return super.equals(o);
    }}
}}
'''
        
        fix = CodeFix(
            fix_id=issue.issue_id,
            category="EDL-5",
            target_class=model_name,
            location="class",
            code_template=template,
            explanation="Create complete domain model class with all fields and behaviors from PL/SQL record",
            required_imports=[
                "org.springframework.data.jpa.domain.support.AuditingEntityListener",
                "org.hibernate.annotations.CreationTimestamp",
                "org.hibernate.annotations.UpdateTimestamp",
                "jakarta.persistence.*",
                "lombok.Data",
            ]
        )
        self.fixes.append(fix)

    def _generate_stateful_behavior_fix(self, issue: Any, service_name: str, package_name: str):
        """[DSLC-6] Generate stateful behavior fix"""
        
        var_name = issue.issue_id.split('-')[1]
        
        template = f'''
    /**
     * [DSLC-6] Stateful mutable buffer from PL/SQL package state
     * Equivalent to PL/SQL package-level VARCHAR2/CLOB variable
     * Handles append, clear, linefeed, and spillover operations
     */
    private static class {self._to_pascal_case(var_name)}Buffer {{
        
        private static final int VARCHAR2_MAX = 32767;  // PL/SQL VARCHAR2 limit
        private StringBuilder buffer = new StringBuilder();
        private boolean spilledToClob = false;
        
        public void append(String value) {{
            if (value == null) return;
            
            // Append with size checking
            buffer.append(value);
            
            // [DSLC-6] Check for spillover: CharField to CLOB
            if (buffer.length() > VARCHAR2_MAX) {{
                logger.debug("[DSLC-6] Spillover: %,d bytes exceeded", buffer.length());
                spilledToClob = true;
            }}
        }}
        
        public void appendLinefeed() {{
            // PL/SQL linefeed equivalent
            buffer.append("\\n");
        }}
        
        public void clear() {{
            // Clear mutable state (optional in PL/SQL)
            buffer = new StringBuilder();
            spilledToClob = false;
        }}
        
        public String getContent() {{
            // Return current buffer content
            return buffer.toString();
        }}
        
        public String getAndClear() {{
            // Some PL/SQL code clears on read
            String content = buffer.toString();
            clear();
            return content;
        }}
        
        public boolean hasSpilledToClob() {{
            return spilledToClob;
        }}
    }}
    
    // Usage in service
    private static final {self._to_pascal_case(var_name)}Buffer {var_name} = new {self._to_pascal_case(var_name)}Buffer();
    
    public void processWith{self._to_pascal_case(var_name)}() {{
        {var_name}.clear();
        {var_name}.append("Processing...");
        {var_name}.appendLinefeed();
        // ... more operations
        String result = {var_name}.getAndClear();
    }}
'''
        
        fix = CodeFix(
            fix_id=issue.issue_id,
            category="EDL-6",
            target_class=service_name,
            location="class",
            code_template=template,
            explanation="Create stateful buffer class that mimics PL/SQL package variable behavior",
            required_imports=[
                "lombok.extern.slf4j.Slf4j",
            ]
        )
        self.fixes.append(fix)

    def _generate_error_semantics_fix(self, issue: Any, service_name: str, package_name: str):
        """[DSLC-7] Generate error handling semantics fix"""
        
        error_code = issue.issue_id.split('-')[-1] if '-' in issue.issue_id else "unknown"
        
        template = f'''
    /**
     * [DSLC-7] Error handling from PL/SQL
     * Application error code: {error_code}
     * Message: {issue.expected_behavior}
     */
    
    // Custom exception with code
    class ApplicationException extends RuntimeException {{
        private final int errorCode;
        
        public ApplicationException(int errorCode, String message) {{
            super(message);
            this.errorCode = errorCode;
        }}
        
        public int getErrorCode() {{
            return errorCode;
        }}
    }}
    
    // Usage in service
    public void performBusinessOperation(Long id) {{
        try {{
            // Validate preconditions
            if (!isValid(id)) {{
                throw new ApplicationException(
                    {error_code},
                    "{issue.expected_behavior}"
                );
            }}
            
            // Perform operation
            executeLogic(id);
            
        }} catch (ApplicationException ex) {{
            // [DSLC-7] Handle application errors with proper semantics
            logger.error("[DSLC-7] Business rule violation: code={{}}, msg={{}}", 
                ex.getErrorCode(), ex.getMessage());
            
            // For autonomous transaction equivalent (logging)
            auditErrorLog(id, ex.getErrorCode(), ex.getMessage());
            
            // Re-throw or wrap
            throw ex;
        }}
    }}
    
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    private void auditErrorLog(Long id, int errorCode, String message) {{
        // [DSLC-7] Autonomous transaction equivalent for logging
        // This executes independently even if parent transaction rolls back
        logger.info("[DSLC-7-AUTONOMOUS] Logging error: code={{}}, entity={{}}", 
            errorCode, id);
    }}
'''
        
        fix = CodeFix(
            fix_id=issue.issue_id,
            category="EDL-7",
            target_class=service_name,
            location="class",
            code_template=template,
            explanation="Implement error handling with application error codes and autonomous logging semantics",
            required_imports=[
                "org.springframework.transaction.annotation.Transactional",
                "org.springframework.transaction.annotation.Propagation",
                "lombok.extern.slf4j.Slf4j",
            ]
        )
        self.fixes.append(fix)

    def _to_camel_case(self, s: str) -> str:
        """Convert snake_case to camelCase"""
        parts = s.lower().split('_')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:])

    def _to_pascal_case(self, s: str) -> str:
        """Convert snake_case to PascalCase"""
        parts = s.lower().split('_')
        return ''.join(p.capitalize() for p in parts)

    def _to_snake_case(self, s: str) -> str:
        """Convert PascalCase to snake_case"""
        result = []
        for i, char in enumerate(s):
            if char.isupper() and i > 0:
                result.append('_')
            result.append(char.lower())
        return ''.join(result)

    def _group_by_category(self) -> Dict[str, int]:
        """Group fixes by category"""
        groups = {}
        for fix in self.fixes:
            if fix.category not in groups:
                groups[fix.category] = 0
            groups[fix.category] += 1
        return groups


def create_correction_report(corrections: Dict[str, Any]) -> str:
    """Create human-readable correction report"""
    
    lines = [
        "=" * 100,
        "DOMAIN-SPECIFIC LOGIC CORRECTION TEMPLATES",
        "=" * 100,
        f"Total corrections generated: {corrections['total_fixes']}",
        "",
    ]
    
    for category, count in corrections.get('fixes_by_category', {}).items():
        lines.append(f"{category}: {count} fix templates")
    lines.append("")
    
    for fix in corrections.get('fixes', []):
        lines.append(f"[{fix.category}] {fix.fix_id}")
        lines.append(f"Target: {fix.target_class}")
        lines.append(f"Explanation: {fix.explanation}")
        lines.append("")
        lines.append("Template:")
        lines.append("-" * 100)
        lines.append(fix.code_template)
        lines.append("-" * 100)
        lines.append("")
    
    return "\n".join(lines)
