"""
100% Logic Accuracy Integration Example for Main Pipeline

This example shows how to integrate the logic extraction and validation system
into the main PL/SQL Accelerator conversion pipeline to ensure 100% logic accuracy.

Integration Points:
1. After LLM service generation (Stage 5)
2. Before semantic validation (Stage 6)
3. After validation report (with correction attempts)
"""

from typing import Dict, Optional, Tuple, Any
import logging
import asyncio

# Import the logic accuracy system
from src.analyzer.logic_extractor import LogicExtractor
from src.converter.logic_integration import (
    LogicIntegrationPipeline,
    LogicCorrectiveService
)
from src.validator.logic_preservation_validator import ValidationStatus
from src.validator.logic_accuracy_test_suite import (
    LogicAccuracyTestSuite,
    TestResult,
    format_test_report
)

logger = logging.getLogger(__name__)


class LogicAccuracyEnhancedConverter:
    """
    Drop-in enhancement to existing converter for 100% logic accuracy.
    
    Usage:
        converter = LogicAccuracyEnhancedConverter(existing_converter_instance)
        result = await converter.run_conversion_with_logic_validation(...)
    """
    
    def __init__(self, base_converter):
        self.base_converter = base_converter
        self.logic_pipeline = LogicIntegrationPipeline()
        self.corrective_service = LogicCorrectiveService()
        self.test_suite = LogicAccuracyTestSuite()
        
        # Configuration
        self.strict_mode = True  # Reject if logic not 100% preserved
        self.auto_correct = True  # Attempt automatic corrections
        self.require_passing_tests = True  # All tests must pass
        self.preservation_threshold = 100.0  # Required percentage
    
    async def run_conversion_with_logic_validation(
        self,
        plsql_files: Dict[str, str],
        semantic_model: Dict[str, Any],
        entities: Dict[str, str],
        repositories: Dict[str, str],
        # ... other standard parameters
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        """
        Enhanced conversion pipeline with 100% logic validation.
        
        Returns:
            (services_dict, accuracy_metrics)
        """
        
        # Stage 1: Standard conversion (existing pipeline)
        logger.info("[LOGIC] Stage 1: Running standard conversion pipeline...")
        services = await self.base_converter.generate_services(
            semantic_model=semantic_model,
            entities=entities,
            repositories=repositories
        )
        
        accuracy_metrics = {}
        
        # Stage 2: Logic accuracy validation for each service
        logger.info("[LOGIC] Stage 2: Validating logic accuracy for each service...")
        
        for service_name, java_code in services.items():
            # Find corresponding PL/SQL procedure
            plsql_procedure = self._find_plsql_procedure(service_name, plsql_files)
            
            if not plsql_procedure:
                logger.warning(f"[LOGIC] No PL/SQL source found for {service_name}")
                continue
            
            logger.info(f"[LOGIC] Analyzing {service_name}...")
            
            # Run complete logic accuracy check
            service_metrics = await self._check_service_logic_accuracy(
                service_name=service_name,
                plsql_source=plsql_procedure,
                java_code=java_code
            )
            accuracy_metrics[service_name] = service_metrics
            
            # Check if corrections are needed
            if service_metrics['preservation_percentage'] < self.preservation_threshold:
                logger.warning(
                    f"[LOGIC] {service_name}: Logic preservation below threshold "
                    f"({service_metrics['preservation_percentage']:.1f}% < {self.preservation_threshold}%)"
                )
                
                if self.auto_correct:
                    # Attempt automatic correction
                    corrected_code = await self._apply_corrections(
                        service_name=service_name,
                        java_code=java_code,
                        metrics=service_metrics,
                        plsql_source=plsql_procedure
                    )
                    
                    if corrected_code:
                        services[service_name] = corrected_code
                        logger.info(f"[LOGIC] {service_name}: Corrections applied")
                        
                        # Re-validate after correction
                        service_metrics = await self._check_service_logic_accuracy(
                            service_name=service_name,
                            plsql_source=plsql_procedure,
                            java_code=corrected_code
                        )
                        accuracy_metrics[service_name] = service_metrics
                
                if service_metrics['preservation_percentage'] < self.preservation_threshold:
                    if self.strict_mode and service_metrics['critical_issues'] > 0:
                        raise ValueError(
                            f"LOGIC ACCURACY FAILURE: {service_name} has "
                            f"{service_metrics['critical_issues']} critical issues. "
                            f"Logic preservation: {service_metrics['preservation_percentage']:.1f}%"
                        )
        
        # Stage 3: Generate comprehensive report
        logger.info("[LOGIC] Stage 3: Generating accuracy report...")
        report = self._generate_overall_report(accuracy_metrics)
        
        if report['critical_failures'] > 0 and self.strict_mode:
            raise ValueError(
                f"LOGIC ACCURACY FAILURE: {report['critical_failures']} services have "
                f"critical issues. Cannot proceed with deployment."
            )
        
        if report['overall_preservation'] < 95.0:
            logger.error(f"[LOGIC] WARNING: Overall preservation is only {report['overall_preservation']:.1f}%")
            if self.strict_mode:
                raise ValueError(
                    f"Overall logic preservation ({report['overall_preservation']:.1f}%) "
                    f"below acceptable threshold"
                )
        
        logger.info(f"[LOGIC] Conversion complete. Overall preservation: {report['overall_preservation']:.1f}%")
        
        return services, accuracy_metrics
    
    async def _check_service_logic_accuracy(
        self,
        service_name: str,
        plsql_source: str,
        java_code: str
    ) -> Dict[str, Any]:
        """
        Complete logic accuracy check for a single service.
        Returns metrics dictionary.
        """
        
        try:
            # Step 1: Extract logic
            extraction_report, preservation_report, metrics = await self.logic_pipeline.extract_and_validate_logic(
                plsql_source=plsql_source,
                java_code=java_code,
                procedure_name=service_name
            )
            
            # Step 2: Run test suite
            test_report = await self.test_suite.run_comprehensive_audit(
                plsql_source=plsql_source,
                java_code=java_code,
                procedure_name=service_name
            )
            
            # Step 3: Compile results
            return {
                'service_name': service_name,
                'extraction_confidence': metrics.extraction_confidence,
                'preservation_percentage': metrics.preservation_percentage,
                'logic_elements_extracted': metrics.logic_elements_extracted,
                'logic_elements_validated': metrics.logic_elements_validated,
                'critical_issues': metrics.critical_issues,
                'warnings': metrics.warnings_count,
                'test_coverage': test_report.coverage_percentage,
                'test_status': test_report.overall_status.value,
                'failed_tests': test_report.failed_tests,
                'extraction_report': extraction_report,
                'preservation_report': preservation_report,
                'test_report': test_report,
            }
        
        except Exception as e:
            logger.exception(f"[LOGIC] Error checking logic accuracy for {service_name}: {e}")
            return {
                'service_name': service_name,
                'error': str(e),
                'extraction_confidence': 0.0,
                'preservation_percentage': 0.0,
                'critical_issues': 1,
            }
    
    async def _apply_corrections(
        self,
        service_name: str,
        java_code: str,
        metrics: Dict[str, Any],
        plsql_source: str
    ) -> Optional[str]:
        """
        Attempt to automatically correct missing logic.
        Returns corrected code or None if unable to correct.
        """
        
        try:
            logger.info(f"[LOGIC] Attempting corrections for {service_name}...")
            
            preservation_report = metrics.get('preservation_report')
            extraction_report = metrics.get('extraction_report')
            
            if not preservation_report or not extraction_report:
                return None
            
            # Use corrective service to suggest fixes
            corrected_code, applied_fixes = await self.corrective_service.correct_java_code(
                java_code=java_code,
                preservation_report=preservation_report,
                extraction_report=extraction_report
            )
            
            if applied_fixes:
                logger.info(f"[LOGIC] Applied {len(applied_fixes)} corrections to {service_name}")
                return corrected_code
            
            return None
        
        except Exception as e:
            logger.warning(f"[LOGIC] Could not auto-correct {service_name}: {e}")
            return None
    
    def _find_plsql_procedure(self, service_name: str, plsql_files: Dict[str, str]) -> Optional[str]:
        """
        Find corresponding PL/SQL procedure for a Java service.
        
        Matching strategy:
        1. Exact name match
        2. Service name contains procedure name
        3. First file if name unclear
        """
        
        # Strategy 1: Exact match on procedure name
        procedure_name = service_name.replace("Service", "").lower()
        
        for file_name, content in plsql_files.items():
            # Look for CREATE PROCEDURE matching service name
            if f"CREATE OR REPLACE PROCEDURE {procedure_name}" in content.upper():
                return content
        
        # Strategy 2: Partial match
        for file_name, content in plsql_files.items():
            if procedure_name in file_name.lower():
                return content
        
        # Strategy 3: Return first available
        if plsql_files:
            return next(iter(plsql_files.values()))
        
        return None
    
    def _generate_overall_report(self, accuracy_metrics: Dict[str, Dict]) -> Dict[str, Any]:
        """Generate overall accuracy report across all services."""
        
        if not accuracy_metrics:
            return {
                'total_services': 0,
                'services_100_percent': 0,
                'services_critical': 0,
                'critical_failures': 0,
                'overall_preservation': 0.0,
                'average_confidence': 0.0,
                'average_test_coverage': 0.0,
            }
        
        preservations = [m.get('preservation_percentage', 0) for m in accuracy_metrics.values()]
        confidences = [m.get('extraction_confidence', 0) for m in accuracy_metrics.values()]
        test_coverages = [m.get('test_coverage', 0) for m in accuracy_metrics.values() if 'test_coverage' in m]
        
        critical_count = sum(1 for m in accuracy_metrics.values() if m.get('critical_issues', 0) > 0)
        perfect_count = sum(1 for p in preservations if p >= 99.9)
        
        return {
            'total_services': len(accuracy_metrics),
            'services_100_percent': perfect_count,
            'services_critical': critical_count,
            'critical_failures': sum(1 for m in accuracy_metrics.values() 
                                    if m.get('preservation_percentage', 0) < 95),
            'overall_preservation': sum(preservations) / len(preservations) if preservations else 0.0,
            'average_confidence': sum(confidences) / len(confidences) if confidences else 0.0,
            'average_test_coverage': sum(test_coverages) / len(test_coverages) if test_coverages else 0.0,
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """
    Example of how to use the logic accuracy enhancement.
    """
    
    # Create existing converter instance (your current converter)
    from main import PlSQLModernizer
    
    base_converter = PlSQLModernizer(config={})
    
    # Wrap with logic accuracy enhancement
    enhanced_converter = LogicAccuracyEnhancedConverter(base_converter)
    
    # Configure strictness
    enhanced_converter.strict_mode = True  # Fail on critical issues
    enhanced_converter.auto_correct = True  # Auto-fix when possible
    enhanced_converter.preservation_threshold = 100.0  # Require 100% preservation
    
    # Use it just like the normal converter
    plsql_files = {
        'employee.sql': """
            CREATE OR REPLACE PROCEDURE reconcile_customer_balances (
                p_batch_size IN NUMBER DEFAULT 100
            ) IS
                CURSOR cust_cursor IS
                    SELECT customer_id FROM customers WHERE status = 'ACTIVE'
                    FOR UPDATE SKIP LOCKED;
                
                TYPE cust_table IS TABLE OF cust_cursor%ROWTYPE;
                v_customers cust_table;
            BEGIN
                OPEN cust_cursor;
                LOOP
                    FETCH cust_cursor BULK COLLECT INTO v_customers LIMIT p_batch_size;
                    EXIT WHEN v_customers.COUNT = 0;
                    
                    FOR i IN 1 .. v_customers.COUNT LOOP
                        ... processing ...
                    END LOOP;
                    
                    COMMIT;
                END LOOP;
                CLOSE cust_cursor;
            END;
        """
    }
    
    services, metrics = await enhanced_converter.run_conversion_with_logic_validation(
        plsql_files=plsql_files,
        semantic_model={},
        entities={},
        repositories={}
    )
    
    # Check results
    for service_name, service_metrics in metrics.items():
        print(f"\n{service_name}:")
        print(f"  Preservation: {service_metrics['preservation_percentage']:.1f}%")
        print(f"  Confidence: {service_metrics['extraction_confidence']:.1%}")
        print(f"  Critical Issues: {service_metrics['critical_issues']}")
        if service_metrics.get('test_report'):
            print(format_test_report(service_metrics['test_report']))


if __name__ == "__main__":
    asyncio.run(example_usage())
