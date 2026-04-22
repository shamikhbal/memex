# tests/test_phase2_integration.py
"""
Phase 2 integration: session transcript → flush → note → compile → _index.md
LLM calls are mocked — no API costs.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from memex.llm_client import LLMResponse


def test_full_pipeline_transcript_to_index(tmp_memex: Path, sample_jsonl: Path, tmp_path: Path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush
    from scripts.compile import compile_project

    # Flush: LLM extracts one DECISION
    flush_response = LLMResponse(text=json.dumps({
        "items": [{
            "tag": "DECISION",
            "concept": "json parsing approach",
            "content": "Use json.loads() on each JSONL line — no streaming parser needed.",
        }]
    }))

    with patch("scripts.flush.LLMClient") as MockFlushClient:
        MockFlushClient.from_config.return_value.complete.return_value = flush_response
        # Also patch subprocess.Popen so compile.py isn't spawned for real
        with patch("scripts.flush.subprocess.Popen"):
            flush(
                raw_file=sample_jsonl,
                project_id="integration-project",
                memex_dir=tmp_memex,
            )

    decisions = tmp_memex / "notes" / "projects" / "integration-project" / "decisions.md"
    assert decisions.exists(), "flush should have written decisions.md"
    assert "json.loads" in decisions.read_text()

    # Compile: LLM writes _index.md
    compile_response = LLMResponse(text="# integration-project\n\nUses json.loads() for JSONL parsing.\n")

    with patch("scripts.compile.LLMClient") as MockCompileClient, \
         patch("scripts.compile.shutil.which", return_value=None):
        MockCompileClient.from_config.return_value.complete.return_value = compile_response
        compile_project(project_id="integration-project", memex_dir=tmp_memex)

    index = tmp_memex / "notes" / "projects" / "integration-project" / "_index.md"
    assert index.exists(), "compile should have written _index.md"
    assert "json.loads" in index.read_text()
