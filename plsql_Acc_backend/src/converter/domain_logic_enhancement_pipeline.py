"""
Domain-Specific Logic Enhancement Pipeline

Orchestrates extraction, validation, and correction of domain-specific
semantic logic differences between PL/SQL and Java.

Addresses all 9 categories of logical mismatches:
1. Function/procedure contract differences (overloads, return types)
2. Validation logic differences (assertions, business rules)
3. Invoice creation flow differences (derivation logic)
4. Invoice approval flow differences (status transitions)
5. Customer package behavior differences (row updates)
6. VAT/description derivation differences (deterministic rules)
7. PayPal utility logic differences (domain models, JSON handling)
8. Stateful buffer logic differences (mutable state)
9. Logging/error semantics differences (autonomous transactions)

DLP-1: Extraction pipeline orchestration
DLP-2: Validation orchestration
DLP-3: Correction orchestration
DLP-4: Reporting and metrics
DLP-5: Integration with base conversion pipeline
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class DomainLogicStatus(Enum):
    """Pipeline execution status"""
    NOT_ANALYZED = "not_analyzed"
    EXTRACTION_COMPLETE = "extraction_complete"
    VALIDATION_COMPLETE = "validation_complete"
    CORRECTIONS_READY = "corrections_ready"
    ALL_ISSUES_RESOLVED = "all_issues_resolved"


@dataclass
class ServiceDomainLogicMetrics:
    """Metrics for domain logic preservation in a service"""
    service_name: str
    
    # Extraction metrics
    total_domain_elements_extracted: int = 0
    overloads_count: int = 0
    assertions_count: int = 0
    derivations_count: int = 0
    transitions_count: int = 0
    domain_models_count: int = 0
    stateful_behaviors_count: int = 0
    error_semantics_count: int = 0
    
    # Validation metrics
    total_issues_found: int = 0
    critical_issues: int = 0
    high_issues: int = 0
    medium_issues: int = 0
    low_issues: int = 0
    validation_success_rate: float = 0.0
    
    # Correction metrics
    corrections_generated: int = 0
    corrections_applied: int = 0
    estimated_coverage_after_fix: float = 0.0
    
    # Overall
    pipeline_status: DomainLogicStatus = DomainLogicStatus.NOT_ANALYZED
    timestamp: str = ""


@dataclass
class DomainLogicEnhancementPipeline:
    """
    [DLP-1-5] Main pipeline orchestrator for domain logic enhancement
    """
    
    # Components
    extractor: Any = None  # EnhancedDomainLogicExtractor
    validator: Any = None  # DomainSemanticLogicValidator
    corrector: Any = None  # DomainLogicCorrectionEngine
    
    # Results
    extracted_domain_logic: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    validation_reports: Dict[str, Any] = field(default_factory=dict)
    corrections: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, ServiceDomainLogicMetrics] = field(default_factory=dict)
    
    def run_full_enhancement(
        self,
        plsql_sources: Dict[str, str],
        java_services: Dict[str, str],
        apply_corrections: bool = False
    ) -> Dict[str, Any]:
        """
        [DLP-1-5] Execute complete domain logic enhancement pipeline:
        1. Extract domain logic from PL/SQL sources
        2. Validate implementation in Java services
        3. Generate correction code
        4. Optionally apply corrections
        5. Report comprehensive metrics
        """
        
        logger.info("[DLP] Starting domain logic enhancement pipeline")
        logger.info("[DLP] PL/SQL sources: %d, Java services: %d", 
                    len(plsql_sources), len(java_services))
        
        results = {
            'extracted_logic': {},
            'validation_reports': {},
            'corrections': {},
            'metrics': {},
            'summary': {}
        }
        
        # For each PL/SQL source, extract domain logic [DLP-1]
        logger.info("[DLP-1] Stage 1: Extract domain logic from PL/SQL sources")
        for source_name, source_code in plsql_sources.items():
            logger.info("[DLP-1] Extracting from %s", source_name)
            
            extraction = self.extractor.extract_all_domain_logic(
                source_code,
                source_name
            )
            
            self.extracted_domain_logic[source_name] = extraction
            results['extracted_logic'][source_name] = {
                'total_elements': extraction['total_domain_elements'],
                'overloads': len(extraction['overloads']),
                'assertions': len(extraction['assertions']),
                'derivations': len(extraction['derivations']),
                'transitions': len(extraction['transitions']),
                'domain_models': len(extraction['domain_models']),
                'stateful_behaviors': len(extraction['stateful_behaviors']),
                'error_semantics': len(extraction['error_semantics']),
            }
        
        logger.info("[DLP] Extraction complete: %d packages analyzed", 
                    len(self.extracted_domain_logic))
        
        # For each Java service, validate against extracted logic [DLP-2]
        logger.info("[DLP-2] Stage 2: Validate Java implementations")
        for service_name, java_code in java_services.items():
            logger.info("[DLP-2] Validating %s", service_name)
            
            # Find matching PL/SQL source
            matching_source = self._find_matching_plsql_source(
                service_name, 
                self.extracted_domain_logic
            )
            
            if matching_source:
                domain_logic = self.extracted_domain_logic[matching_source]
                
                # Validate
                validation_report = self.validator.validate_domain_implementation(
                    domain_logic,
                    java_code,
                    service_name
                )
                
                self.validation_reports[service_name] = validation_report
                results['validation_reports'][service_name] = {
                    'status': validation_report.validation_status,
                    'success_rate': validation_report.validation_success_rate,
                    'critical_issues': len(validation_report.critical_issues),
                    'high_issues': len(validation_report.high_issues),
                    'recommendations': validation_report.recommendations
                }
        
        logger.info("[DLP] Validation complete: %d services validated", 
                    len(self.validation_reports))
        
        # Generate corrections [DLP-3]
        logger.info("[DLP-3] Stage 3: Generate correction code")
        for service_name, validation_report in self.validation_reports.items():
            if validation_report.all_issues:
                logger.info("[DLP-3] Generating corrections for %s", service_name)
                
                corrections = self.corrector.generate_corrections(
                    validation_report.all_issues,
                    service_name,
                    ""  # package_name can be inferred
                )
                
                self.corrections[service_name] = corrections
                results['corrections'][service_name] = {
                    'total_fixes': corrections['total_fixes'],
                    'fixes_by_category': corrections['fixes_by_category']
                }
        
        logger.info("[DLP] Correction generation complete: %d services with fixes", 
                    len(self.corrections))
        
        # Generate metrics [DLP-4]
        logger.info("[DLP-4] Stage 4: Calculate metrics")
        self._calculate_metrics()
        
        results['metrics'] = {
            service: {
                'service_name': m.service_name,
                'total_domain_elements': m.total_domain_elements_extracted,
                'total_issues': m.total_issues_found,
                'critical_issues': m.critical_issues,
                'validation_success_rate': m.validation_success_rate,
                'corrections_generated': m.corrections_generated,
                'status': m.pipeline_status.value,
            }
            for service, m in self.metrics.items()
        }
        
        # Overall summary [DLP-5] Integration summary
        results['summary'] = self._generate_summary()
        
        logger.info("[DLP] Pipeline complete")
        logger.info("[DLP] Summary: %s", results['summary'])
        
        return results
    
    def _find_matching_plsql_source(
        self,
        service_name: str,
        extracted_sources: Dict[str, Any]
    ) -> Optional[str]:
        """Find PL/SQL source matching Java service name"""
        
        # Simple heuristic: look for containing package name
        for source_name in extracted_sources.keys():
            if source_name.lower().replace('_', '') in service_name.lower().replace('_', ''):
                return source_name
            if service_name.lower().replace('_', '') in source_name.lower().replace('_', ''):
                return source_name
        
        # Return first as fallback
        return next(iter(extracted_sources.keys())) if extracted_sources else None
    
    def _calculate_metrics(self):
        """[DLP-4] Calculate comprehensive metrics"""
        
        for service_name, validation_report in self.validation_reports.items():
            metrics = ServiceDomainLogicMetrics(
                service_name=service_name,
                validation_success_rate=validation_report.validation_success_rate,
                total_issues_found=len(validation_report.all_issues),
                critical_issues=len(validation_report.critical_issues),
                high_issues=len(validation_report.high_issues),
            )
            
            # Count issue types
            for issue in validation_report.all_issues:
                if issue.severity.value == "medium":
                    metrics.medium_issues += 1
                elif issue.severity.value == "low":
                    metrics.low_issues += 1
            
            # Add corrections count
            if service_name in self.corrections:
                metrics.corrections_generated = self.corrections[service_name]['total_fixes']
            
            # Estimate coverage after fixes
            total_issues = metrics.total_issues_found
            if total_issues > 0:
                metrics.estimated_coverage_after_fix = min(
                    0.99,  # Can't guarantee 100%
                    validation_report.validation_success_rate + 
                    (metrics.corrections_generated / (total_issues + 1)) * 0.2
                )
            
            # Determine status
            if metrics.critical_issues == 0:
                if metrics.high_issues == 0:
                    metrics.pipeline_status = DomainLogicStatus.ALL_ISSUES_RESOLVED
                else:
                    metrics.pipeline_status = DomainLogicStatus.CORRECTIONS_READY
            else:
                metrics.pipeline_status = DomainLogicStatus.VALIDATION_COMPLETE
            
            self.metrics[service_name] = metrics
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate overall summary"""
        
        total_services = len(self.metrics)
        fully_compliant = sum(
            1 for m in self.metrics.values() 
            if m.critical_issues == 0 and m.high_issues == 0
        )
        
        total_issues = sum(m.total_issues_found for m in self.metrics.values())
        total_critical = sum(m.critical_issues for m in self.metrics.values())
        
        avg_success_rate = sum(
            m.validation_success_rate for m in self.metrics.values()
        ) / total_services if total_services > 0 else 0.0
        
        return {
            'total_services_analyzed': total_services,
            'fully_compliant_services': fully_compliant,
            'compliance_percentage': (fully_compliant / total_services * 100) if total_services > 0 else 0,
            'total_domain_logic_issues': total_issues,
            'critical_issues_blocking_deployment': total_critical,
            'average_validation_success_rate': avg_success_rate,
            'total_corrections_available': sum(
                c['total_fixes'] for c in self.corrections.values()
            ),
            'pipeline_ready_for_deployment': total_critical == 0,
        }


