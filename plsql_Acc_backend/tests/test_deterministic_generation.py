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
            IF v_balance < 0 THEN
                RAISE_APPLICATION_ERROR(-20001, 'Negative balance for customer');
            END IF;
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
            "business_rules": [{"condition": "v_balance < 0", "action": "RAISE_APPLICATION_ERROR"}],
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


def _generate_services_from_payload(
    source_units: list[dict],
    entities: dict[str, str],
    repositories: dict[str, str],
) -> dict[str, str]:
    async def _run() -> dict[str, str]:
        engine = _build_test_engine()
        return await engine.generate_services_from_semantics(source_units, entities, repositories)

    return asyncio.run(_run())


def _generate_repositories_from_payload(
    source_units: list[dict],
    entities: dict[str, str],
) -> dict[str, str]:
    async def _run() -> dict[str, str]:
        engine = _build_test_engine()
        return await engine.generate_repositories_from_semantics(source_units, entities)

    return asyncio.run(_run())


def test_repository_generation_limits_sum_methods_to_aggregation_variants():
    repositories, _ = _generate_repositories_and_services()
    transactions_repo = repositories["TransactionsRepository.java"]
    assert "BigDecimal sumByAccountId(" in transactions_repo
    assert "BigDecimal sumByAccountIdAndAmount(" not in transactions_repo
    assert "sumByAccountIdIn(" not in transactions_repo


def test_service_generation_enforces_batch_transaction_for_savepoint_units():
    _, services = _generate_repositories_and_services()
    process_service = services["ProcessBalancesService.java"]
    assert not re.search(r"@Transactional\s+public\s+void\s+processBalances\(", process_service)
    assert "TransactionTemplate" in process_service
    assert "executeWithoutResult" in process_service
    assert "PageRequest.of(0, size)" in process_service
    assert "page++;" not in process_service
    assert '"Negative balance for customer"' in process_service
    assert "Negative balance for key" not in process_service


def test_service_generation_avoids_findby_for_aggregation_tables():
    _, services = _generate_repositories_and_services()
    process_service = services["ProcessBalancesService.java"]
    assert "transactionsRepository.sumBy" in process_service
    assert "transactionsRepository.findBy" not in process_service


