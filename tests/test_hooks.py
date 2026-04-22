import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import importlib


def run_hook(hook_path: Path, stdin_data: dict, env: dict | None = None) -> int:
    """Run a hook script as a subprocess and return exit code."""
    import subprocess
    import os
    environment = os.environ.copy()
    environment.pop("CLAUDE_INVOKED_BY", None)
    if env:
        environment.update(env)
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(stdin_data),
        text=True,
        capture_output=True,
        env=environment,
    )
    return result.returncode


def test_session_end_writes_raw_file(tmp_memex: Path, sample_jsonl: Path, tmp_path: Path):
    hook = Path("hooks/session-end.py")
    hook_input = {
        "session_id": "sess-001",
        "transcript_path": str(sample_jsonl),
        "cwd": str(tmp_path),
    }
    with patch.dict("os.environ", {"MEMEX_DIR": str(tmp_memex)}):
        returncode = run_hook(hook, hook_input, env={"MEMEX_DIR": str(tmp_memex)})
    assert returncode == 0
    raw_files = list((tmp_memex / "raw").rglob("*.md"))
    assert len(raw_files) == 1
    assert "User:" in raw_files[0].read_text()


def test_session_end_exits_on_recursion_guard(tmp_memex: Path, sample_jsonl: Path, tmp_path: Path):
    hook = Path("hooks/session-end.py")
    hook_input = {"session_id": "sess-001", "transcript_path": str(sample_jsonl), "cwd": str(tmp_path)}
    returncode = run_hook(hook, hook_input, env={"CLAUDE_INVOKED_BY": "memory_flush", "MEMEX_DIR": str(tmp_memex)})
    assert returncode == 0
    raw_files = list((tmp_memex / "raw").rglob("*.md"))
    assert len(raw_files) == 0  # nothing written


def test_session_end_skips_empty_transcript(tmp_memex: Path, tmp_path: Path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    hook = Path("hooks/session-end.py")
    hook_input = {"session_id": "sess-001", "transcript_path": str(empty), "cwd": str(tmp_path)}
    returncode = run_hook(hook, hook_input, env={"MEMEX_DIR": str(tmp_memex)})
    assert returncode == 0
    raw_files = list((tmp_memex / "raw").rglob("*.md"))
    assert len(raw_files) == 0
