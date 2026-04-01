#!/usr/bin/env python
"""Test FK generation in entity classes"""

from src.generator.spring_boot_generator import SpringBootGenerator

def test_fk_generation():
    """Test that FKs are properly converted to @ManyToOne and @JoinColumn"""
    
    config = {
        "package_name": "com.example.app",
        "artifact_id": "test-app",
        "java_version": "17",
        "build_tool": "maven",
        "spring_boot_version": "3.0.0",
        "group_id": "com.example",
        "target_directory": "./test_output"
    }
    
    generator = SpringBootGenerator(config)
    
    # Test case: Order entity with FK to Customer
    columns = [
        {"name": "ORDER_ID", "type": "NUMBER"},
        {"name": "CUSTOMER_ID", "type": "NUMBER"},
        {"name": "ORDER_DATE", "type": "TIMESTAMP"}
    ]
    
    fk_list = [
        {
            "column": "CUSTOMER_ID",
            "ref_table": "CUSTOMER",
            "ref_column": "CUSTOMER_ID"
        }
    ]
    
    entity_code = generator._generate_entity_from_ddl(
        entity_name="OrderEntity",
        table_name="ORDER",
        columns=columns,
        fk_list=fk_list
    )
    
    print("Generated Entity Code:")
    print("=" * 80)
    print(entity_code)
    print("=" * 80)
    
    # Verify FK-related annotations are present
    assert "@ManyToOne(fetch = FetchType.LAZY)" in entity_code, "Missing @ManyToOne annotation"
    assert "@JoinColumn(name = \"CUSTOMER_ID\"" in entity_code, "Missing @JoinColumn annotation"
    assert "private CustomerEntity customerId;" in entity_code, "Missing FK field declaration"
    assert "import com.example.app.entity.CustomerEntity;" in entity_code, "Missing FK entity import"
    
    print("\n✅ FK generation test PASSED!")
    print("✅ Entity field with @ManyToOne annotation properly generated")
    print("✅ @JoinColumn annotation properly generated")
    print("✅ Related entity imported correctly")

if __name__ == "__main__":
    test_fk_generation()
