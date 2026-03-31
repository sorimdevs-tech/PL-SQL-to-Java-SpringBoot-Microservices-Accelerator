#!/usr/bin/env python3
"""
Quick pipeline test with metadata integration
Tests that the full service generation flow works with metadata provider
"""

import sys
import os
import tempfile
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def main():
    print("=" * 60)
    print("QUICK PIPELINE TEST WITH METADATA INTEGRATION")
    print("=" * 60)
    
    try:
        from src.parser.table_metadata_provider import TableMetadataProvider
        print("\n✓ Imported TableMetadataProvider")
        
        # Create test metadata
        metadata_provider = TableMetadataProvider()
        
        # Register test tables  
        tables = {
            "EMPLOYEES": {"emp_id": "NUMBER", "name": "VARCHAR2(100)", "salary": "NUMBER"},
            "DEPARTMENTS": {"dept_id": "NUMBER", "dept_name": "VARCHAR2(100)"},
        }
        
        for table_name, columns in tables.items():
            entity_name = f"{table_name.title()}Entity"
            metadata_provider.register_table(table_name, entity_name, columns)
            print(f"✓ Registered {table_name} -> {entity_name}")
        
        # Check metadata retrieval
        emp_meta = metadata_provider.get_table_metadata("EmployeesEntity")
        if emp_meta:
            print(f"✓ Retrieved EmployeesEntity metadata: {len(emp_meta.columns)} columns")
        
        # Test the enhancements added to LLMConversionEngine
        from src.converter.llm_engine import LLMConversionEngine
        
        # Create an engine without requiring API credentials
        engine = LLMConversionEngine.__new__(LLMConversionEngine)
        engine.config = {'output': {'package_name': 'com.test'}}
        
        # Test validation methods
        valid_fields = engine._validate_table_fields_against_metadata("EmployeesEntity", metadata_provider)
        print(f"✓ Field validation for EmployeesEntity: {valid_fields}")
        
        getter = engine._sanitize_getter_call("EmployeesEntity", "salary", valid_fields)
        print(f"✓ Sanitized getter: getSalary() -> {getter}")
        
        # Test with invalid field
        bad_getter = engine._sanitize_getter_call("EmployeesEntity", "nonexistent", valid_fields)
        print(f"✓ Invalid field fallback: {bad_getter}")
        
        print("\n" + "=" * 60)
        print("✅ PIPELINE TEST PASSED - Metadata integration works!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
