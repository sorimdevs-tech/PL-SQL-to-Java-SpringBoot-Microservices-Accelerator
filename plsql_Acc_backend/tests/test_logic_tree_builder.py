from src.analyzer.logic_tree_builder import build_logic_tree


def test_logic_tree_builder_extracts_sequence_branches_and_feature_flags():
    source = """
    BEGIN
        SELECT COUNT(*) INTO v_count FROM customers WHERE customer_id = p_customer_id;
        v_sql := 'UPDATE customers SET status = ''A'' WHERE customer_id = :id';
        IF v_count > 0 THEN
            EXECUTE IMMEDIATE v_sql USING p_customer_id;
        ELSE
            INSERT INTO audit_log(customer_id) VALUES (p_customer_id);
        END IF;
    EXCEPTION
        WHEN OTHERS THEN
            NULL;
    END;
    """

    tree = build_logic_tree(source)

    assert tree["metrics"]["sequence_length"] >= 3
    assert tree["metrics"]["branch_count"] >= 2
    assert tree["features"]["dynamic_sql"] is True
    assert tree["features"]["exception_block"] is True
    assert any(node["node_type"] == "count_into" for node in tree["sequence"])
    assert any(node["node_type"] == "assignment" for node in tree["sequence"])
    assert any(node["node_type"] == "execute_immediate" for node in tree["sequence"])
    assert tree["branches"]
    assert tree["branches"][0]["node_type"] == "if"
