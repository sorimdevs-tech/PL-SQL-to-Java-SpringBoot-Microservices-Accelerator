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


def test_error_solution_store_deduplicates_same_error_across_files(tmp_path):
    store = ErrorSolutionStore(
        config={
            "enabled": False,
            "provider": "pinecone",
            "fallback_path": str(tmp_path / "error_vectors.json"),
        }
    )

    first_metadata = {
        "category": "general",
        "code": "missing_localdatetime_import",
        "component": "repository",
        "object_name": "AppointmentRepository",
        "file_name": "AppointmentRepository.java",
    }
    second_metadata = {
        "category": "general",
        "code": "missing_localdatetime_import",
        "component": "repository",
        "object_name": "VisitRepository",
        "file_name": "VisitRepository.java",
    }

    first = store.store_error_solution(
        error_message="Repository uses LocalDateTime without importing it",
        sql_context="select * from appointment where apptdate = p_apptdate",
        error_type="semantic-validation",
        solution={"summary": "first capture", "steps": [], "changed_files": []},
        metadata=first_metadata,
    )
    second = store.store_error_solution(
        error_message="Repository uses LocalDateTime without importing it",
        sql_context="select * from visit where visit_time = p_visit_time",
        error_type="semantic-validation",
        solution={"summary": "second capture", "steps": [], "changed_files": []},
        metadata=second_metadata,
    )

    matches = store.retrieve_similar_errors(
        error_message="Repository uses LocalDateTime without importing it",
        sql_context="select * from appointment",
        top_k=10,
        error_type="semantic-validation",
    )

    assert first["stored"] is True
    assert second["stored"] is False
    assert second["fingerprint"] == first["fingerprint"]
    assert len(matches) == 1
    assert matches[0]["code"] == "missing_localdatetime_import"


class _FakeCloudVectorStore:
    def __init__(self):
        self.items = {}

    def has_vector(self, vector_id: str) -> bool:
        return vector_id in self.items

    def uses_cloud_backend(self) -> bool:
        return True

    def get_status(self):
        return {"provider": "fake", "success": True, "mode": "cloud"}

    def store_vectors(self, items):
        for item in items:
            self.items[item["id"]] = item
        return [item["id"] for item in items]

    def search_vectors(self, query_text, top_k=3, metadata_filter=None):
        return []


def test_error_solution_store_allows_store_when_cloud_is_active_and_local_registry_is_stale(tmp_path):
    store = ErrorSolutionStore(
        vector_store=_FakeCloudVectorStore(),
        config={
            "enabled": True,
            "provider": "pinecone",
            "fallback_path": str(tmp_path / "error_vectors.json"),
        },
    )

    stale_metadata = {
        "category": "general",
        "code": "missing_localdatetime_import",
    }
    stale_fingerprint = store.generate_fingerprint(
        error_message="Repository uses LocalDateTime without importing it",
        sql_context="select * from appointment",
        error_type="semantic-validation",
        metadata=stale_metadata,
    )
    stale_record = {
        "fingerprint": stale_fingerprint,
        "error_message": "Repository uses LocalDateTime without importing it",
        "error_type": "semantic-validation",
        "category": "general",
        "code": "missing_localdatetime_import",
    }
    store.registry[stale_fingerprint] = stale_record
    store._rebuild_dedup_index()

    result = store.store_error_solution(
        error_message="Repository uses LocalDateTime without importing it",
        sql_context="select * from appointment",
        error_type="semantic-validation",
        solution={"summary": "re-store after cloud reset", "steps": [], "changed_files": []},
        metadata=stale_metadata,
    )

    assert result["stored"] is True
    assert result["fingerprint"] == stale_fingerprint
