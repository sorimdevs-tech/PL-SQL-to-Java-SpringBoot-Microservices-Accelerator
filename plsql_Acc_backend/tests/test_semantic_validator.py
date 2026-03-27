from src.validator.semantic_validator import SemanticValidator


def test_semantic_validator_detects_missing_repository_method_and_missing_batching():
    validator = SemanticValidator("com.company.project")

    source_units = [
        {
            "name": "reconcile_customer_balances",
            "object_type": "PROCEDURE",
            "raw_plsql": """
                CREATE OR REPLACE PROCEDURE reconcile_customer_balances IS
                BEGIN
                    MERGE INTO customer_balance cb USING dual ON (cb.customer_id = 1)
                    WHEN MATCHED THEN UPDATE SET balance = 1
                    WHEN NOT MATCHED THEN INSERT (balance_id, customer_id, balance) VALUES (1, 1, 1);
                END;
            """,
            "tables_used": ["CUSTOMER_BALANCE"],
            "operations_by_table": {"CUSTOMER_BALANCE": ["MERGE"]},
            "bulk_operations": [{"type": "BULK_COLLECT"}],
            "cursor": {"locking": "FOR UPDATE SKIP LOCKED"},
            "transaction": {"has_savepoint": True},
            "input_parameters": [{"name": "p_run_mode", "type": "VARCHAR2"}],
        }
    ]

    entities = {
        "CustomerBalanceEntity.java": """
            package com.company.project.entity;
            import jakarta.persistence.*;
            @Entity
            public class CustomerBalanceEntity {
                @Id
                private Long balanceId;
                private Long customerId;
                private java.math.BigDecimal balance;
                public void setCustomerId(Long customerId) { this.customerId = customerId; }
                public void setBalance(java.math.BigDecimal balance) { this.balance = balance; }
                public Long getCustomerId() { return customerId; }
            }
        """
    }

    repositories = {
        "CustomerBalanceRepository.java": """
            package com.company.project.repository;
            import org.springframework.data.jpa.repository.JpaRepository;
            import com.company.project.entity.CustomerBalanceEntity;
            public interface CustomerBalanceRepository extends JpaRepository<CustomerBalanceEntity, Long> {
            }
        """
    }

    services = {
        "ReconcileCustomerBalancesService.java": """
            package com.company.project.service;
            import org.springframework.stereotype.Service;
            @Service
            public class ReconcileCustomerBalancesService {
                private CustomerBalanceRepository customerBalanceRepository;

                public void reconcileCustomerBalances(String pRunMode) {
                    switch (pRunMode) {
                        case "INSERT":
                            customerBalanceRepository.findByCustomerId(1L);
                            break;
                        default:
                            break;
                    }
                }
            }
        """
    }

    report = validator.validate(source_units, entities, repositories, services)
    issue_codes = {issue.code for issue in report.issues}

    assert not report.passed
    assert "missing_repository_method" in issue_codes
    assert "bulk_collect_not_preserved" in issue_codes
    assert "skip_locked_not_preserved" in issue_codes
    assert "transaction_not_preserved" in issue_codes
    assert "mode_flag_misused" in issue_codes


def test_semantic_validator_enforces_lookup_repository_methods_and_upsert_shape():
    validator = SemanticValidator("com.company.project")
    source_units = [
        {
            "name": "upsert_balance",
            "object_type": "PROCEDURE",
            "raw_plsql": """
                BEGIN
                    MERGE INTO customer_balance cb USING dual ON (cb.customer_id = 1)
                    WHEN MATCHED THEN UPDATE SET balance = 1
                    WHEN NOT MATCHED THEN INSERT (balance_id, customer_id, balance) VALUES (1, 1, 1);
                END;
            """,
            "tables_used": ["CUSTOMER_BALANCE"],
            "operations_by_table": {"CUSTOMER_BALANCE": ["MERGE"]},
            "lookup_keys": {"CUSTOMER_BALANCE": ["CUSTOMER_ID"]},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [],
        }
    ]
    entities = {
        "CustomerBalanceEntity.java": """
            package com.company.project.entity;
            public class CustomerBalanceEntity {}
        """
    }
    repositories = {
        "CustomerBalanceRepository.java": """
            package com.company.project.repository;
            import org.springframework.data.jpa.repository.JpaRepository;
            import com.company.project.entity.CustomerBalanceEntity;
            public interface CustomerBalanceRepository extends JpaRepository<CustomerBalanceEntity, Long> {
            }
        """
    }
    services = {
        "UpsertBalanceService.java": """
            package com.company.project.service;
            import org.springframework.stereotype.Service;
            @Service
            public class UpsertBalanceService {
                private CustomerBalanceRepository customerBalanceRepository;
                public void upsertBalance() {
                    customerBalanceRepository.save(new CustomerBalanceEntity());
                }
            }
        """
    }

    report = validator.validate(source_units, entities, repositories, services)
    issue_codes = {issue.code for issue in report.issues}
    assert "missing_lookup_repository_method" in issue_codes
    assert "merge_not_preserved" in issue_codes


