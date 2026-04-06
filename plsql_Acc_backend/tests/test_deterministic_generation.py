import asyncio
import re

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


def _build_entities() -> dict[str, str]:
    return {
        "AccountsEntity.java": """
            public class AccountsEntity {
                private Long accountId;
                private String status;
                public Long getAccountId() { return accountId; }
            }
        """,
        "TransactionsEntity.java": """
            public class TransactionsEntity {
                private Long accountId;
                private java.math.BigDecimal amount;
            }
        """,
        "AccountBalanceEntity.java": """
            public class AccountBalanceEntity {
                private Long accountId;
                private java.math.BigDecimal balance;
                private java.time.LocalDateTime updatedAt;
                public void setAccountId(Long accountId) {}
                public void setBalance(java.math.BigDecimal balance) {}
                public void setUpdatedAt(java.time.LocalDateTime updatedAt) {}
            }
        """,
    }


def _build_source_units() -> list[dict]:
    process_balances = {
        "name": "process_balances",
        "object_type": "PROCEDURE",
        "raw_plsql": """
            CURSOR c_acc IS SELECT account_id FROM accounts FOR UPDATE SKIP LOCKED;
            SAVEPOINT batch_start;
            SELECT NVL(SUM(amount), 0) INTO v_balance FROM transactions WHERE account_id = v_acc.account_id;
            MERGE INTO account_balance ab USING dual ON (ab.account_id = v_acc.account_id)
            WHEN MATCHED THEN UPDATE SET balance = v_balance;
            ROLLBACK TO batch_start;
            COMMIT;
        """,
        "operations_by_table": {
            "ACCOUNTS": ["SELECT"],
            "TRANSACTIONS": ["SELECT"],
            "ACCOUNT_BALANCE": ["MERGE"],
        },
        "lookup_keys": {
            "ACCOUNTS": ["STATUS"],
            "TRANSACTIONS": ["ACCOUNT_ID"],
            "ACCOUNT_BALANCE": ["ACCOUNT_ID"],
        },
        "skip_locked_tables": ["ACCOUNTS"],
        "driving_table": "ACCOUNTS",
        "target_tables": ["ACCOUNT_BALANCE"],
        "bulk_operations": [{"type": "BULK_COLLECT"}],
        "cursor": {"locking": "FOR UPDATE SKIP LOCKED"},
        "transaction": {
            "required": True,
            "has_savepoint": True,
            "has_partial_rollback": True,
            "has_commit": True,
            "has_rollback": True,
        },
        "input_parameters": [{"name": "p_batch_size", "type": "NUMBER", "direction": "IN"}],
        "semantic_analysis": {
            "aggregation": {"columns": ["transactions.amount"]},
            "upsert_operations": [{"table": "ACCOUNT_BALANCE"}],
            "business_rules": [],
            "error_handling_semantics": [],
        },
    }
    flag_high_risk = {
        "name": "flag_high_risk",
        "object_type": "PROCEDURE",
        "raw_plsql": "UPDATE accounts a SET status = 'REVIEW' WHERE EXISTS (SELECT 1 FROM transactions t WHERE t.account_id = a.account_id AND t.amount > 10000);",
        "operations_by_table": {
            "ACCOUNTS": ["UPDATE"],
            "TRANSACTIONS": ["SELECT"],
        },
        "lookup_keys": {
            "TRANSACTIONS": ["ACCOUNT_ID", "AMOUNT"],
        },
        "skip_locked_tables": [],
        "driving_table": "ACCOUNTS",
        "target_tables": ["ACCOUNTS"],
        "bulk_operations": [],
        "cursor": {},
        "transaction": {},
        "input_parameters": [],
        "semantic_analysis": {},
    }
    return [process_balances, flag_high_risk]


def _generate_repositories_and_services() -> tuple[dict[str, str], dict[str, str]]:
    async def _run() -> tuple[dict[str, str], dict[str, str]]:
        engine = _build_test_engine()
        entities = _build_entities()
        source_units = _build_source_units()
        repositories = await engine.generate_repositories_from_semantics(source_units, entities)
        services = await engine.generate_services_from_semantics(source_units, entities, repositories)
        return repositories, services

    return asyncio.run(_run())


