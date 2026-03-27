from pathlib import Path

from main import PLSQLModernizationPipeline


def _build_pipeline(tmp_path: Path) -> PLSQLModernizationPipeline:
    config_path = Path(__file__).resolve().parents[1] / "config.json"
    return PLSQLModernizationPipeline(
        config_path=str(config_path),
        output_directory=str(tmp_path),
    )


def test_apply_repair_files_adds_optional_import_into_existing_service_import_block(tmp_path):
    pipeline = _build_pipeline(tmp_path)
    project_root = tmp_path / "project"
    rel_path = "src/main/java/com/example/demo/service/LoginService.java"
    content = """package com.example.demo.service;

import org.springframework.stereotype.Service;

@Service
public class LoginService {
    public void login() {
        Optional<String> value = Optional.empty();
    }
}
"""

    changed = pipeline._apply_repair_files(
        project_root,
        [{"path": rel_path, "content": content}],
    )
    assert changed == [rel_path]
    written = (project_root / rel_path).read_text(encoding="utf-8")
    assert "import java.util.Optional;" in written
    assert written.index("import org.springframework.stereotype.Service;") < written.index("import java.util.Optional;")


def test_apply_repair_files_creates_service_import_block_for_optional_when_missing(tmp_path):
    pipeline = _build_pipeline(tmp_path)
    project_root = tmp_path / "project"
    rel_path = "src/main/java/com/example/demo/service/ReportService.java"
    content = """package com.example.demo.service;

public class ReportService {
    public void build() {
        Optional<Long> id = Optional.of(1L);
    }
}
"""

    pipeline._apply_repair_files(
        project_root,
        [{"path": rel_path, "content": content}],
    )
    written = (project_root / rel_path).read_text(encoding="utf-8")
    assert "import java.util.Optional;" in written
    assert written.index("package com.example.demo.service;") < written.index("import java.util.Optional;")
    assert written.index("import java.util.Optional;") < written.index("public class ReportService")

