from src.converter.llm_engine import LLMConversionEngine


def _build_test_engine() -> LLMConversionEngine:
    return LLMConversionEngine(
        {
            "provider": "openrouter",
            "model": "openai/gpt-4o-mini",
            "api_key": "test-key",
            "base_url": "https://openrouter.ai/api/v1",
            "timeout": 30,
            "retry_attempts": 1,
            "batch_size": 1,
        }
    )


def test_service_repair_prompt_includes_correction_engine_rules():
    engine = _build_test_engine()
    prompt = engine._build_service_repair_prompt(
        service_filename="ViewItemLibraryService.java",
        current_code="public class ViewItemLibraryService {}",
        issues=[
            {
                "message": "ViewItemLibraryService.java appears to implement COUNT(*) using row-fetch semantics instead of query/count semantics",
                "file_name": "ViewItemLibraryService.java",
            }
        ],
        entities={
            "BookEntity.java": "public class BookEntity { private String bookId; }",
        },
        repositories={
            "BookRepository.java": "public interface BookRepository { long countByBookId(String bookId); }",
        },
    )

    assert "You are a PL/SQL -> Java correction engine." in prompt
    assert "Restore all missing IF / ELSIF / ELSE branches." in prompt
    assert "If the source behavior implies COUNT(*), use repository.countBy..." in prompt
    assert "Never use findBy... or entity fetch to simulate COUNT semantics." in prompt
    assert "Do not leave any validation error unresolved." in prompt
    assert "Repair the code instead of rewriting randomly." in prompt
