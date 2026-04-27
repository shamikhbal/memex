import json
import pytest
from pathlib import Path
from memex.pre_filter import pre_filter, truncate_transcript


def test_extracts_user_and_assistant_turns(sample_jsonl: Path):
    content, count = pre_filter(sample_jsonl, max_context_chars=50000, max_turns=100)
    assert "**User:** How do I parse JSONL?" in content
    assert "**Assistant:** Use json.loads() on each line." in content
    assert count == 4  # 2 user + 2 assistant turns


def test_skips_tool_turns(sample_jsonl: Path):
    content, _ = pre_filter(sample_jsonl, max_context_chars=50000, max_turns=100)
    assert "some tool output" not in content


def test_handles_list_content_blocks(sample_jsonl: Path):
    content, _ = pre_filter(sample_jsonl, max_context_chars=50000, max_turns=100)
    assert "Show me an example." in content
    assert "json.loads" in content


def test_returns_empty_for_empty_transcript(tmp_path: Path):
    transcript = tmp_path / "empty.jsonl"
    transcript.write_text("")
    content, count = pre_filter(transcript, max_context_chars=50000, max_turns=100)
    assert content == ""
    assert count == 0


def test_truncates_to_max_context_chars(sample_jsonl: Path):
    content, _ = pre_filter(sample_jsonl, max_context_chars=50, max_turns=100)
    assert len(content) <= 100  # allow boundary to align to turn start


def test_truncates_to_max_turns(sample_jsonl: Path):
    content, count = pre_filter(sample_jsonl, max_context_chars=50000, max_turns=2)
    assert count == 2


def test_missing_transcript_returns_empty(tmp_path: Path):
    content, count = pre_filter(tmp_path / "nonexistent.jsonl", max_context_chars=50000, max_turns=100)
    assert content == ""
    assert count == 0


# ── truncate_transcript ──────────────────────────────────────────────────────


def test_truncate_transcript_no_truncation_needed():
    text = "short transcript"
    assert truncate_transcript(text, 50000) == text


def test_truncate_transcript_truncates_at_max_chars():
    text = "x" * 200 + "\n**User:** hello"
    result = truncate_transcript(text, 100)
    assert len(result) <= 200  # may include alignment buffer
    assert "User" in result


def test_truncate_transcript_aligns_to_turn_boundary():
    text = "ignore this junk\n**User:** real content here\n**Assistant:** yes indeed"
    result = truncate_transcript(text, 55)
    assert result.startswith("**User:**") or result.startswith("**Assistant:")
    assert "ignore this junk" not in result


def test_truncate_transcript_empty():
    assert truncate_transcript("", 100) == ""


def test_truncate_transcript_exact_boundary():
    text = "**User:** hi\n**Assistant:** hello"
    result = truncate_transcript(text, 50000)
    assert result == text
