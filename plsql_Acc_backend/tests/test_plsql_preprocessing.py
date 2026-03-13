from src.parser.plsql_parser import PLSQLParser, preprocess_plsql_for_parser


def test_preprocess_removes_sqlplus_noise():
    content = """
    REM header comment
    SET ECHO OFF
    PROMPT Installing
    CREATE OR REPLACE PROCEDURE p_demo IS
    BEGIN
      NULL;
    END;
    /
    """
    cleaned = preprocess_plsql_for_parser(content)
    assert "REM" not in cleaned.upper()
    assert "SET ECHO OFF" not in cleaned.upper()
    assert "PROMPT INSTALLING" not in cleaned.upper()
    assert "CREATE OR REPLACE PROCEDURE p_demo" in cleaned


def test_preprocess_normalizes_oracle_specific_tokens():
    content = """
    CREATE OR REPLACE PROCEDURE p_demo(
      p_id employees.employee_id%TYPE
    ) AS
    BEGIN
      INSERT INTO job_history(employee_id) VALUES(:old.employee_id);
    END;
    """
    cleaned = preprocess_plsql_for_parser(content)
    assert "%TYPE" not in cleaned.upper()
    assert ":old.employee_id" not in cleaned
    assert "old_employee_id" in cleaned


def test_fallback_parse_extracts_objects_and_sql():
    parser = PLSQLParser()
    content = """
    CREATE OR REPLACE PROCEDURE secure_dml IS
    BEGIN
      INSERT INTO audit_log(id) VALUES(1);
    END secure_dml;

    CREATE OR REPLACE TRIGGER secure_employees
      BEFORE INSERT OR UPDATE OR DELETE ON employees
    BEGIN
      secure_dml;
    END secure_employees;
    """
    ast = parser._fallback_parse(preprocess_plsql_for_parser(content))
    assert ast is not None
    assert len(ast["procedures"]) == 1
    assert len(ast["triggers"]) == 1
    assert ast["procedures"][0]["name"] == "secure_dml"
    assert ast["procedures"][0]["statements"][0]["type"] == "sql_statement"
