from src.converter.llm_engine import PromptTemplate
from src.converter.llm_engine_integration import inject_enhanced_prompts
from src.parser.table_metadata_provider import TableMetadataProvider


def test_llm_prompt_includes_metadata_guidance_and_repository_examples():
    provider = TableMetadataProvider()
    provider.register_table('TEST_TABLE', 'TestEntity', {'ID': 'NUMBER', 'NAME': 'VARCHAR2(50)'})

    prompt = inject_enhanced_prompts(
        PromptTemplate(),
        {'type': 'procedure', 'raw_plsql': 'BEGIN NULL; END;', 'name': 'TEST_PROC'},
        {
            'package_name': 'com.example.project',
            'entity_fields': 'TestEntity: id (Long)',
            'conversion_type': 'procedure_to_service',
            'plsql_code': 'BEGIN NULL; END;',
        },
        metadata_provider=provider,
    )

    assert 'Spring Data guidance:' in prompt
    assert 'Repository examples:' in prompt
    assert 'TestEntity' in prompt
