from src.validator.semantic_enforcement import SemanticEnforcementEngine


def _source_unit() -> dict:
    return {
        "name": "process_balances",
        "object_type": "PROCEDURE",
        "raw_plsql": """
            CURSOR c_acc IS SELECT account_id FROM accounts FOR UPDATE SKIP LOCKED;
            SAVEPOINT batch_start;
            IF v_balance < 0 THEN
                RAISE_APPLICATION_ERROR(-20001, 'Negative balance for customer');
            END IF;
            ROLLBACK TO batch_start;
            COMMIT;
        """,
        "cursor": {"locking": "FOR UPDATE SKIP LOCKED"},
        "transaction": {"has_savepoint": True, "has_partial_rollback": True, "has_commit": True},
    }


def test_semantic_enforcement_flags_batch_cursor_and_literal_violations():
    engine = SemanticEnforcementEngine()
    services = {
        "ProcessBalancesService.java": """
            package com.company.project.service;
            import org.springframework.transaction.annotation.Transactional;
            import org.springframework.data.domain.PageRequest;
            public class ProcessBalancesService {
                @Transactional
                public void processBalances(Long batchSize) {
                    int page = 0;
                    int size = 100;
                    while (true) {
                        accountsRepository.findPageForUpdateSkipLocked(PageRequest.of(page, size));
                        page++;
                        saveErrorRecord("Negative balance for key");
                    }
                }
            }
        """
    }
    repositories = {
        "AccountsRepository.java": """
            import org.springframework.data.domain.Page;
            import org.springframework.data.domain.Pageable;
            import org.springframework.data.jpa.repository.Query;
            public interface AccountsRepository {
                @Query(value = "SELECT * FROM accounts FOR UPDATE SKIP LOCKED", nativeQuery = true)
                Page<AccountsEntity> findPageForUpdateSkipLocked(Pageable pageable);
            }
        """
    }

    issues = engine.validate([_source_unit()], repositories, services)
    issue_codes = {issue.code for issue in issues}
    warning_codes = {issue.code for issue in issues if issue.severity == "warning"}

    assert "savepoint_method_transactional_forbidden" in issue_codes
    assert "savepoint_batch_transaction_missing" in issue_codes
    assert "skip_locked_page_increment" in issue_codes
    assert "skip_locked_offset_pagination" in issue_codes
    assert "literal_message_mismatch" in issue_codes
    assert "native_query_for_update_pageable_risky" in warning_codes


def test_semantic_enforcement_accepts_compliant_batch_cursor_and_literal_behavior():
    engine = SemanticEnforcementEngine()
    services = {
        "ProcessBalancesService.java": """
            package com.company.project.service;
            import org.springframework.transaction.support.TransactionTemplate;
            import org.springframework.data.domain.Page;
            import org.springframework.data.domain.PageRequest;
            public class ProcessBalancesService {
                private final TransactionTemplate batchTransactionTemplate;

                public void processBalances(Long batchSize) {
                    int size = 100;
                    boolean hasMore = true;
                    while (hasMore) {
                        Page<AccountsEntity> pageBatch = accountsRepository.findPageForUpdateSkipLocked(PageRequest.of(0, size));
                        hasMore = pageBatch.hasContent();
                        if (!hasMore) {
                            continue;
                        }
                        final boolean[] batchHasError = new boolean[] { false };
                        batchTransactionTemplate.executeWithoutResult(status -> {
                            if (batchHasError[0]) {
                                status.setRollbackOnly();
                            }
                        });
                        saveErrorRecord("Negative balance for customer");
                    }
                }
            }
        """
    }
    repositories = {
        "AccountsRepository.java": """
            import org.springframework.data.jpa.repository.Query;
            import org.springframework.data.repository.query.Param;
            public interface AccountsRepository {
                @Query(value = "SELECT * FROM accounts WHERE status = :status FOR UPDATE SKIP LOCKED", nativeQuery = true)
                java.util.List<AccountsEntity> lockBatchWithoutPageable(@Param("status") String status);
            }
        """
    }

    issues = engine.validate([_source_unit()], repositories, services)
    assert not any(issue.severity == "error" for issue in issues)

