from src.parser.discovery_analyzer import analyze_sql_source, build_discovery_model, build_conversion_units


def test_analyze_sql_source_extracts_metadata():
    sql = """
    CREATE OR REPLACE PROCEDURE process_order(
        p_customer_id IN NUMBER,
        p_status OUT VARCHAR2
    ) AS
        v_total NUMBER;
        e_invalid EXCEPTION;
    BEGIN
        SELECT id INTO v_total FROM customers WHERE customer_id = p_customer_id;
        INSERT INTO orders(customer_id) VALUES (p_customer_id);
        IF v_total > 0 THEN
            UPDATE customers SET status = 'ACTIVE' WHERE customer_id = p_customer_id;
        ELSE
            DELETE FROM products WHERE id = 1;
        END IF;
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            p_status := 'NOT_FOUND';
        WHEN OTHERS THEN
            p_status := 'ERROR';
    END;
    """

    results = analyze_sql_source(sql)
    assert len(results) == 1
    item = results[0]
    assert item["procedureName"] == "process_order"
    assert item["objectType"] == "PROCEDURE"
    assert item["parameters"]["in"] == [{"name": "p_customer_id", "type": "NUMBER"}]
    assert item["parameters"]["out"] == [{"name": "p_status", "type": "VARCHAR2"}]
    assert "CUSTOMERS" in item["tablesUsed"]
    assert "ORDERS" in item["tablesUsed"]
    assert set(item["operations"]) == {"SELECT", "INSERT", "UPDATE", "DELETE"}
    assert "NO_DATA_FOUND" in item["exceptions"]
    assert "OTHERS" in item["exceptions"]
    assert item["complexity"]["numberOfQueries"] >= 4
    assert item["conversionPreview"]["services"] == ["ProcessOrderService"]


def test_build_discovery_model_infers_schema_from_procedure_dml():
    sql = """
    CREATE OR REPLACE PROCEDURE process_batch IS
        v_order_id NUMBER;
        v_amount NUMBER;
    BEGIN
        SELECT o.order_id, o.amount
        INTO v_order_id, v_amount
        FROM orders o
        WHERE o.order_id = 1;

        INSERT INTO payments (order_id, amount)
        VALUES (v_order_id, v_amount);

        UPDATE error_log
        SET status = 'FAILED'
        WHERE order_id = v_order_id;

        DELETE FROM order_audit_log
        WHERE order_id = v_order_id;
    END;
    /
    """

    model = build_discovery_model(sql)
    schema_tables = {table["name"]: table for table in model["schema"]["tables"]}

    assert {"ORDERS", "PAYMENTS", "ERROR_LOG", "ORDER_AUDIT_LOG"}.issubset(schema_tables)
    assert schema_tables["ORDERS"]["source"] == "inferred_from_procedure"
    assert {column["name"] for column in schema_tables["ORDERS"]["columns"]} == {"ORDER_ID", "AMOUNT"}


def test_build_conversion_units_preserves_raw_body_and_filters_merge_keywords():
    sql = """
    CREATE OR REPLACE PROCEDURE reconcile_customer_balances(
        p_batch_size IN NUMBER,
        p_run_mode   IN VARCHAR2
    ) AS
    BEGIN
        MERGE INTO customer_balance cb
        USING dual
        ON (cb.customer_id = 1)
        WHEN MATCHED THEN
            UPDATE SET balance = 10
        WHEN NOT MATCHED THEN
            INSERT (balance_id, customer_id, balance)
            VALUES (1, 1, 10);

        SELECT customer_id
        INTO p_batch_size
        FROM customers
        FOR UPDATE SKIP LOCKED;
    END;
    """

    units = build_conversion_units(sql)

    assert len(units) == 1
    unit = units[0]
    assert "MERGE INTO customer_balance" in unit["raw_plsql"]
    assert "FOR UPDATE SKIP LOCKED" in unit["raw_plsql"]
    assert "CUSTOMER_BALANCE" in unit["operations_by_table"]
    assert "MERGE" in unit["operations_by_table"]["CUSTOMER_BALANCE"]
    assert "SET" not in unit["operations_by_table"]
    assert "SKIP" not in unit["operations_by_table"]
    assert "LOCKED" not in unit["operations_by_table"]


