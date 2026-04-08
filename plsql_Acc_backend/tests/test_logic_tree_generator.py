from src.generator.logic_tree_generator import (
    LogicTreeGenerationRequest,
    LogicTreePromptBuilder,
    create_logic_tree_prompt,
)


def test_logic_tree_prompt_builder_uses_logic_tree_as_source_of_truth():
    logic_tree = {
        "sequence": [
            {
                "node_type": "count_into",
                "metadata": {
                    "from": "BOOK",
                    "where": "bookid = auxItemId",
                },
            }
        ],
        "branches": [
            {
                "node_type": "if",
                "condition": "auxBook > 0",
                "children": [
                    {"node_type": "then", "text": "SELECT ..."},
                    {"node_type": "else", "text": "DELETE ..."},
                ],
            }
        ],
    }

    prompt = LogicTreePromptBuilder().build_prompt(
        LogicTreeGenerationRequest(
            logic_tree=logic_tree,
            method_name="viewItemLibrary",
            service_name="ViewItemLibraryService",
            repositories=["BookRepository"],
            entities=["BookEntity"],
            entity_fields={"BookEntity": ["bookId", "isbn"]},
        )
    )

    assert "You are NOT converting raw SQL." in prompt
    assert "LOGIC TREE (SOURCE OF TRUTH):" in prompt
    assert '"node_type": "count_into"' in prompt
    assert "FOLLOW LOGIC TREE EXACTLY" in prompt
    assert "SELECT -> repository.findBy..." in prompt
    assert "COUNT -> repository.countBy..." in prompt
    assert "Return exactly one Java method only." in prompt
    assert "No markdown fences." in prompt


def test_create_logic_tree_prompt_exposes_automation_friendly_output_rules():
    prompt = create_logic_tree_prompt(
        logic_tree={"sequence": [], "branches": [], "features": {}},
        method_name="processData",
        repositories=["DataRepository"],
    )

    assert "No prose before the method." in prompt
    assert "If the logic tree is incomplete, do not guess" in prompt
