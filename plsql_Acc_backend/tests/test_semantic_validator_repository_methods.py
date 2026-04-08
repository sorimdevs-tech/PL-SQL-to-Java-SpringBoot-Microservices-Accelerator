from src.validator.semantic_validator import SemanticValidator


def test_semantic_validator_rejects_get_total_value_prefix_even_with_query():
    validator = SemanticValidator()
    repositories = {
        "BookRepository.java": """
package com.example.demo.repository;

import java.math.BigDecimal;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface BookRepository extends JpaRepository<BookEntity, Long> {
    @Query("SELECT COALESCE(SUM(e.value), 0) FROM BookEntity e WHERE e.bookid = :bookid")
    BigDecimal getTotalValueByBookid(@Param("bookid") String bookid);
}
"""
    }

    issues = validator._validate_repository_files(repositories)

    assert any(issue.code == "invalid_repository_method_name" for issue in issues)


def test_semantic_validator_accepts_get_sum_prefix_with_query():
    validator = SemanticValidator()
    repositories = {
        "BookRepository.java": """
package com.example.demo.repository;

import java.math.BigDecimal;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface BookRepository extends JpaRepository<BookEntity, Long> {
    @Query("SELECT COALESCE(SUM(e.value), 0) FROM BookEntity e WHERE e.bookid = :bookid")
    BigDecimal getSumValueByBookid(@Param("bookid") String bookid);
}
"""
    }

    issues = validator._validate_repository_files(repositories)

    assert not any(issue.code == "invalid_repository_method_name" for issue in issues)
