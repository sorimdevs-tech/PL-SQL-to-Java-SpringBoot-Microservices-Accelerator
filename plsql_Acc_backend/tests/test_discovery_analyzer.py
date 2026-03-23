from src.parser.discovery_analyzer import analyze_sql_source, build_discovery_model


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