def test_service_generation_avoids_dual_repository_fallback():
    source_units = [
        {
            "name": "assert_service",
            "object_type": "PROCEDURE",
            "raw_plsql": "BEGIN SELECT 1 INTO v_dummy FROM dual; END;",
            "operations_by_table": {"DUAL": ["SELECT"]},
            "driving_table": "DUAL",
            "target_tables": [],
            "lookup_keys": {},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [],
            "semantic_analysis": {},
        }
    ]
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
            public interface XyCustomerRepository extends org.springframework.data.jpa.repository.JpaRepository<XyCustomerEntity, Long> {}
        """
    }

    services = _generate_services_from_payload(source_units, entities, repositories)
    service_code = services["AssertService.java"]
    assert "DualRepository" not in service_code
    assert "XyCustomerRepository" in service_code


def test_service_generation_avoids_missing_row_getter_for_lookup_keys():
    source_units = [
        {
            "name": "purge_old_customers",
            "object_type": "PROCEDURE",
            "raw_plsql": """
                BEGIN
                    MERGE INTO purge_audit pa USING dual ON (pa.last_active_date = SYSDATE - 90)
                    WHEN MATCHED THEN UPDATE SET pa.last_active_date = SYSDATE;
                END;
            """,
            "operations_by_table": {
                "XY_CUSTOMER": ["SELECT"],
                "PURGE_AUDIT": ["MERGE"],
            },
            "driving_table": "XY_CUSTOMER",
            "target_tables": ["PURGE_AUDIT"],
            "lookup_keys": {
                "PURGE_AUDIT": ["LAST_ACTIVE_DATE"],
            },
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [],
            "semantic_analysis": {
                "upsert_operations": [{"table": "PURGE_AUDIT"}],
            },
        }
    ]
    entities = {
        "XyCustomerEntity.java": """
            public class XyCustomerEntity {
                private Long customerId;
                public Long getCustomerId() { return customerId; }
            }
        """,
        "PurgeAuditEntity.java": """
            public class PurgeAuditEntity {
                private java.time.LocalDateTime lastActiveDate;
                public void setLastActiveDate(java.time.LocalDateTime lastActiveDate) {}
            }
        """,
    }
    repositories = {
        "XyCustomerRepository.java": """
            public interface XyCustomerRepository extends org.springframework.data.jpa.repository.JpaRepository<XyCustomerEntity, Long> {}
        """,
        "PurgeAuditRepository.java": """
            public interface PurgeAuditRepository extends org.springframework.data.jpa.repository.JpaRepository<PurgeAuditEntity, Long> {
                java.util.Optional<PurgeAuditEntity> findByLastActiveDate(java.time.LocalDateTime lastActiveDate);
            }
        """,
    }

    services = _generate_services_from_payload(source_units, entities, repositories)
    service_code = services["PurgeOldCustomersService.java"]
    assert "row.getLastActiveDate()" not in service_code


def test_service_generation_imports_localdatetime_and_avoids_fake_loop_stub():
    source_units = [
        {
            "name": "cleanup_records",
            "object_type": "PROCEDURE",
            "raw_plsql": "BEGIN NULL; END;",
            "operations_by_table": {"CUSTOMERS": ["SELECT"]},
            "driving_table": "CUSTOMERS",
            "target_tables": [],
            "lookup_keys": {},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {"has_savepoint": True},
            "input_parameters": [{"name": "p_cutoff", "type": "DATE", "direction": "IN"}],
            "semantic_analysis": {},
        }
    ]
    entities = {
        "CustomersEntity.java": """
            public class CustomersEntity {
                private Long id;
                public Long getId() { return id; }
            }
        """
    }
    repositories = {
        "CustomersRepository.java": """
            public interface CustomersRepository extends org.springframework.data.jpa.repository.JpaRepository<CustomersEntity, Long> {}
        """
    }

    services = _generate_services_from_payload(source_units, entities, repositories)
    service_code = services["CleanupRecordsService.java"]
    assert "import java.time.LocalDateTime;" in service_code
    assert "rowIndex < 1" not in service_code


def test_repository_generation_omits_findby_for_aggregation_only_tables():
    source_units = [
        {
            "name": "agg_only",
            "object_type": "PROCEDURE",
            "raw_plsql": "SELECT SUM(amount) INTO v_total FROM rent WHERE cardid = p_cardid;",
            "operations_by_table": {"RENT": ["SELECT"]},
            "driving_table": "RENT",
            "target_tables": [],
            "lookup_keys": {"RENT": ["CARDID"]},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [{"name": "p_cardid", "type": "NUMBER", "direction": "IN"}],
            "semantic_analysis": {"aggregation": {"columns": ["rent.amount"]}},
        }
    ]
    entities = {
        "RentEntity.java": """
            public class RentEntity {
                private Long cardid;
                private java.math.BigDecimal amount;
            }
        """
    }

    repositories = _generate_repositories_from_payload(source_units, entities)
    rent_repo = repositories["RentRepository.java"]
    assert "sumByCardid(" in rent_repo
    assert "findByCardid(" not in rent_repo


def test_repository_generation_keeps_findby_for_mixed_aggregation_tables():
    source_units = [
        {
            "name": "agg_with_update",
            "object_type": "PROCEDURE",
            "raw_plsql": "UPDATE rent SET amount = amount WHERE cardid = p_cardid;",
            "operations_by_table": {"RENT": ["SELECT", "UPDATE"]},
            "driving_table": "RENT",
            "target_tables": ["RENT"],
            "lookup_keys": {"RENT": ["CARDID"]},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [{"name": "p_cardid", "type": "NUMBER", "direction": "IN"}],
            "semantic_analysis": {"aggregation": {"columns": ["rent.amount"]}},
        }
    ]
    entities = {
        "RentEntity.java": """
            public class RentEntity {
                private Long cardid;
                private java.math.BigDecimal amount;
            }
        """
    }

    repositories = _generate_repositories_from_payload(source_units, entities)
    rent_repo = repositories["RentRepository.java"]
    assert "sumByCardid(" in rent_repo
    assert "findByCardid(" in rent_repo


def test_repository_generation_splits_lookup_and_sum_variants_for_mixed_units():
    source_units = [
        {
            "name": "customer_account",
            "object_type": "PROCEDURE",
            "raw_plsql": "SELECT SUM(amount) INTO v_total FROM rent WHERE cardid = p_cardid;",
            "operations_by_table": {"RENT": ["SELECT"]},
            "driving_table": "RENT",
            "target_tables": [],
            "lookup_keys": {"RENT": ["CARDID"]},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [{"name": "p_cardid", "type": "NUMBER", "direction": "IN"}],
            "semantic_analysis": {"aggregation": {"columns": ["rent.amount"]}},
        },
        {
            "name": "handle_return",
            "object_type": "PROCEDURE",
            "raw_plsql": "DELETE FROM rent WHERE cardid = p_cardid AND itemid = p_itemid;",
            "operations_by_table": {"RENT": ["SELECT", "DELETE"]},
            "driving_table": "RENT",
            "target_tables": ["RENT"],
            "lookup_keys": {"RENT": ["CARDID", "ITEMID"]},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [
                {"name": "p_cardid", "type": "NUMBER", "direction": "IN"},
                {"name": "p_itemid", "type": "NUMBER", "direction": "IN"},
            ],
            "semantic_analysis": {"aggregation": {"columns": ["rent.amount"]}},
        },
    ]
    entities = {
        "RentEntity.java": """
            public class RentEntity {
                private Long cardid;
                private Long itemid;
                private java.math.BigDecimal amount;
            }
        """
    }

    repositories = _generate_repositories_from_payload(source_units, entities)
    rent_repo = repositories["RentRepository.java"]
    assert "sumByCardid(" in rent_repo
    assert "sumByCardidAndItemid(" in rent_repo
    assert "findByCardidAndItemid(" in rent_repo
    assert "findByCardid(" not in rent_repo


def test_direct_insert_function_uses_input_and_returns_id():
    source_units = [
        {
            "name": "new_customer",
            "object_type": "FUNCTION",
            "raw_plsql": """
                CREATE OR REPLACE FUNCTION new_customer(p_customer_name IN VARCHAR2) RETURN NUMBER IS
                  l_returnvalue xy_customer.customer_id%TYPE;
                BEGIN
                  INSERT INTO xy_customer(customer_name) VALUES (p_customer_name)
                  RETURNING customer_id INTO l_returnvalue;
                  RETURN l_returnvalue;
                END;
            """,
            "operations_by_table": {"XY_CUSTOMER": ["INSERT"]},
            "driving_table": "XY_CUSTOMER",
            "target_tables": ["XY_CUSTOMER"],
            "lookup_keys": {},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [{"name": "p_customer_name", "type": "VARCHAR2", "direction": "IN"}],
            "semantic_analysis": {},
        }
    ]
    entities = {
        "XyCustomerEntity.java": """
            public class XyCustomerEntity {
                private Long customerId;
                private String customerName;
                public Long getCustomerId() { return customerId; }
                public void setCustomerName(String customerName) {}
            }
        """
    }
    repositories = {
        "XyCustomerRepository.java": """
            public interface XyCustomerRepository extends org.springframework.data.jpa.repository.JpaRepository<XyCustomerEntity, Long> {}
        """
    }
    services = _generate_services_from_payload(source_units, entities, repositories)
    code = services["NewCustomerService.java"]
    assert "public Long newCustomer(" in code
    assert "findAll(PageRequest.of(0, size))" not in code
    assert ".setCustomerName(" in code
    assert "return savedXyCustomerEntity.getCustomerId();" in code


def test_direct_select_function_returns_lookup_value():
    source_units = [
        {
            "name": "get_customer_name",
            "object_type": "FUNCTION",
            "raw_plsql": """
                CREATE OR REPLACE FUNCTION get_customer_name(p_customer_id IN NUMBER) RETURN VARCHAR2 IS
                  l_returnvalue xy_customer.customer_name%TYPE;
                BEGIN
                  SELECT customer_name INTO l_returnvalue FROM xy_customer WHERE customer_id = p_customer_id;
                  RETURN l_returnvalue;
                END;
            """,
            "operations_by_table": {"XY_CUSTOMER": ["SELECT"]},
            "driving_table": "XY_CUSTOMER",
            "target_tables": [],
            "lookup_keys": {"XY_CUSTOMER": ["CUSTOMER_ID"]},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [{"name": "p_customer_id", "type": "NUMBER", "direction": "IN"}],
            "semantic_analysis": {},
        }
    ]
    entities = {
        "XyCustomerEntity.java": """
            public class XyCustomerEntity {
                private Long customerId;
                private String customerName;
                public String getCustomerName() { return customerName; }
            }
        """
    }
    repositories = {
        "XyCustomerRepository.java": """
            public interface XyCustomerRepository extends org.springframework.data.jpa.repository.JpaRepository<XyCustomerEntity, Long> {
                java.util.Optional<XyCustomerEntity> findByCustomerId(Long customerId);
            }
        """
    }
    services = _generate_services_from_payload(source_units, entities, repositories)
    code = services["GetCustomerNameService.java"]
    assert "public String getCustomerName(" in code
    assert ".findByCustomerId(customerId)" in code
    assert "return found.map(XyCustomerEntity::getCustomerName).orElse(null);" in code
    assert "findAll(PageRequest.of(0, size))" not in code


def test_direct_select_infers_lookup_keys_when_missing():
    source_units = [
        {
            "name": "get_customer_name",
            "object_type": "FUNCTION",
            "raw_plsql": """
                CREATE OR REPLACE FUNCTION get_customer_name(p_customer_id IN NUMBER) RETURN VARCHAR2 IS
                BEGIN
                  RETURN NULL;
                END;
            """,
            "operations_by_table": {"XY_CUSTOMER": ["SELECT"]},
            "driving_table": "XY_CUSTOMER",
            "target_tables": [],
            "lookup_keys": {},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [{"name": "p_customer_id", "type": "NUMBER", "direction": "IN"}],
            "semantic_analysis": {},
        }
    ]
    entities = {
        "XyCustomerEntity.java": """
            public class XyCustomerEntity {
                private Long customerId;
                private String customerName;
                public String getCustomerName() { return customerName; }
            }
        """
    }
    repositories = {
        "XyCustomerRepository.java": """
            public interface XyCustomerRepository extends org.springframework.data.jpa.repository.JpaRepository<XyCustomerEntity, Long> {
                java.util.Optional<XyCustomerEntity> findByCustomerId(Long customerId);
            }
        """
    }

    services = _generate_services_from_payload(source_units, entities, repositories)
    code = services["GetCustomerNameService.java"]
    assert ".findByCustomerId(customerId)" in code
    assert "return found.map(XyCustomerEntity::getCustomerName).orElse(null);" in code


def test_direct_aggregation_only_skips_findby_in_service():
    source_units = [
        {
            "name": "view_items",
            "object_type": "PROCEDURE",
            "raw_plsql": "SELECT COUNT(*) INTO v_count FROM book WHERE bookid = p_item_id;",
            "operations_by_table": {"BOOK": ["SELECT"]},
            "driving_table": "BOOK",
            "target_tables": [],
            "lookup_keys": {"BOOK": ["BOOKID"]},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [{"name": "p_item_id", "type": "NUMBER", "direction": "IN"}],
            "semantic_analysis": {"aggregation": {"columns": ["book.amount"]}},
        }
    ]
    entities = {
        "BookEntity.java": """
            public class BookEntity {
                private Long bookid;
                private java.math.BigDecimal amount;
            }
        """
    }
    repositories = {
        "BookRepository.java": """
            public interface BookRepository extends org.springframework.data.jpa.repository.JpaRepository<BookEntity, Long> {
                java.math.BigDecimal sumByBookid(Long bookid);
                java.util.Optional<BookEntity> findByBookid(Long bookid);
            }
        """
    }

    services = _generate_services_from_payload(source_units, entities, repositories)
    code = services["ViewItemsService.java"]
    assert "bookRepository.sumByBookid(itemId)" in code
    assert "bookRepository.findByBookid(" not in code


def test_direct_delete_prefers_custom_delete_method():
    source_units = [
        {
            "name": "delete_customer",
            "object_type": "PROCEDURE",
            "raw_plsql": "DELETE FROM xy_customer WHERE customer_id = p_customer_id;",
            "operations_by_table": {"XY_CUSTOMER": ["DELETE"]},
            "driving_table": "XY_CUSTOMER",
            "target_tables": ["XY_CUSTOMER"],
            "lookup_keys": {"XY_CUSTOMER": ["CUSTOMER_ID"]},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [{"name": "p_customer_id", "type": "NUMBER", "direction": "IN"}],
            "semantic_analysis": {},
        }
    ]
    entities = {
        "XyCustomerEntity.java": """
            public class XyCustomerEntity {
                private Long customerId;
            }
        """
    }
    repositories = {
        "XyCustomerRepository.java": """
            public interface XyCustomerRepository extends org.springframework.data.jpa.repository.JpaRepository<XyCustomerEntity, Long> {
                void deleteXyCustomerByCustomerId(Long customerId);
            }
        """
    }
    services = _generate_services_from_payload(source_units, entities, repositories)
    code = services["DeleteCustomerService.java"]
    assert ".deleteXyCustomerByCustomerId(" in code
    assert ".save(" not in code


def test_fallback_repository_prefers_domain_token_match():
    source_units = [
        {
            "name": "create_invoice",
            "object_type": "FUNCTION",
            "raw_plsql": "CREATE OR REPLACE FUNCTION create_invoice RETURN NUMBER IS BEGIN RETURN 1; END;",
            "operations_by_table": {},
            "driving_table": "",
            "target_tables": [],
            "lookup_keys": {},
            "bulk_operations": [],
            "cursor": {},
            "transaction": {},
            "input_parameters": [],
            "semantic_analysis": {},
        }
    ]
    entities = {
        "ApplLogEntity.java": "public class ApplLogEntity {}",
        "XyInvoiceEntity.java": """
            public class XyInvoiceEntity {
                private Long invoiceId;
                public Long getInvoiceId() { return invoiceId; }
            }
        """,
    }
    repositories = {
        "ApplLogRepository.java": """
            public interface ApplLogRepository extends org.springframework.data.jpa.repository.JpaRepository<ApplLogEntity, Long> {}
        """,
        "XyInvoiceRepository.java": """
            public interface XyInvoiceRepository extends org.springframework.data.jpa.repository.JpaRepository<XyInvoiceEntity, Long> {}
        """,
    }
    services = _generate_services_from_payload(source_units, entities, repositories)
    code = services["CreateInvoiceService.java"]
    assert "private final XyInvoiceRepository xyInvoiceRepository;" in code
    assert "private final ApplLogRepository applLogRepository;" not in code