def test_build_conversion_units_extracts_lookup_keys_from_predicates():
    sql = """
    CREATE OR REPLACE PROCEDURE reconcile_customer_balances(
        p_customer_id IN NUMBER
    ) AS
        v_total NUMBER;
    BEGIN
        SELECT NVL(SUM(o.amount), 0)
        INTO v_total
        FROM orders o
        WHERE o.customer_id = p_customer_id;

        UPDATE customer_balance
        SET balance = v_total,
            updated_at = SYSDATE
        WHERE customer_id = p_customer_id;

        MERGE INTO balance_audit_log bal
        USING dual
        ON (bal.customer_id = p_customer_id AND bal.audit_id = 1)
        WHEN MATCHED THEN
            UPDATE SET action_date = SYSDATE
        WHEN NOT MATCHED THEN
            INSERT (audit_id, customer_id, action_date)
            VALUES (1, p_customer_id, SYSDATE);
    END;
    """

    units = build_conversion_units(sql)

    assert len(units) == 1
    lookup_keys = units[0]["lookup_keys"]
    assert lookup_keys["ORDERS"] == ["CUSTOMER_ID"]
    assert lookup_keys["CUSTOMER_BALANCE"] == ["CUSTOMER_ID"]
    assert lookup_keys["BALANCE_AUDIT_LOG"] == ["AUDIT_ID", "CUSTOMER_ID"]
    assert "BALANCE" not in lookup_keys["CUSTOMER_BALANCE"]
    assert "UPDATED_AT" not in lookup_keys["CUSTOMER_BALANCE"]


def test_build_conversion_units_ignores_markdown_fences():
    sql = """
    CREATE OR REPLACE PROCEDURE fenced_demo IS
    ```
    BEGIN
        UPDATE accounts
        SET status = 'REVIEW'
        WHERE account_id = 1;
    END;
    ```
    """

    units = build_conversion_units(sql)
    assert len(units) == 1
    unit = units[0]
    assert "```" not in unit["raw_plsql"]
    assert "ACCOUNTS" in unit["operations_by_table"]
    assert "UPDATE" in unit["operations_by_table"]["ACCOUNTS"]


