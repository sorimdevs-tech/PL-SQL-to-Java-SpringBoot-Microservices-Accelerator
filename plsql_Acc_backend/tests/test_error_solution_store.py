from src.rag_engine.error_solution_store import ErrorSolutionStore


def test_error_solution_store_deduplicates_and_retrieves(tmp_path):
    store = ErrorSolutionStore(
        config={
            "enabled": False,
            "provider": "pinecone",
            "fallback_path": str(tmp_path / "error_vectors.json"),
        }
    )

    first = store.store_error_solution(
        error_message="cannot find symbol CustomerRepository",
        sql_context="SELECT * FROM customers WHERE status = 'A'",
        error_type="compilation",
        solution={
            "summary": "Add the missing repository import and align the bean name.",
            "steps": ["Add import", "Fix constructor injection"],
            "changed_files": ["src/main/java/com/company/project/service/CustomerService.java"],
        },
        metadata={"category": "dependency", "code": "cannot find symbol"},
    )
    second = store.store_error_solution(
        error_message="cannot find symbol CustomerRepository",
        sql_context="  select * from customers where status = 'A'  ",
        error_type="compilation",
        solution={"summary": "duplicate"},
        metadata={"category": "dependency", "code": "cannot find symbol"},
    )

    matches = store.retrieve_similar_errors(
        error_message="cannot find symbol CustomerRepository",
        sql_context="SELECT * FROM customers WHERE status = 'A'",
        top_k=3,
        error_type="compilation",
    )

    assert first["stored"] is True
    assert second["stored"] is False
    assert matches
    assert matches[0]["category"] == "dependency"
    assert "repository import" in matches[0]["solution_summary"].lower()