def test_repository_generation_emits_sum_methods_for_each_lookup_variant():
    repositories, _ = _generate_repositories_and_services()
    transactions_repo = repositories["TransactionsRepository.java"]
    assert "BigDecimal sumByAccountId(" in transactions_repo
    assert "BigDecimal sumByAccountIdAndAmount(" in transactions_repo


def test_service_generation_adds_transactional_annotation_for_savepoint_units():
    _, services = _generate_repositories_and_services()
    process_service = services["ProcessBalancesService.java"]
    assert re.search(r"@Transactional\s+public\s+void\s+processBalances\(", process_service)


def test_service_generation_prefers_richer_duplicate_unit_for_same_service_filename():
    async def _run() -> dict[str, str]:
        engine = _build_test_engine()
        entities = {
            "XyCustomerEntity.java": """
                public class XyCustomerEntity {
                    private Long customerId;
                    public Long getCustomerId() { return customerId; }
                }
            """
        }
        repositories = {
            "XyCustomerRepository.java": """
                public interface XyCustomerRepository
                    extends org.springframework.data.jpa.repository.JpaRepository<XyCustomerEntity, Long> {}
            """
        }
        rich_unit = {
            "name": "customer_pkg",
            "object_type": "PACKAGE",
            "raw_plsql": "BEGIN SAVEPOINT batch_start; EXCEPTION WHEN OTHERS THEN ROLLBACK TO batch_start; END;",
            "operations_by_table": {"XY_CUSTOMER": ["UPDATE"]},
            "lookup_keys": {"XY_CUSTOMER": ["CUSTOMER_ID"]},
            "driving_table": "XY_CUSTOMER",
            "target_tables": ["XY_CUSTOMER"],
            "bulk_operations": [],
            "cursor": {},
            "transaction": {"has_savepoint": True},
            "input_parameters": [],
            "semantic_analysis": {},
        }
        sparse_duplicate = {
            "name": "customer_pkg",
            "object_type": "PACKAGE",
            "raw_plsql": "PACKAGE customer_pkg IS END;",
            "operations_by_table": {},
            "lookup_keys": {},
            "driving_table": "",
            "target_tables": [],
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [],
            "semantic_analysis": {},
        }
        return await engine.generate_services_from_semantics(
            [rich_unit, sparse_duplicate],
            entities,
            repositories,
        )

    services = asyncio.run(_run())
    customer_service = services["CustomerPkgService.java"]
    assert "XyCustomerRepository" in customer_service
    assert "No SQL operations" not in customer_service
    assert "continue;" in customer_service


def test_service_generation_prefers_duplicate_utility_unit_with_raise_metadata():
    async def _run() -> dict[str, str]:
        engine = _build_test_engine()
        rich_utility_unit = {
            "name": "appl_error_pkg",
            "object_type": "PACKAGE",
            "raw_plsql": "BEGIN raise_application_error(-20001, 'invalid'); END;",
            "operations_by_table": {},
            "programmatic_raises": [{"error_code": -20001, "message": "invalid"}],
            "input_parameters": [],
            "semantic_analysis": {},
        }
        sparse_duplicate = {
            "name": "appl_error_pkg",
            "object_type": "PACKAGE",
            "raw_plsql": "PACKAGE appl_error_pkg IS END;",
            "operations_by_table": {},
            "programmatic_raises": [],
            "input_parameters": [],
            "semantic_analysis": {},
        }
        return await engine.generate_services_from_semantics(
            [rich_utility_unit, sparse_duplicate],
            entities={},
            repositories={},
        )

    services = asyncio.run(_run())
    error_service = services["ApplErrorPkgService.java"]
    assert 'throw new BusinessException(-20001, "invalid");' in error_service


