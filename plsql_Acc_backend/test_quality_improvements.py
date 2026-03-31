#!/usr/bin/env python3
"""
Quick test of new quality improvement modules
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_table_metadata_provider():
    """Test table metadata provider"""
    from src.parser.table_metadata_provider import TableMetadataProvider, ColumnMetadata
    
    logger.info("Testing TableMetadataProvider...")
    
    provider = TableMetadataProvider()
    
    # Register a test table
    columns = {
        "ISBN": "VARCHAR2(50)",
        "BOOKID": "VARCHAR2(50)",
        "TITLE": "VARCHAR2(200)",
        "PRICE": "NUMBER(10,2)",
        "STATE": "VARCHAR2(10)",
    }
    
    provider.register_table("BOOK", "BookEntity", columns)
    
    # Test retrieval
    metadata = provider.get_table_metadata("BookEntity")
    assert metadata is not None, "Could not retrieve metadata"
    assert len(metadata.columns) == 5, f"Expected 5 columns, got {len(metadata.columns)}"
    
    # Test field formatting
    entity_fields = provider.get_entity_fields_for_service_prompt("BookEntity")
    assert "bookid" in entity_fields.lower(), "Missing bookid field"
    assert "price" in entity_fields.lower(), "Missing price field"
    
    logger.info("✓ TableMetadataProvider works correctly")
    return True


def test_llm_prompt_enhancements():
    """Test LLM prompt enhancement utilities"""
    from src.converter.llm_prompt_enhancements import (
        RepositoryEnchancements, 
        ServiceMethodEnhancement,
        enhance_service_prompt_with_metadata
    )
    
    logger.info("Testing LLM Prompt Enhancements...")
    
    # Test getting examples
    examples = RepositoryEnchancements.get_spring_data_examples()
    assert "findById" in examples, "Missing findById examples"
    assert "CORRECT" in examples, "Missing CORRECT marker in examples"
    
    # Test entity rules
    entity_rules = RepositoryEnchancements.get_entity_usage_rules("TestEntity: field1 (String)")
    assert "field1" in entity_rules, "Entity fields not in rules"
    
    # Test error handling
    error_patterns = ServiceMethodEnhancement.get_error_handling_pattern()
    assert "orElseThrow" in error_patterns, "Missing orElseThrow pattern"
    
    logger.info("✓ LLM Prompt Enhancements work correctly")
    return True


def test_build_validator():
    """Test build validator"""
    from src.generator.build_validator import BuildValidator
    
    logger.info("Testing BuildValidator...")
    
    validator = BuildValidator()
    
    # Check tool detection
    logger.info(f"  Maven available: {validator.has_maven}")
    logger.info(f"  Gradle available: {validator.has_gradle}")
    
    # At least one tool should be detected (though not guaranteed on all systems)
    if not (validator.has_maven or validator.has_gradle):
        logger.warning("  (No build tools found - this is OK for this test)")
    
    logger.info("✓ BuildValidator initialized successfully")
    return True


def main():
    """Run all tests"""
    try:
        tests = [
            ("TableMetadataProvider", test_table_metadata_provider),
            ("LLM Prompt Enhancements", test_llm_prompt_enhancements),
            ("BuildValidator", test_build_validator),
        ]
        
        results = []
        for name, test_func in tests:
            try:
                result = test_func()
                results.append((name, result, None))
            except Exception as e:
                logger.error(f"Test '{name}' failed: {e}", exc_info=True)
                results.append((name, False, str(e)))
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("TEST RESULTS")
        logger.info("="*60)
        
        passed = sum(1 for _, result, _ in results if result)
        total = len(results)
        
        for name, result, error in results:
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"{status}: {name}")
            if error:
                logger.info(f"       {error}")
        
        logger.info("="*60)
        logger.info(f"Results: {passed}/{total} tests passed")
        
        return 0 if passed == total else 1
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
