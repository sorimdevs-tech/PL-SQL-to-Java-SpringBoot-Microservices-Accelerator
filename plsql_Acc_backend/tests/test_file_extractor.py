import asyncio
from pathlib import Path

import git

from src.utils.file_utils import FileExtractor, GitRepoPublisher


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


def test_git_repo_publisher_rejects_target_path_escape():
    publisher = GitRepoPublisher()

    try:
        publisher._normalize_target_subdirectory("../outside")
    except ValueError as exc:
        assert "must stay inside the target repository" in str(exc)
    else:
        raise AssertionError("Expected target path validation to reject traversal")


def test_git_repo_publisher_pushes_generated_output_to_target_repo(tmp_path):
    remote_repo_path = tmp_path / "remote.git"
    git.Repo.init(remote_repo_path, bare=True)

    seed_repo_path = tmp_path / "seed"
    seed_repo_path.mkdir()
    seed_repo = git.Repo.init(seed_repo_path)
    (seed_repo_path / "README.md").write_text("# seed\n", encoding="utf-8")
    seed_repo.git.add(A=True)
    seed_repo.index.commit("Initial commit")
    active_branch = seed_repo.active_branch.name
    seed_repo.create_remote("origin", remote_repo_path.as_posix())
    seed_repo.remotes.origin.push(f"{active_branch}:{active_branch}")

    generated_output = tmp_path / "generated-output"
    generated_output.mkdir()
    (generated_output / "service.txt").write_text("generated", encoding="utf-8")

    publisher = GitRepoPublisher(workspace_root=tmp_path)
    result = asyncio.run(
        publisher.publish_directory(
            source_dir=generated_output,
            repo_url=remote_repo_path.as_posix(),
            branch=active_branch,
            target_subdirectory="generated/app",
            commit_message="Publish generated output",
        )
    )

    assert result["published"] is True
    assert result["branch"] == active_branch
    assert result["target_path"] == "generated/app"

    verification_repo_path = tmp_path / "verification"
    verification_repo = git.Repo.clone_from(remote_repo_path.as_posix(), verification_repo_path.as_posix())
    verification_repo.git.checkout(active_branch)

    published_file = verification_repo_path / Path("generated/app/service.txt")
    assert published_file.read_text(encoding="utf-8") == "generated"