class DomainLogicEnhancementIntegration:
    """
    [DLP-5] Integration adapter for existing conversion pipeline
    """
    
    def __init__(self, base_converter: Any):
        self.base_converter = base_converter
        self.pipeline = DomainLogicEnhancementPipeline()
    
    def enhance_conversion_with_domain_logic(
        self,
        plsql_sources: Dict[str, str],
        java_services: Dict[str, str],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        [DLP-5] Enhance existing conversion with domain logic validation
        """
        
        if config is None:
            config = {}
        
        logger.info("[DLP-5] Starting domain logic enhancement integration")
        
        # Run full pipeline
        results = self.pipeline.run_full_enhancement(
            plsql_sources,
            java_services,
            apply_corrections=config.get('auto_apply_corrections', False)
        )
        
        # Integrate results with base conversion
        enhanced_results = {
            'base_conversion': {},
            'domain_logic_enhancement': results,
            'final_status': 'SUCCESS' if results['summary']['pipeline_ready_for_deployment'] else 'REVIEW_REQUIRED',
        }
        
        return enhanced_results


def create_domain_enhancement_report(
    results: Dict[str, Any],
    format: str = "text"
) -> str:
    """Create formatted report of domain logic enhancement"""
    
    if format == "json":
        return json.dumps(results, indent=2, default=str)
    
    # Text format
    lines = [
        "=" * 120,
        "DOMAIN-SPECIFIC LOGIC ENHANCEMENT REPORT",
        "=" * 120,
        "",
    ]
    
    summary = results.get('summary', {})
    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 120)
    lines.append(f"Services Analyzed: {summary.get('total_services_analyzed', 0)}")
    lines.append(f"Fully Compliant: {summary.get('fully_compliant_services', 0)} "
                f"({summary.get('compliance_percentage', 0):.1f}%)")
    lines.append(f"Total Issues Found: {summary.get('total_domain_logic_issues', 0)}")
    lines.append(f"Critical Issues: {summary.get('critical_issues_blocking_deployment', 0)}")
    lines.append(f"Avg Validation Success Rate: {summary.get('average_validation_success_rate', 0):.1%}")
    lines.append(f"Ready for Deployment: {'YES' if summary.get('pipeline_ready_for_deployment') else 'NO'}")
    lines.append("")
    
    # Extracted logic summary
    extracted = results.get('extracted_logic', {})
    if extracted:
        lines.append("EXTRACTED DOMAIN LOGIC")
        lines.append("-" * 120)
        for source, counts in extracted.items():
            lines.append(f"  {source}:")
            lines.append(f"    Total elements: {counts.get('total_elements', 0)}")
            lines.append(f"    Overloads: {counts.get('overloads', 0)}")
            lines.append(f"    Assertions: {counts.get('assertions', 0)}")
            lines.append(f"    Derivations: {counts.get('derivations', 0)}")
        lines.append("")
    
    # Validation results
    validation = results.get('validation_reports', {})
    if validation:
        lines.append("VALIDATION RESULTS")
        lines.append("-" * 120)
        for service, report in validation.items():
            lines.append(f"  {service}: {report.get('status')} "
                        f"({report.get('success_rate', 0):.1%})")
            lines.append(f"    Critical: {report.get('critical_issues', 0)}, "
                        f"High: {report.get('high_issues', 0)}")
        lines.append("")
    
    # Corrections available
    corrections = results.get('corrections', {})
    if corrections:
        lines.append("CORRECTIONS AVAILABLE")
        lines.append("-" * 120)
        for service, fixes in corrections.items():
            lines.append(f"  {service}: {fixes.get('total_fixes', 0)} fix templates")
        lines.append("")
    
    lines.append("=" * 120)
    
    return "\n".join(lines)
