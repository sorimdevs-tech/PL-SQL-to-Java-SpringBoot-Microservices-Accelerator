"""Small Pinecone smoke test for the learned error-solution store."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag_engine.cloud_vector_store import CloudVectorStore
from src.rag_engine.error_solution_store import ErrorSolutionStore
from src.utils.config import load_config


def main() -> None:
    project_root = PROJECT_ROOT
    load_dotenv(project_root / ".env", override=False)

    config = load_config(str(project_root / "config.json"))
    config_dict = config.model_dump() if hasattr(config, "model_dump") else config.dict()
    vector_cfg = config_dict.get("vector_db", {})

    store = ErrorSolutionStore(
        vector_store=CloudVectorStore(vector_cfg),
        config=vector_cfg,
    )

    result = store.store_error_solution(
        error_message="manual smoke test cannot find symbol DemoRepository",
        sql_context="SELECT * FROM demo_table WHERE status = 'A'",
        error_type="compilation",
        solution={
            "summary": "Manual smoke test record for Pinecone connectivity.",
            "steps": ["Insert a test record into the learned error store."],
            "changed_files": ["src/main/java/com/company/project/service/DemoService.java"],
        },
        metadata={
            "category": "dependency",
            "code": "cannot find symbol",
            "file": "DemoService.java",
            "line": 1,
            "build_tool": "manual-test",
        },
    )
    matches = store.retrieve_similar_errors(
        error_message="cannot find symbol DemoRepository",
        sql_context="SELECT * FROM demo_table WHERE status = 'A'",
        top_k=3,
        error_type="compilation",
    )

    payload = {
        "store_result": result,
        "matches_found": len(matches),
        "top_match": matches[0] if matches else None,
        "namespace": vector_cfg.get("namespace", "plsql-modernization"),
        "index_name": vector_cfg.get("index_name"),
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
    