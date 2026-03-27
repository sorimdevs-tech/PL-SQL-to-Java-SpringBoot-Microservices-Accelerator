import asyncio
from pathlib import Path

from main import PLSQLModernizationPipeline


def _build_pipeline(tmp_path: Path) -> PLSQLModernizationPipeline:
    config_path = Path(__file__).resolve().parents[1] / "config.json"
    return PLSQLModernizationPipeline(
        config_path=str(config_path),
        output_directory=str(tmp_path),
    )


def test_run_generated_project_build_marks_skipped_when_no_tool(monkeypatch, tmp_path):
    (tmp_path / "build.gradle").write_text("plugins {}", encoding="utf-8")
    pipeline = _build_pipeline(tmp_path)
    monkeypatch.setattr("main.shutil.which", lambda _name: None)

    result = asyncio.run(pipeline._run_generated_project_build(tmp_path))

    assert result["success"] is False
    assert result["skipped"] is True
    assert result["skip_reason"] == "no_supported_build_command"
    assert "No supported build command found" in result["combined_output"]


def test_build_pipeline_result_completed_when_build_validation_skipped(tmp_path):
    pipeline = _build_pipeline(tmp_path)
    result = pipeline._build_pipeline_result(
        source_path="https://example.com/repo.git",
        source_type="git",
        plsql_files={},
        ast_results={},
        dependency_graph={},
        project_structure={"java_files": {}},
        entities={},
        repositories={},
        services={},
        controllers={},
        test_results={"validation_passed": True},
        repair_results={"final_build": {"success": False, "skipped": True}, "iterations": []},
    )

    assert result["status"] == "completed"
    assert result["summary"]["build_validation_passed"] is False
    assert result["summary"]["build_validation_skipped"] is True


def test_resolve_build_command_supports_gradle_kts(monkeypatch, tmp_path):
    (tmp_path / "build.gradle.kts").write_text("plugins {}", encoding="utf-8")
    pipeline = _build_pipeline(tmp_path)
    monkeypatch.setattr(
        "main.shutil.which",
        lambda name: "C:/gradle/bin/gradle.bat" if name == "gradle" else None,
    )

    command = pipeline._resolve_build_command(tmp_path)
    assert command == ["C:/gradle/bin/gradle.bat", "compileJava"]
