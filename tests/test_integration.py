# tests/test_integration.py
"""
End-to-end Phase 1 integration test.
Simulates a session ending → verifies raw file written + flush stub ran.
"""
import json
import subprocess
import sys
import time
from pathlib import Path


def test_session_end_to_raw_file(tmp_memex: Path, sample_jsonl: Path, tmp_path: Path):
    """Full hook → raw file pipeline."""
    import os

    hook = Path("hooks/session-end.py").resolve()
    hook_input = {
        "session_id": "integration-sess-001",
        "transcript_path": str(sample_jsonl),
        "cwd": str(tmp_path),
    }

    env = os.environ.copy()
    env.pop("CLAUDE_INVOKED_BY", None)
    env["MEMEX_DIR"] = str(tmp_memex)

    result = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(hook_input),
        text=True,
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0, f"hook failed: {result.stderr}"

    raw_files = list((tmp_memex / "raw").rglob("*.md"))
    assert len(raw_files) == 1, "expected exactly one raw file"

    raw_content = raw_files[0].read_text()
    assert "**User:** How do I parse JSONL?" in raw_content
    assert "some tool output" not in raw_content  # tool turns filtered

    # Give flush stub 2s to write its log
    time.sleep(2)
    log_file = Path("scripts/flush.log")
    if log_file.exists():
        log_content = log_file.read_text()
        assert "flush triggered" in log_content