def test_analyze_sql_source_adds_semantic_analysis_for_reconciliation_flow():
    sql = """
    CREATE OR REPLACE PROCEDURE reconcile_customer_balances (
        p_batch_size     IN NUMBER DEFAULT 100,
        p_run_mode       IN VARCHAR2 DEFAULT 'FULL'
    )
    IS
        CURSOR cust_cursor IS
            SELECT customer_id
            FROM customers
            WHERE status = 'ACTIVE'
            FOR UPDATE SKIP LOCKED;

        TYPE cust_table IS TABLE OF cust_cursor%ROWTYPE;
        v_customers cust_table;

        v_total_orders   NUMBER;
        v_total_payments NUMBER;
        v_balance        NUMBER;
        v_limit          NUMBER := p_batch_size;

        v_has_error      BOOLEAN := FALSE;

        e_balance_error EXCEPTION;

    BEGIN
        OPEN cust_cursor;

        LOOP
            FETCH cust_cursor BULK COLLECT INTO v_customers LIMIT v_limit;
            EXIT WHEN v_customers.COUNT = 0;

            SAVEPOINT batch_start;

            FOR i IN 1 .. v_customers.COUNT LOOP
                SELECT NVL(SUM(o.amount), 0)
                INTO v_total_orders
                FROM orders o
                WHERE o.customer_id = v_customers(i).customer_id;

                SELECT NVL(SUM(p.amount), 0)
                INTO v_total_payments
                FROM payments p
                WHERE p.customer_id = v_customers(i).customer_id;

                v_balance := v_total_orders - v_total_payments;

                IF v_balance < 0 THEN
                    RAISE e_balance_error;
                END IF;

                MERGE INTO customer_balance cb
                USING dual
                ON (cb.customer_id = v_customers(i).customer_id)
                WHEN MATCHED THEN
                    UPDATE SET balance = v_balance,
                               updated_at = SYSDATE
                WHEN NOT MATCHED THEN
                    INSERT (balance_id, customer_id, balance, created_at)
                    VALUES (balance_seq.NEXTVAL,
                            v_customers(i).customer_id,
                            v_balance,
                            SYSDATE);

            END LOOP;

            IF p_run_mode = 'FULL' AND NOT v_has_error THEN
                COMMIT;
            ELSE
                ROLLBACK TO batch_start;
            END IF;

        END LOOP;

        CLOSE cust_cursor;

    EXCEPTION
        WHEN e_balance_error THEN
            NULL;
        WHEN OTHERS THEN
            NULL;
    END reconcile_customer_balances;
    /
    """

    results = analyze_sql_source(sql)
    assert len(results) == 1
    item = results[0]
    semantic = item["semantic_analysis"]

    assert semantic["upsert_operations"] == [
        {
            "table": "CUSTOMER_BALANCE",
            "operation": "UPSERT",
            "type": "upsert_operation",
            "details": ["INSERT", "UPDATE"],
        }
    ]
    assert semantic["aggregation"]["type"] == "aggregation"
    assert semantic["aggregation"]["functions"] == ["SUM"]
    assert "orders.amount" in semantic["aggregation"]["columns"]
    assert "payments.amount" in semantic["aggregation"]["columns"]

    assert any(
        entry["variable"] == "v_balance"
        and entry["type"] == "derived_value"
        and entry["formula"] == "v_total_orders - v_total_payments"
        and entry["semantic_type"] == "financial_calculation"
        for entry in semantic["derived_values"]
    )
    assert any(
        flow["target"] == "v_total_orders"
        and flow["source"] == "orders.amount"
        and flow["operation"] == "SUM"
        for flow in semantic["structured_data_flow"]
    )
    assert any(
        flow["target"] == "v_total_payments"
        and flow["source"] == "payments.amount"
        and flow["operation"] == "SUM"
        for flow in semantic["structured_data_flow"]
    )
    assert any(
        flow["target"] == "v_balance"
        and flow["source"] == ["v_total_orders", "v_total_payments"]
        and flow["operation"] == "subtraction"
        for flow in semantic["structured_data_flow"]
    )
    assert any(
        rule["type"] == "validation_rule"
        and rule["condition"] == "v_balance < 0"
        and rule["action"] == "RAISE e_balance_error"
        for rule in semantic["business_rules"]
    )
    assert semantic["transaction_strategy"] == {
        "type": "conditional_transaction",
        "strategy": "commit_or_rollback",
        "condition": "p_run_mode = 'FULL' AND NOT v_has_error",
    }
    assert semantic["cursor_semantics"] == {
        "type": "concurrent_processing",
        "strategy": "skip_locked_rows",
        "purpose": "parallel_safe_batch_execution",
    }
    assert {"type": "business_exception", "name": "e_balance_error"} in semantic["error_handling_semantics"]
    assert {"type": "system_exception", "name": "OTHERS"} in semantic["error_handling_semantics"]
    assert semantic["process_classification"] == {
        "process_type": "batch_reconciliation",
        "domain": "financial_processing",
    }
    assert item["complexity"]["classification"] == "high_complexity_batch_processing"
    assert (
        semantic["intent_summary"]
        == "This procedure performs financial reconciliation using aggregated order and payment data, applies validation rules, performs upsert operations, and uses conditional transaction management with concurrency-safe batch processing."
    )


def test_analyze_sql_source_distinguishes_package_body_from_package_spec():
    sql = """
    CREATE OR REPLACE PACKAGE emp_pkg AS
        PROCEDURE add_employee;
    END emp_pkg;
    /
    CREATE OR REPLACE PACKAGE BODY emp_pkg AS
        PROCEDURE add_employee IS
        BEGIN
            INSERT INTO employees (emp_id) VALUES (1);
        END;
    END emp_pkg;
    /
    """

    results = analyze_sql_source(sql)

    assert len(results) == 2
    object_types = {item["objectType"] for item in results}
    assert object_types == {"PACKAGE", "PACKAGE BODY"}

    body = next(item for item in results if item["objectType"] == "PACKAGE BODY")
    assert "EMPLOYEES" in body["tablesUsed"]
    assert "INSERT" in body["operations"]
    assert body["conversionPreview"]["entities"] == ["Employees"]
