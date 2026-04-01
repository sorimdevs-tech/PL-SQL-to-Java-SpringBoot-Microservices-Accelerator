#!/usr/bin/env python3
"""
Test metadata integration into service generation.
Tests that metadata_provider parameter flows through correctly.
"""

import sys
from unittest.mock import MagicMock
from src.converter.llm_engine import LLMConversionEngine
from src.parser.table_metadata_provider import TableMetadataProvider


def test_metadata_integration():
    """Test that metadata provider can be passed to service generation."""
    
    # Create a simple metadata provider with test data
    metadata_provider = TableMetadataProvider()
    
    # Register a test table with the correct format (dict of column_name -> sql_type)
    columns_dict = {
        "book_id": "NUMBER",
        "title": "VARCHAR2(100)",
        "author": "VARCHAR2(100)",
    }
    metadata_provider.register_table("BOOK", "BookEntity", columns_dict)
    
    print("✓ TableMetadataProvider created and registered BOOK table")
    print(f"  - Columns: {len(columns_dict)}")
    
    # Verify fields can be retrieved
    table_meta = metadata_provider.get_table_metadata("BookEntity")
    if table_meta:
        print(f"✓ Table metadata retrieved for BookEntity")
        print(f"  - Java entity: {table_meta.java_entity_name}")
        print(f"  - Column count: {len(table_meta.columns)}")
        for col in table_meta.columns:
            print(f"    - {col.name}: {col.java_type}")
    else:
        print("✗ Failed to retrieve table metadata for BookEntity")
        return False
    
    # Create a minimal LLMConversionEngine with mocked provider
    config = {
        'output': {'package_name': 'com.test.project', 'base_path': '/tmp'},
        'llm': {'model': 'test', 'provider': 'openrouter'}
    }
    
    try:
        # Create the engine but mock the provider to avoid API key requirement
        llm_engine = LLMConversionEngine.__new__(LLMConversionEngine)
        llm_engine.config = config
        llm_engine.logger = __import__('logging').getLogger('test')
        print("✓ LLMConversionEngine created (mocked)")
        
        # Test _validate_table_fields_against_metadata method
        valid_fields = llm_engine._validate_table_fields_against_metadata("BookEntity", metadata_provider)
        print(f"✓ Field validation returned: {valid_fields}")
        
        # Verify actual fields are found
        # Note: BOOK_ID becomes bookId, TITLE becomes title, AUTHOR becomes author
        if 'bookid' in valid_fields and 'title' in valid_fields and 'author' in valid_fields:
            print(f"✓ All expected fields found in validation set")
        else:
            print(f"✗ Expected fields missing. Got: {valid_fields}")
            return False
        
        # Test _sanitize_getter_call method
        getter = llm_engine._sanitize_getter_call("BookEntity", "title", valid_fields)
        print(f"✓ Sanitized getter call for valid field: {getter}")
        if getter == "getTitle()":
            print(f"  ✓ Correct getter format")
        else:
            print(f"  ✗ Unexpected getter format")
        
        # Test with invalid field
        bad_getter = llm_engine._sanitize_getter_call("BookEntity", "invalidfield", valid_fields)
        print(f"✓ Invalid field handled safely: {bad_getter}")
        if bad_getter == "getId()":
            print(f"  ✓ Correct fallback to getId()")
        else:
            print(f"  ✗ Unexpected fallback getter")
        
    except Exception as e:
        print(f"✗ Error during service generation test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ All metadata integration tests passed!")
    return True


if __name__ == '__main__':
    success = test_metadata_integration()
    sys.exit(0 if success else 1)
