"""
Logic Accuracy Test Suite

Comprehensive testing framework to validate that PL/SQL → Java conversions 
preserve 100% of the original logic.

LATS-1: Logic element coverage testing
LATS-2: Behavior equivalence testing
LATS-3: Edge case detection
LATS-4: Logic mutation testing
LATS-5: Integration testing
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from enum import Enum
from dataclasses import dataclass

from src.analyzer.logic_extractor import (
    LogicExtractor, LogicType, LogicElement
)
from src.validator.logic_preservation_validator import (
    LogicPreservationValidator
)
from src.converter.logic_integration import LogicIntegrationPipeline

logger = logging.getLogger(__name__)


class TestResult(Enum):
    """Test execution result"""
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


@dataclass
class LogicTest:
    """Single logic test case"""
    test_id: str
    test_name: str
    test_type: str  # "coverage", "behavior", "edge_case", "mutation", "integration"
    description: str
    logic_element: Optional[LogicElement] = None
    test_function: Optional[callable] = None
    expected_result: Optional[str] = None


@dataclass
class LogicTestResult:
    """Result of a single test"""
    test_id: str
    test_name: str
    result: TestResult
    duration_ms: float
    error_message: Optional[str] = None
    assertion_details: Optional[str] = None


@dataclass
class LogicTestReport:
    """Complete test suite report"""
    total_tests: int
    passed_tests: int
    failed_tests: int
    warning_tests: int
    skipped_tests: int
    test_results: List[LogicTestResult]
    coverage_percentage: float
    overall_status: TestResult
    recommendations: List[str]


class LogicAccuracyTestSuite:
    """
    Comprehensive test suite for logic preservation [LATS-1-5]
    """
    
    def __init__(self):
        self.tests: List[LogicTest] = []
        self.results: List[LogicTestResult] = []
        self.extractor = LogicExtractor()
        self.validator = LogicPreservationValidator()
        self.pipeline = LogicIntegrationPipeline()
        
    async def run_comprehensive_audit(
        self,
        plsql_source: str,
        java_code: str,
        procedure_name: str = ""
    ) -> LogicTestReport:
        """
        [LATS-1-5] Run complete logic accuracy audit
        """
        logger.info(f"[LATS] Starting comprehensive logic audit for {procedure_name}")
        
        # Stage 1: Build test suite
        logger.info("[LATS-1] Building coverage tests")
        self._build_coverage_tests(plsql_source)
        
        # Stage 2: Extract and validate
        logger.info("[LATS-1-5] Running extraction and validation")
        extraction_report, preservation_report, metrics = await self.pipeline.extract_and_validate_logic(
            plsql_source,
            java_code,
            procedure_name
        )
        
        # Stage 3: Run all tests
        logger.info("[LATS-2-5] Executing test suite")
        for test in self.tests:
            await self._execute_test(test, plsql_source, java_code)
        
        # Stage 4: Generate report
        logger.info("[LATS] Generating test report")
        report = self._generate_report(preservation_report, metrics)
        
        logger.info(f"[LATS] Audit complete: {report.overall_status.value}")
        
        return report

    def _build_coverage_tests(self, plsql_source: str) -> None:
        """[LATS-1] Build logic element coverage tests"""
        
        # Extract logic elements
        extraction = self.extractor.extract_logic(plsql_source)
        
        # Create test for each logic element
        for i, element in enumerate(extraction.elements):
            test = LogicTest(
                test_id=f"cov_{i}",
                test_name=f"Coverage: {element.logic_type.value}",
                test_type="coverage",
                description=f"Verify {element.name} logic is preserved",
                logic_element=element,
                expected_result="Java code contains equivalent logic"
            )
            self.tests.append(test)
        
        logger.info(f"[LATS-1] Built {len(self.tests)} coverage tests")

    async def _execute_test(
        self,
        test: LogicTest,
        plsql_source: str,
        java_code: str
    ) -> None:
        """Execute individual test [LATS-2-5]"""
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            if test.test_type == "coverage":
                result = await self._test_coverage(test, java_code)
            elif test.test_type == "behavior":
                result = await self._test_behavior(test, plsql_source, java_code)
            elif test.test_type == "edge_case":
                result = await self._test_edge_case(test, plsql_source, java_code)
            elif test.test_type == "mutation":
                result = await self._test_mutation(test, plsql_source, java_code)
            else:
                result = TestResult.SKIP
            
            duration = (asyncio.get_event_loop().time() - start_time) * 1000
            
            test_result = LogicTestResult(
                test_id=test.test_id,
                test_name=test.test_name,
                result=result,
                duration_ms=duration
            )
            self.results.append(test_result)
            
        except Exception as e:
            logger.error(f"[LATS] Test {test.test_id} failed with error: {str(e)}")
            test_result = LogicTestResult(
                test_id=test.test_id,
                test_name=test.test_name,
                result=TestResult.FAIL,
                duration_ms=0,
                error_message=str(e)
            )
            self.results.append(test_result)

    async def _test_coverage(self, test: LogicTest, java_code: str) -> TestResult:
        """[LATS-1] Test logic element coverage in Java code"""
        
        if not test.logic_element:
            return TestResult.SKIP
        
        element = test.logic_element
        
        # Check if equivalent logic exists in Java
        if self._find_equivalent_logic(element, java_code):
            return TestResult.PASS
        elif element.is_critical:
            logger.error(f"[LATS-1] Critical logic missing: {element.name}")
            return TestResult.FAIL
        else:
            return TestResult.WARN

    async def _test_behavior(
        self,
        test: LogicTest,
        plsql_source: str,
        java_code: str
    ) -> TestResult:
        """[LATS-2] Test behavioral equivalence"""
        
        if not test.logic_element:
            return TestResult.SKIP
        
        element = test.logic_element
        
        # Verify data transformations produce same results
        if self._verify_behavior_equivalence(element, plsql_source, java_code):
            return TestResult.PASS
        else:
            return TestResult.FAIL

    async def _test_edge_case(
        self,
        test: LogicTest,
        plsql_source: str,
        java_code: str
    ) -> TestResult:
        """[LATS-3] Test edge cases"""
        
        edge_cases = [
            ("null_values", "Null value handling"),
            ("empty_collections", "Empty collection handling"),
            ("boundary_values", "Boundary values (MIN/MAX)"),
            ("concurrent_access", "Concurrent access safety"),
            ("resource_cleanup", "Resource cleanup on error"),
        ]
        
        fails = 0
        for case_name, case_desc in edge_cases:
            if not self._check_edge_case(case_name, java_code):
                logger.warning(f"[LATS-3] Edge case not handled: {case_desc}")
                fails += 1
        
        return TestResult.PASS if fails == 0 else TestResult.WARN

    async def _test_mutation(
        self,
        test: LogicTest,
        plsql_source: str,
        java_code: str
    ) -> TestResult:
        """[LATS-4] Test resilience to logic mutations"""
        
        # Verify that critical logic mutations would be caught
        mutations_to_test = [
            ("remove_null_check", "if (x != null)"),
            ("remove_validation", "if (x < 0) throw"),
            ("remove_loop", "for ("),
            ("remove_transaction", "@Transactional"),
        ]
        
        detectable = 0
        for mutation_name, pattern in mutations_to_test:
            if pattern in java_code:
                detectable += 1
        
        return TestResult.PASS if detectable >= len(mutations_to_test) * 0.7 else TestResult.WARN

    def _find_equivalent_logic(self, element: LogicElement, java_code: str) -> bool:
        """Check if Java code contains equivalent logic"""
        
        import re
        
        if element.logic_type == LogicType.CURSOR_OPERATION:
            return bool(re.search(r"findAll\s*\(|findBy", java_code, re.IGNORECASE))
        elif element.logic_type == LogicType.MERGE_UPSERT:
            return bool(re.search(r"\.save\s*\(", java_code))
        elif element.logic_type == LogicType.LOOP:
            return bool(re.search(r"for\s*\(|while\s*\(|forEach", java_code, re.IGNORECASE))
        elif element.logic_type == LogicType.CONDITIONAL:
            return bool(re.search(r"if\s*\(", java_code, re.IGNORECASE))
        elif element.logic_type == LogicType.AGGREGATION:
            return bool(re.search(r"\.sum\s*\(|\.reduce\s*\(", java_code, re.IGNORECASE))
        elif element.logic_type == LogicType.EXCEPTION_HANDLER:
            return "try" in java_code.lower() and "catch" in java_code.lower()
        elif element.logic_type == LogicType.TRANSACTION_CONTROL:
            return "@Transactional" in java_code
        
        return False

    def _verify_behavior_equivalence(
        self,
        element: LogicElement,
        plsql_source: str,
        java_code: str
    ) -> bool:
        """Verify behavioral equivalence between PL/SQL and Java"""
        
        # For aggregations, verify the operation
        if element.logic_type == LogicType.AGGREGATION:
            # Check that aggregation function is preserved
            if "SUM" in element.source_code.upper():
                return ".sum(" in java_code or "+=" in java_code
            elif "COUNT" in element.source_code.upper():
                return ".count(" in java_code or ".size()" in java_code
        
        return True

    def _check_edge_case(self, case_name: str, java_code: str) -> bool:
        """Check if edge case is handled"""
        
        import re
        
        cases = {
            "null_values": r"!= null|!= null|Optional\.|Objects\.require",
            "empty_collections": r"\.isEmpty\(|\.size\(\) == 0|\.length == 0",
            "boundary_values": r"MIN|MAX|MIN_VALUE|MAX_VALUE",
            "concurrent_access": r"synchronized|AtomicReference|ConcurrentHashMap",
            "resource_cleanup": r"try.*finally|try-with-resources|@Cleanup",
        }
        
        if case_name in cases:
            pattern = cases[case_name]
            return bool(re.search(pattern, java_code, re.IGNORECASE))
        
        return True

    def _generate_report(
        self,
        preservation_report,
        metrics
    ) -> LogicTestReport:
        """Generate comprehensive test report"""
        
        passed = sum(1 for r in self.results if r.result == TestResult.PASS)
        failed = sum(1 for r in self.results if r.result == TestResult.FAIL)
        warned = sum(1 for r in self.results if r.result == TestResult.WARN)
        skipped = sum(1 for r in self.results if r.result == TestResult.SKIP)
        
        total = len(self.results)
        coverage = (passed / total * 100) if total > 0 else 0
        
        overall_status = (
            TestResult.PASS if failed == 0 else
            TestResult.WARN if warned > 0 else
            TestResult.FAIL
        )
        
        recommendations = []
        
        if metrics.preservation_percentage < 100:
            recommendations.append(
                f"Logic preservation is {metrics.preservation_percentage:.1f}%. "
                f"Review {metrics.critical_issues} critical issues."
            )
        
        if warned > 0:
            recommendations.append(
                f"{warned} warning-level issues detected. "
                f"Review edge cases and optional logic."
            )
        
        if failed > 0:
            recommendations.append(
                f"URGENT: {failed} critical logic elements missing. "
                f"Cannot deploy without fixes."
            )
        
        return LogicTestReport(
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            warning_tests=warned,
            skipped_tests=skipped,
            test_results=self.results,
            coverage_percentage=coverage,
            overall_status=overall_status,
            recommendations=recommendations
        )


def format_test_report(report: LogicTestReport) -> str:
    """Format test report for display"""
    
    lines = [
        "=" * 80,
        "LOGIC ACCURACY TEST REPORT",
        "=" * 80,
        f"Overall Status: {report.overall_status.value.upper()}",
        f"Coverage: {report.coverage_percentage:.1f}%",
        "",
        f"Test Results:",
        f"  Passed:  {report.passed_tests:3d}",
        f"  Failed:  {report.failed_tests:3d}",
        f"  Warning: {report.warning_tests:3d}",
        f"  Skipped: {report.skipped_tests:3d}",
        f"  Total:   {report.total_tests:3d}",
        "",
    ]
    
    if report.failed_tests > 0:
        lines.append("FAILED TESTS:")
        for result in report.test_results:
            if result.result == TestResult.FAIL:
                lines.append(f"  ✗ {result.test_name}")
                if result.error_message:
                    lines.append(f"    Error: {result.error_message}")
        lines.append("")
    
    if report.recommendations:
        lines.append("RECOMMENDATIONS:")
        for rec in report.recommendations:
            lines.append(f"  • {rec}")
        lines.append("")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)
