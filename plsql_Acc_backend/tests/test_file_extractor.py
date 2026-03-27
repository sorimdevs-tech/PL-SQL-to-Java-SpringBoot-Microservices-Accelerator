from pathlib import Path

from src.utils.file_utils import FileExtractor


def test_extract_from_directory_ignores_git_internal_files(tmp_path: Path):
    extractor = FileExtractor()

    sql_file = tmp_path / "schema.sql"
    sql_file.write_text("CREATE OR REPLACE PROCEDURE p_demo IS BEGIN NULL; END;", encoding="utf-8")

    hook_file = tmp_path / ".git" / "hooks" / "pre-commit.sample"
    hook_file.parent.mkdir(parents=True, exist_ok=True)
    hook_file.write_text("#!/bin/sh\nfunction sample() { echo test; }\n", encoding="utf-8")

    extracted = extractor.extract_from_file(str(tmp_path))

    assert "schema.sql" in extracted
    assert ".git/hooks/pre-commit.sample" not in extracted


def test_plsql_detection_does_not_accept_sample_extension(tmp_path: Path):
    extractor = FileExtractor()
    sample_file = tmp_path / "script.sample"
    sample_file.write_text("CREATE OR REPLACE PROCEDURE p_demo IS BEGIN NULL; END;", encoding="utf-8")

    assert extractor._is_plsql_file(sample_file) is False
