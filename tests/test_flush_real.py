# tests/test_flush_real.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from memex.llm_client import LLMResponse
from memex.scripts.flush import _extract_json


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


def test_flush_writes_explore_to_project(tmp_memex: Path, tmp_path: Path):
    """EXPLORE items route to project explore- files."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush

    raw_file = tmp_path / "20260423T120000Z.md"
    raw_file.write_text("**User:** What if we used GraphQL?\n**Assistant:** That's an interesting idea.")

    mock_response = make_llm_response([{
        "tag": "EXPLORE",
        "concept": "graphql migration",
        "content": "Explored switching from REST to GraphQL for the API layer.",
        "related": ["rest-api"],
        "tags": ["tech/graphql"],
    }])

    with patch("scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    explore_note = tmp_memex / "notes" / "projects" / "test-project" / "explore-graphql-migration.md"
    assert explore_note.exists()
    assert "type/exploration" in explore_note.read_text()


def test_flush_passes_target_project(tmp_memex: Path, tmp_path: Path):
    """Items with target_project get routed to the matching project."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush

    (tmp_memex / "notes" / "projects" / "memex").mkdir(parents=True, exist_ok=True)

    raw_file = tmp_path / "20260423T120000Z.md"
    raw_file.write_text("**User:** For memex, let's use sqlite.\n**Assistant:** Good choice.")

    mock_response = make_llm_response([{
        "tag": "DECISION",
        "concept": "storage-engine",
        "content": "Chose sqlite for memex queue storage.",
        "target_project": "memex",
    }])

    with patch("scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="", memex_dir=tmp_memex)

    dest = tmp_memex / "notes" / "projects" / "memex" / "decisions.md"
    assert dest.exists()
    assert "sqlite" in dest.read_text()


def test_flush_clears_status_override_on_new_notes(tmp_memex: Path, tmp_path: Path):
    """When flush writes new items, any status override is cleared."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush
    from memex.state import ProjectState

    state = ProjectState(state_dir=tmp_memex / "state", project_id="test-project")
    state.set_override("completed")
    state.save()

    raw_file = tmp_path / "20260423T120000Z.md"
    raw_file.write_text("**User:** Let's change the config format.\n**Assistant:** Good idea.")

    mock_response = make_llm_response([{
        "tag": "DECISION",
        "concept": "config-format",
        "content": "Switched from INI to YAML for config.",
    }])

    with patch("scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    reloaded = ProjectState(state_dir=tmp_memex / "state", project_id="test-project")
    assert reloaded.status_override is None


def test_extract_json_plain():
    """Plain JSON passes through unchanged."""
    raw = '{"items": []}'
    assert _extract_json(raw) == '{"items": []}'


def test_extract_json_strips_fences():
    """JSON wrapped in ```json fences is extracted correctly."""
    raw = '```json\n{"items": []}\n```'
    result = _extract_json(raw)
    import json
    assert json.loads(result) == {"items": []}


def test_extract_json_strips_plain_fences():
    """JSON wrapped in plain ``` fences is extracted correctly."""
    raw = '```\n{"items": [{"tag": "SKIP"}]}\n```'
    result = _extract_json(raw)
    import json
    assert json.loads(result) == {"items": [{"tag": "SKIP"}]}


def test_extract_json_strips_prose():
    """JSON preceded by prose is extracted from the first { to last }."""
    raw = 'Here is the JSON output:\n{"items": []}\nHope that helps!'
    result = _extract_json(raw)
    import json
    assert json.loads(result) == {"items": []}


def test_extract_json_empty_returns_empty():
    """Empty string returns empty string (json.loads will raise, caught upstream)."""
    assert _extract_json("") == ""


def test_extract_json_no_braces_returns_original():
    """Text with no braces returns the stripped text (json.loads will raise upstream)."""
    result = _extract_json("not json at all")
    assert result == "not json at all"
