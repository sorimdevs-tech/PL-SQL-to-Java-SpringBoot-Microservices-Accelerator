from src.parser.sql_table_discovery import extract_create_table_names


def test_extract_plain_create_table():
    sql = "CREATE TABLE account_master (id NUMBER);"
    assert extract_create_table_names(sql) == ["ACCOUNT_MASTER"]


def test_extract_quoted_create_table():
    sql = 'CREATE TABLE "gl_transaction" (id NUMBER);'
    assert extract_create_table_names(sql) == ["GL_TRANSACTION"]


def test_extract_schema_qualified_table():
    sql = "CREATE TABLE finance.audit_log (id NUMBER);"
    assert extract_create_table_names(sql) == ["AUDIT_LOG"]


def test_extract_comments_and_multiline_sql():
    sql = """
    -- CREATE TABLE ignored_comment (id NUMBER);
    /*
      CREATE TABLE ignored_block (id NUMBER);
    */
    CREATE TABLE
      reporting_monthly
    (
      id NUMBER
    );
    """
    assert extract_create_table_names(sql) == ["REPORTING_MONTHLY"]


def test_extract_duplicate_tables_deduplicates_and_sorts():
    sql = """
    CREATE TABLE gl_transaction (id NUMBER);
    create table GL_TRANSACTION (id NUMBER);
    CREATE TABLE account_master (id NUMBER);
    """
    assert extract_create_table_names(sql) == ["ACCOUNT_MASTER", "GL_TRANSACTION"]
