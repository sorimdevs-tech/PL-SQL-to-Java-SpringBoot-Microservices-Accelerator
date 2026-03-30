from src.utils.file_utils import FileExtractor


def test_extract_directory_preserves_same_basename_files_with_relative_paths(tmp_path):
    extractor = FileExtractor()
    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"
    a_dir.mkdir(parents=True, exist_ok=True)
    b_dir.mkdir(parents=True, exist_ok=True)

    (a_dir / "customer.pks").write_text(
        "create or replace package customer_pkg as procedure run; end customer_pkg;",
        encoding="utf-8",
    )
    (b_dir / "customer.pks").write_text(
        "create or replace package body customer_pkg as procedure run is begin null; end; end customer_pkg;",
        encoding="utf-8",
    )

    extracted = extractor.extract_from_file(str(tmp_path))

    assert "a/customer.pks" in extracted
    assert "b/customer.pks" in extracted
    assert len(extracted) == 2


def test_extract_directory_skips_non_plsql_unknown_extension_files(tmp_path):
    extractor = FileExtractor()
    (tmp_path / "hook.sample").write_text(
        "#!/bin/sh\n# git hook\nif [ -n \"$1\" ]; then\necho \"ok\"\nfi\n",
        encoding="utf-8",
    )
    (tmp_path / "real_logic.pkb").write_text(
        "create or replace package body appl_log_pkg as procedure log_it is begin null; end; end appl_log_pkg;",
        encoding="utf-8",
    )

    extracted = extractor.extract_from_file(str(tmp_path))

    assert "real_logic.pkb" in extracted
    assert "hook.sample" not in extracted


def test_extract_directory_accepts_unknown_extension_when_plsql_signature_present(tmp_path):
    extractor = FileExtractor()
    (tmp_path / "logic.txt").write_text(
        "create or replace procedure do_work is begin null; end;",
        encoding="utf-8",
    )

    extracted = extractor.extract_from_file(str(tmp_path))

    assert "logic.txt" in extracted
