#!/usr/bin/env python3
"""
PreCompact hook — safety net before AI platform auto-compacts context.
Same architecture as session-end.py. Guards against empty transcript_path (known CC bug #13668).

Supports both Claude Code and Factory Droid platforms.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

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
    format="%(asctime)s %(levelname)s [pre-compact] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main() -> None:
    if _IS_FACTORY:
        hook_input = {}
    else:
        try:
            hook_input = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, ValueError) as e:
            logging.error("invalid hook input: %s", e)
            sys.exit(0)

    transcript_path_str: str = hook_input.get("transcript_path", "")
    cwd_str: str = hook_input.get("cwd", ".")

    if _IS_FACTORY:
        cwd = Path(os.environ["FACTORY_PROJECT_DIR"])
    else:
        cwd = Path(cwd_str)

    # Known CC bug: transcript_path can be empty on PreCompact
    if not transcript_path_str:
        logging.info("empty transcript_path (known CC bug), skipping")
        sys.exit(0)

    transcript_path = Path(transcript_path_str)

    content, turn_count = pre_filter(
        transcript_path,
        max_context_chars=config.max_context_chars,
        max_turns=config.max_turns,
    )

    if not content:
        logging.info("pre-filter produced empty output, skipping")
        sys.exit(0)

    project_id = get_project_id(cwd)
    raw_dir = config.raw_dir / (project_id or "_daily")
    raw_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_file = raw_dir / f"{timestamp}-compact.md"
    raw_file.write_text(content)

    logging.info("pre-compact: wrote raw file %s (%d turns)", raw_file.name, turn_count)

    flush_script = ROOT / "scripts" / "flush.py"
    subprocess.Popen(
        [sys.executable, str(flush_script), str(raw_file), project_id or ""],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    main()
