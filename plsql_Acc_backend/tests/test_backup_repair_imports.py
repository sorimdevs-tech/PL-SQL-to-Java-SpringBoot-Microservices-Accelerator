from pathlib import Path

from main import PLSQLModernizationPipeline
from src.converter.llm_engine import LLMConversionEngine


def _build_pipeline(tmp_path: Path) -> PLSQLModernizationPipeline:
    config_path = Path(__file__).resolve().parents[1] / "config.json"
    return PLSQLModernizationPipeline(
        config_path=str(config_path),
        output_directory=str(tmp_path),
    )


def _build_engine() -> LLMConversionEngine:
    return LLMConversionEngine(
        {
            "provider": "openrouter",
            "model": "openai/gpt-4o-mini",
            "api_key": "test-key",
            "base_url": "https://openrouter.ai/api/v1",
            "timeout": 30,
            "retry_attempts": 1,
            "batch_size": 1,
            "backup_llm": {
                "enabled": True,
                "provider": "openrouter",
                "model": "openai/gpt-4o-mini",
                "api_key": "test-key",
                "base_url": "https://openrouter.ai/api/v1",
            },
        }
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


def test_apply_repair_files_adds_transaction_template_import_into_existing_service_import_block(tmp_path):
    pipeline = _build_pipeline(tmp_path)
    project_root = tmp_path / "project"
    rel_path = "src/main/java/com/example/demo/service/BatchService.java"
    content = """package com.example.demo.service;

import org.springframework.stereotype.Service;

@Service
public class BatchService {
    private final TransactionTemplate batchTransactionTemplate;

    public BatchService() {
        this.batchTransactionTemplate = null;
    }
}
"""

    changed = pipeline._apply_repair_files(
        project_root,
        [{"path": rel_path, "content": content}],
    )
    assert changed == [rel_path]
    written = (project_root / rel_path).read_text(encoding="utf-8")
    assert "import org.springframework.transaction.support.TransactionTemplate;" in written
    assert written.index("import org.springframework.stereotype.Service;") < written.index(
        "import org.springframework.transaction.support.TransactionTemplate;"
    )


def test_apply_repair_files_creates_service_import_block_for_transaction_types_when_missing(tmp_path):
    pipeline = _build_pipeline(tmp_path)
    project_root = tmp_path / "project"
    rel_path = "src/main/java/com/example/demo/service/BatchService.java"
    content = """package com.example.demo.service;

public class BatchService {
    private final TransactionTemplate batchTransactionTemplate;

    public BatchService(PlatformTransactionManager transactionManager) {
        this.batchTransactionTemplate = new TransactionTemplate(transactionManager);
    }
}
"""

    pipeline._apply_repair_files(
        project_root,
        [{"path": rel_path, "content": content}],
    )
    written = (project_root / rel_path).read_text(encoding="utf-8")
    assert "import org.springframework.transaction.PlatformTransactionManager;" in written
    assert "import org.springframework.transaction.support.TransactionTemplate;" in written
    assert written.index("package com.example.demo.service;") < written.index(
        "import org.springframework.transaction.PlatformTransactionManager;"
    )
    assert written.index("package com.example.demo.service;") < written.index(
        "import org.springframework.transaction.support.TransactionTemplate;"
    )
    assert written.index("public class BatchService") > written.index(
        "import org.springframework.transaction.support.TransactionTemplate;"
    )


def test_repair_prompt_includes_transaction_template_import_rule():
    engine = _build_engine()
    prompt = engine._build_repair_prompt({"build_output": "", "failing_files": []})
    assert "if TransactionTemplate appears" in prompt
    assert "import org.springframework.transaction.support.TransactionTemplate;" in prompt
