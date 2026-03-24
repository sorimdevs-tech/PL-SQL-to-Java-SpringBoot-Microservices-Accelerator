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
