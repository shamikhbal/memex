#!/usr/bin/env python3
"""
SessionEnd hook — captures AI session transcript → raw file → spawns flush.py.

Supports both Claude Code and Factory Droid platforms.
No API calls. Must complete in <10 seconds.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Recursion guard — exit immediately if spawned by flush.py
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / "__init__.py").exists():
    sys.path.insert(0, str(ROOT))

from memex.config import Config
from memex.pre_filter import pre_filter
from memex.project_id import get_project_id

MEMEX_DIR = Path(os.environ.get("MEMEX_DIR", Path.home() / ".memex"))
config = Config(memex_dir=MEMEX_DIR)

_IS_FACTORY = bool(os.environ.get("FACTORY_PROJECT_DIR"))

logging.basicConfig(
    filename=str(MEMEX_DIR / "flush.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [session-end] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _read_transcript(hook_input: dict) -> str | None:
    """Read transcript content from either Claude Code or Factory Droid payload."""
    # Factory Droid may provide transcript directly
    transcript = hook_input.get("transcript", "") or hook_input.get("transcript_path", "")
    if transcript:
        if "\n" in transcript and len(transcript) > 200:
            return transcript.lstrip("\ufeff")
        # It's a file path
        tp = Path(transcript)
        if tp.exists():
            return tp.read_text(encoding="utf-8")
    return None


def main() -> None:
    if _IS_FACTORY:
        hook_input = {}
    else:
        try:
            hook_input = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, ValueError) as e:
            logging.error("invalid hook input: %s", e)
            sys.exit(0)

    session_id: str = hook_input.get("session_id", "unknown")
    transcript_path_str: str = hook_input.get("transcript_path", "")
    cwd_str: str = hook_input.get("cwd", ".")

    if _IS_FACTORY:
        cwd = Path(os.environ["FACTORY_PROJECT_DIR"])
    else:
        cwd = Path(cwd_str)

    # Try reading transcript — Factory may provide it differently
    transcript = _read_transcript(hook_input)

    if transcript:
        content = transcript
        turn_count = content.count("\n") // 2  # rough estimate
    elif transcript_path_str:
        transcript_path = Path(transcript_path_str)
        content, turn_count = pre_filter(
            transcript_path,
            max_context_chars=config.max_context_chars,
            max_turns=config.max_turns,
        )
    else:
        logging.info("no transcript_path, skipping")
        sys.exit(0)

    if not content:
        logging.info("pre-filter produced empty output, skipping")
        sys.exit(0)

    project_id = get_project_id(cwd)
    raw_dir = config.raw_dir / (project_id or "_daily")
    raw_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_file = raw_dir / f"{timestamp}.md"
    raw_file.write_text(content)

    logging.info("wrote raw file: %s (%d turns)", raw_file.name, turn_count)

    # Spawn flush.py as a detached background process
    flush_script = ROOT / "scripts" / "flush.py"
    subprocess.Popen(
        [sys.executable, str(flush_script), str(raw_file), project_id or ""],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logging.info("spawned flush.py for session %s", session_id)


if __name__ == "__main__":
    main()
