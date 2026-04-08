from src.converter.llm_engine import PromptTemplate


def test_prompt_template_includes_logic_conversion_charter_for_service_prompts():
    template = PromptTemplate()
    context = {
        "package_name": "com.company.project",
        "entity_fields": {},
        "entity_sources": "",
        "repository_sources": "",
        "validation_feedback": "",
        "semantic_summary": "{}",
    }
    plsql_ast = {"raw_plsql": "BEGIN NULL; END;"}

    procedure_prompt = template.get_prompt("procedure_to_service", plsql_ast, context)
    function_prompt = template.get_prompt("function_to_service", plsql_ast, context)
    package_prompt = template.get_prompt("package_to_class", plsql_ast, context)
    utility_prompt = template.get_prompt("utility_to_service", plsql_ast, context)

    for prompt in (procedure_prompt, function_prompt, package_prompt, utility_prompt):
        assert "CONVERSION CHARTER:" in prompt
        assert "SELECT COUNT(*) -> repository.countBy..." in prompt
        assert "Never use entity fetch instead of COUNT semantics." in prompt
        assert "If triggers exist, preserve trigger side effects in service-layer logic." in prompt
        assert "If any logic is unclear, do not guess; explicitly mention the missing mapping." in prompt

    assert "Return Java code only. No markdown or explanations outside the Java file." in procedure_prompt
    assert "Return Java code only. No markdown or explanation outside the Java file." in function_prompt
