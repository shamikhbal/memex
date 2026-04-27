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
    from memex.scripts.flush import flush

    raw_content = "**User:** Should we use sqlite or jsonl?\n**Assistant:** Use jsonl for simplicity."
    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text(raw_content)

    mock_response = make_llm_response([{
        "tag": "DECISION",
        "concept": "queue storage format",
        "content": "Chose jsonl over sqlite for simplicity — no schema needed.",
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
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
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text("**User:** How do I spawn detached?\n**Assistant:** Use start_new_session=True.")

    mock_response = make_llm_response([{
        "tag": "PATTERN",
        "concept": "detached subprocess",
        "content": "Set start_new_session=True in Popen to fully detach the child process.",
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    concept_note = tmp_memex / "notes" / "concepts" / "detached-subprocess.md"
    assert concept_note.exists()
    assert "start_new_session" in concept_note.read_text()


def test_flush_skips_empty_items(tmp_memex: Path, tmp_path: Path):
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text("**User:** hi\n**Assistant:** hello")

    mock_response = make_llm_response([])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    assert not list((tmp_memex / "notes").rglob("*.md"))


def test_flush_handles_malformed_llm_response(tmp_memex: Path, tmp_path: Path):
    """If LLM returns non-JSON, flush logs and exits gracefully — no crash."""
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text("**User:** something\n**Assistant:** something else")

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = LLMResponse(text="not json at all")
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    # No crash, no notes written
    assert not list((tmp_memex / "notes").rglob("*.md"))


def test_flush_writes_explore_to_project(tmp_memex: Path, tmp_path: Path):
    """EXPLORE items route to project explore- files."""
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260423T120000Z.md"
    raw_file.write_text("**User:** What if we used GraphQL?\n**Assistant:** That's an interesting idea.")

    mock_response = make_llm_response([{
        "tag": "EXPLORE",
        "concept": "graphql migration",
        "content": "Explored switching from REST to GraphQL for the API layer.",
        "related": ["rest-api"],
        "tags": ["tech/graphql"],
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    explore_note = tmp_memex / "notes" / "projects" / "test-project" / "explore-graphql-migration.md"
    assert explore_note.exists()
    assert "type/exploration" in explore_note.read_text()


def test_flush_passes_target_project(tmp_memex: Path, tmp_path: Path):
    """Items with target_project get routed to the matching project."""
    from memex.scripts.flush import flush

    (tmp_memex / "notes" / "projects" / "memex").mkdir(parents=True, exist_ok=True)

    raw_file = tmp_path / "20260423T120000Z.md"
    raw_file.write_text("**User:** For memex, let's use sqlite.\n**Assistant:** Good choice.")

    mock_response = make_llm_response([{
        "tag": "DECISION",
        "concept": "storage-engine",
        "content": "Chose sqlite for memex queue storage.",
        "target_project": "memex",
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="", memex_dir=tmp_memex)

    dest = tmp_memex / "notes" / "projects" / "memex" / "decisions.md"
    assert dest.exists()
    assert "sqlite" in dest.read_text()


def test_flush_clears_status_override_on_new_notes(tmp_memex: Path, tmp_path: Path):
    """When flush writes new items, any status override is cleared."""
    from memex.scripts.flush import flush
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

    with patch("memex.scripts.flush.LLMClient") as MockClient:
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


def test_extract_json_none_returns_empty():
    """None input returns empty string instead of crashing."""
    assert _extract_json(None) == ""


def test_flush_handles_none_response(tmp_memex: Path, tmp_path: Path):
    """If LLM returns None content, flush logs and exits gracefully — no crash."""
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text("**User:** something\n**Assistant:** something else")

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = LLMResponse(text=None)
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    # No crash, no notes written
    assert not list((tmp_memex / "notes").rglob("*.md"))


def test_flush_handles_empty_response(tmp_memex: Path, tmp_path: Path):
    """If LLM returns empty string, flush logs and exits gracefully."""
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text("**User:** something\n**Assistant:** something else")

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = LLMResponse(text="")
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    assert not list((tmp_memex / "notes").rglob("*.md"))


def test_flush_handles_llm_request_failure(tmp_memex: Path, tmp_path: Path):
    """If the LLM request itself fails, flush logs and exits gracefully."""
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text("**User:** something\n**Assistant:** something else")

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.side_effect = ConnectionError("ollama down")
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    assert not list((tmp_memex / "notes").rglob("*.md"))


def test_flush_writes_summary_to_daily_notes(tmp_memex: Path, tmp_path: Path):
    """SUMMARY items from the LLM are written to daily notes."""
    from datetime import date
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260424T120000Z.md"
    raw_file.write_text("**User:** How's the weather?\n**Assistant:** It's sunny and warm.")

    mock_response = make_llm_response([{
        "tag": "SUMMARY",
        "concept": "casual chat",
        "content": "Brief chat about the weather — sunny and warm.",
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id=None, memex_dir=tmp_memex)

    daily = tmp_memex / "notes" / "daily" / f"{date.today().isoformat()}.md"
    assert daily.exists()
    text = daily.read_text()
    assert "type/daily" in text
    assert "sunny and warm" in text


def test_flush_summary_prevents_empty_daily_note(tmp_memex: Path, tmp_path: Path):
    """When the LLM returns at least one SUMMARY item, a daily note IS created."""
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260424T120000Z.md"
    raw_file.write_text("**User:** hi\n**Assistant:** hello")

    mock_response = make_llm_response([{
        "tag": "SUMMARY",
        "concept": "greeting",
        "content": "Casual greeting exchange.",
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id=None, memex_dir=tmp_memex)

    daily_files = list((tmp_memex / "notes" / "daily").glob("*.md"))
    assert len(daily_files) == 1


def test_flush_skip_items_still_discarded(tmp_memex: Path, tmp_path: Path):
    """SKIP items are still discarded for backward compatibility."""
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260424T120000Z.md"
    raw_file.write_text("**User:** hi\n**Assistant:** hello")

    mock_response = make_llm_response([{
        "tag": "SKIP",
        "concept": "greeting",
        "content": "Nothing worth keeping.",
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    assert not list((tmp_memex / "notes").rglob("*.md"))


# ── REMINDER ─────────────────────────────────────────────────────────────────


def test_flush_writes_reminder_to_project_reminders(tmp_memex: Path, tmp_path: Path):
    """flush() extracts a REMINDER and writes it to project reminders.md."""
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260425T120000Z.md"
    raw_file.write_text(
        "**User:** We need to check the deployment after Friday's release.\n"
        "**Assistant:** I'll remind you — that's by April 28th."
    )

    mock_response = make_llm_response([{
        "tag": "REMINDER",
        "concept": "deploy verification",
        "content": "Check production deployment is healthy after Friday release.",
        "deadline": "2026-04-28",
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    reminders = tmp_memex / "notes" / "projects" / "test-project" / "reminders.md"
    assert reminders.exists()
    text = reminders.read_text()
    assert "type/reminder-log" in text
    assert "deploy" in text.lower()
    assert "[deadline:: 2026-04-28]" in text


def test_flush_writes_reminder_without_deadline(tmp_memex: Path, tmp_path: Path):
    """REMINDER without deadline field still works."""
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260425T120000Z.md"
    raw_file.write_text(
        "**User:** Don't let me forget to research WebSocket alternatives.\n"
        "**Assistant:** Noted."
    )

    mock_response = make_llm_response([{
        "tag": "REMINDER",
        "concept": "websocket research",
        "content": "Research WebSocket alternatives for real-time chat feature.",
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    reminders = tmp_memex / "notes" / "projects" / "test-project" / "reminders.md"
    assert reminders.exists()
    assert "WebSocket" in reminders.read_text()


def test_flush_writes_reminder_without_project_to_global(tmp_memex: Path, tmp_path: Path):
    """REMINDER without project_id writes to global reminders.md."""
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260425T120000Z.md"
    raw_file.write_text("**User:** I need to renew the SSL cert.\n**Assistant:** Noted for May 1st.")

    mock_response = make_llm_response([{
        "tag": "REMINDER",
        "concept": "ssl renewal",
        "content": "Renew SSL certificate before it expires.",
        "deadline": "2026-05-01",
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id=None, memex_dir=tmp_memex)

    dest = tmp_memex / "notes" / "reminders.md"
    assert dest.exists()
    assert "SSL" in dest.read_text()


def test_flush_reminder_target_project_routes(tmp_memex: Path, tmp_path: Path):
    """REMINDER with target_project routes to that project even when project_id is None."""
    from memex.scripts.flush import flush

    (tmp_memex / "notes" / "projects" / "memex").mkdir(parents=True, exist_ok=True)

    raw_file = tmp_path / "20260425T120000Z.md"
    raw_file.write_text("**User:** For memex, we need to audit flush performance.\n**Assistant:** Added to reminders.")

    mock_response = make_llm_response([{
        "tag": "REMINDER",
        "concept": "flush performance audit",
        "content": "Audit flush.py performance with large transcripts.",
        "target_project": "memex",
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id=None, memex_dir=tmp_memex)

    dest = tmp_memex / "notes" / "projects" / "memex" / "reminders.md"
    assert dest.exists()
    assert "flush.py" in dest.read_text()


# ── POST_MORTEM ──────────────────────────────────────────────────────────────


def test_flush_writes_post_mortem_to_project(tmp_memex: Path, tmp_path: Path):
    """flush() extracts a POST_MORTEM and writes it to project post-mortems.md."""
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260426T120000Z.md"
    raw_file.write_text(
        "**User:** The deploy crashed because we forgot the DB_URL env var.\n"
        "**Assistant:** That's a moderate severity issue. We should add it to CI."
    )

    mock_response = make_llm_response([{
        "tag": "POST_MORTEM",
        "concept": "deploy crash",
        "content": "Staging deploy crashed — missing DB_URL env var. Lesson: always check env vars in CI config. Prevention: added DB_URL to .env.example and CI pipeline.",
        "severity": "moderate",
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    pm = tmp_memex / "notes" / "projects" / "test-project" / "post-mortems.md"
    assert pm.exists()
    text = pm.read_text()
    assert "type/postmortem-log" in text
    assert "DB_URL" in text
    assert "**Severity**: moderate" in text


def test_flush_writes_post_mortem_without_severity(tmp_memex: Path, tmp_path: Path):
    """POST_MORTEM without severity field still works."""
    from memex.scripts.flush import flush

    raw_file = tmp_path / "20260426T120000Z.md"
    raw_file.write_text("**User:** Wasted 2 hours on a dead-end approach.\n**Assistant:** Noted.")

    mock_response = make_llm_response([{
        "tag": "POST_MORTEM",
        "concept": "dead end approach",
        "content": "Spent 2 hours on file-watching approach that didn't work. Lesson: prototype first before full implementation. Prevention: time-box exploration to 30min.",
    }])

    with patch("memex.scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    pm = tmp_memex / "notes" / "projects" / "test-project" / "post-mortems.md"
    assert pm.exists()
    assert "file-watching" in pm.read_text()