def test_service_generation_imports_bigdecimal_when_parameter_is_decimal():
    async def _run() -> dict[str, str]:
        engine = _build_test_engine()
        entities = {
            "PaymentsEntity.java": """
                public class PaymentsEntity {
                    private Long paymentId;
                    private java.math.BigDecimal amount;
                }
            """
        }
        repositories = {
            "PaymentsRepository.java": """
                public interface PaymentsRepository
                    extends org.springframework.data.jpa.repository.JpaRepository<PaymentsEntity, Long> {}
            """
        }
        source_units = [
            {
                "name": "payment_pkg_create_payment",
                "subprogram_name": "create_payment",
                "object_type": "PACKAGE_PROCEDURE",
                "raw_plsql": "BEGIN INSERT INTO payments(amount) VALUES (p_amount); END;",
                "operations_by_table": {"PAYMENTS": ["INSERT"]},
                "lookup_keys": {"PAYMENTS": ["PAYMENT_ID"]},
                "driving_table": "PAYMENTS",
                "target_tables": ["PAYMENTS"],
                "bulk_operations": [],
                "cursor": {},
                "transaction": {},
                "input_parameters": [{"name": "p_amount", "type": "NUMBER(10,2)", "direction": "IN"}],
                "semantic_analysis": {},
            }
        ]
        return await engine.generate_services_from_semantics(source_units, entities, repositories)

    services = asyncio.run(_run())
    code = services["PaymentPkgCreatePaymentService.java"]
    assert "import java.math.BigDecimal;" in code
    assert "public void createPayment(BigDecimal amount)" in code


def test_service_generation_emits_select_and_delete_repository_calls_for_simple_units():
    async def _run() -> dict[str, str]:
        engine = _build_test_engine()
        entities = {
            "CustomersEntity.java": """
                public class CustomersEntity {
                    private Long customerId;
                }
            """
        }
        repositories = {
            "CustomersRepository.java": """
                public interface CustomersRepository
                    extends org.springframework.data.jpa.repository.JpaRepository<CustomersEntity, Long> {
                    java.util.Optional<CustomersEntity> findByCustomerId(Long customerId);
                }
            """
        }
        source_units = [
            {
                "name": "customer_pkg_get_customer",
                "subprogram_name": "get_customer",
                "object_type": "PACKAGE_PROCEDURE",
                "raw_plsql": "BEGIN SELECT * FROM customers WHERE customer_id = p_customer_id; END;",
                "operations_by_table": {"CUSTOMERS": ["SELECT"]},
                "lookup_keys": {"CUSTOMERS": ["CUSTOMER_ID"]},
                "driving_table": "CUSTOMERS",
                "target_tables": ["CUSTOMERS"],
                "bulk_operations": [],
                "cursor": {},
                "transaction": {},
                "input_parameters": [{"name": "p_customer_id", "type": "NUMBER", "direction": "IN"}],
                "semantic_analysis": {},
            },
            {
                "name": "customer_pkg_delete_customer",
                "subprogram_name": "delete_customer",
                "object_type": "PACKAGE_PROCEDURE",
                "raw_plsql": "BEGIN DELETE FROM customers WHERE customer_id = p_customer_id; END;",
                "operations_by_table": {"CUSTOMERS": ["DELETE"]},
                "lookup_keys": {"CUSTOMERS": ["CUSTOMER_ID"]},
                "driving_table": "CUSTOMERS",
                "target_tables": ["CUSTOMERS"],
                "bulk_operations": [],
                "cursor": {},
                "transaction": {},
                "input_parameters": [{"name": "p_customer_id", "type": "NUMBER", "direction": "IN"}],
                "semantic_analysis": {},
            },
        ]
        return await engine.generate_services_from_semantics(source_units, entities, repositories)

    services = asyncio.run(_run())
    get_code = services["CustomerPkgGetCustomerService.java"]
    delete_code = services["CustomerPkgDeleteCustomerService.java"]
    assert ".findByCustomerId(" in get_code or ".findById(" in get_code or ".findAll(" in get_code
    assert ".deleteById(" in delete_code
