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


def test_repository_guard_detects_missing_filtered_sum_method():
    engine = _build_test_engine()
    spec = {
        "aggregation_columns": ["PRICE"],
        "lookup_keys": ["BOOKID"],
        "lookup_key_variants": [["BOOKID"]],
    }
    entity_field_types = {
        "BookEntity": {
            "bookid": "String",
            "price": "BigDecimal",
        }
    }
    repository_code = """
package com.example.demo.repository;

import com.example.demo.entity.BookEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

@Repository
public interface BookRepository extends JpaRepository<BookEntity, Long> {
    @Query("SELECT COUNT(e) FROM BookEntity e WHERE e.bookid = :bookid")
    long countByBookid(String bookid);
}
"""

    assert engine._repository_needs_deterministic_aggregation_fix(
        repository_code=repository_code,
        spec=spec,
        entity_name="BookEntity",
        entity_field_types=entity_field_types,
    )


def test_repository_guard_accepts_required_filtered_sum_method():
    engine = _build_test_engine()
    spec = {
        "aggregation_columns": ["PRICE"],
        "lookup_keys": ["BOOKID"],
        "lookup_key_variants": [["BOOKID"]],
    }
    entity_field_types = {
        "BookEntity": {
            "bookid": "String",
            "price": "BigDecimal",
        }
    }
    repository_code = """
package com.example.demo.repository;

import com.example.demo.entity.BookEntity;
import java.math.BigDecimal;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public interface BookRepository extends JpaRepository<BookEntity, Long> {
    @Transactional(readOnly = true)
    @Query("SELECT COALESCE(SUM(e.price), 0) FROM BookEntity e WHERE e.bookid = :bookid")
    BigDecimal getSumPriceByBookid(@Param("bookid") String bookid);
}
"""

    assert not engine._repository_needs_deterministic_aggregation_fix(
        repository_code=repository_code,
        spec=spec,
        entity_name="BookEntity",
        entity_field_types=entity_field_types,
    )
