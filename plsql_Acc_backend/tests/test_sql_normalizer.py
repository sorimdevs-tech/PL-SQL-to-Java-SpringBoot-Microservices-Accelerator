from src.utils.sql_normalizer import SQLNormalizer


def test_normalize_sql_removes_comments_and_case_noise():
    normalizer = SQLNormalizer()

    raw_sql = """
    -- fetch active employees
    CREATE OR REPLACE PROCEDURE test_proc AS
    BEGIN
      /* inline note */
      SELECT  employee_id,  employee_name
      INTO    v_id, v_name
      FROM    employees
      WHERE   status = 'ACTIVE';
    END;
    """

    normalized = normalizer.normalize_sql(raw_sql)

    assert "--" not in normalized
    assert "/*" not in normalized
    assert normalized == normalized.lower()
    assert "select employee_id, employee_name into v_id, v_name from employees where status = 'active';" in normalized


def test_extract_key_patterns_returns_semantic_markers():
    normalizer = SQLNormalizer()

    patterns = normalizer.extract_key_patterns(
        "SELECT * FROM orders FOR UPDATE SKIP LOCKED"
    )

    assert "select" in patterns
    assert "for_update" in patterns
    assert "skip_locked" in patterns
