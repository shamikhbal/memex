# tests/test_flush_real.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from memex.llm_client import LLMResponse


def make_llm_response(items: list) -> LLMResponse:
    return LLMResponse(text=json.dumps({"items": items}))


def test_flush_writes_decision_to_notes(tmp_memex: Path, tmp_path: Path):
    """flush() extracts a DECISION and writes it to the project decisions.md."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush

    raw_content = "**User:** Should we use sqlite or jsonl?\n**Assistant:** Use jsonl for simplicity."
    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text(raw_content)

    mock_response = make_llm_response([{
        "tag": "DECISION",
        "concept": "queue storage format",
        "content": "Chose jsonl over sqlite for simplicity — no schema needed.",
    }])

    with patch("scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(
            raw_file=raw_file,
            project_id="test-project",
            memex_dir=tmp_memex,
        )

    decisions = tmp_memex / "notes" / "projects" / "test-project" / "decisions.md"
    assert decisions.exists()
    assert "jsonl over sqlite" in decisions.read_text()


def test_flush_writes_pattern_to_concepts(tmp_memex: Path, tmp_path: Path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush

    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text("**User:** How do I spawn detached?\n**Assistant:** Use start_new_session=True.")

    mock_response = make_llm_response([{
        "tag": "PATTERN",
        "concept": "detached subprocess",
        "content": "Set start_new_session=True in Popen to fully detach the child process.",
    }])

    with patch("scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    concept_note = tmp_memex / "notes" / "concepts" / "detached-subprocess.md"
    assert concept_note.exists()
    assert "start_new_session" in concept_note.read_text()


def test_flush_skips_empty_items(tmp_memex: Path, tmp_path: Path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush

    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text("**User:** hi\n**Assistant:** hello")

    mock_response = make_llm_response([])

    with patch("scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    assert not list((tmp_memex / "notes").rglob("*.md"))


def test_flush_handles_malformed_llm_response(tmp_memex: Path, tmp_path: Path):
    """If LLM returns non-JSON, flush logs and exits gracefully — no crash."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush

    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text("**User:** something\n**Assistant:** something else")

    with patch("scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = LLMResponse(text="not json at all")
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    # No crash, no notes written
    assert not list((tmp_memex / "notes").rglob("*.md"))