def test_semantic_validator_flags_findall_misuse_for_bulk_collect():
    validator = SemanticValidator("com.company.project")
    source_units = [
        {
            "name": "bulk_sync",
            "object_type": "PROCEDURE",
            "raw_plsql": "BEGIN FETCH c BULK COLLECT INTO t; END;",
            "tables_used": ["PAYMENTS"],
            "operations_by_table": {"PAYMENTS": ["SELECT"]},
            "lookup_keys": {"PAYMENTS": ["PAYMENT_ID"]},
            "bulk_operations": [{"type": "BULK_COLLECT"}],
            "cursor": {"locking": ""},
            "transaction": {"has_savepoint": False},
            "input_parameters": [],
        }
    ]
    entities = {"PaymentsEntity.java": "public class PaymentsEntity {}"}
    repositories = {
        "PaymentsRepository.java": """
            import org.springframework.data.jpa.repository.JpaRepository;
            public interface PaymentsRepository extends JpaRepository<PaymentsEntity, Long> {
                java.util.Optional<PaymentsEntity> findByPaymentId(Long paymentId);
            }
        """
    }
    services = {
        "BulkSyncService.java": """
            package com.company.project.service;
            import org.springframework.stereotype.Service;
            @Service
            public class BulkSyncService {
                private PaymentsRepository paymentsRepository;
                public void bulkSync() {
                    paymentsRepository.findAll();
                }
            }
        """
    }

    report = validator.validate(source_units, entities, repositories, services)
    issue_codes = {issue.code for issue in report.issues}
    assert "findall_misuse" in issue_codes
    assert "bulk_collect_not_preserved" in issue_codes


def test_semantic_validator_requires_generic_try_catch_for_non_iterative_exception_blocks():
    validator = SemanticValidator("com.company.project")
    source_units = [
        {
            "name": "login_customer",
            "object_type": "PROCEDURE",
            "raw_plsql": """
                CREATE OR REPLACE PROCEDURE login_customer(p_user IN VARCHAR2) IS
                BEGIN
                  NULL;
                EXCEPTION
                  WHEN NO_DATA_FOUND THEN NULL;
                END;
            """,
            "tables_used": ["CUSTOMER"],
            "operations_by_table": {"CUSTOMER": ["SELECT"]},
            "lookup_keys": {"CUSTOMER": ["USERNAME"]},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {"has_savepoint": False},
            "input_parameters": [{"name": "p_user", "type": "VARCHAR2"}],
        }
    ]
    entities = {"CustomerEntity.java": "public class CustomerEntity { private String username; }"}
    repositories = {
        "CustomerRepository.java": """
            import org.springframework.data.jpa.repository.JpaRepository;
            public interface CustomerRepository extends JpaRepository<CustomerEntity, Long> {
                java.util.Optional<CustomerEntity> findByUsername(String username);
            }
        """
    }
    services = {
        "LoginCustomerService.java": """
            package com.company.project.service;
            import org.springframework.stereotype.Service;
            @Service
            public class LoginCustomerService {
                private CustomerRepository customerRepository;
                public void loginCustomer(String user) {
                    customerRepository.findByUsername(user);
                }
            }
        """
    }

    report = validator.validate(source_units, entities, repositories, services)
    issue_codes = {issue.code for issue in report.issues}
    assert "missing_exception_fallback" in issue_codes
    assert "missing_row_level_try_catch" not in issue_codes
