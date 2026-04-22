#!/usr/bin/env python3
"""
flush.py — extracts knowledge from a raw session transcript using Haiku.
Called as: python scripts/flush.py <raw_file> <project_id>
Also importable as a module for testing: from scripts.flush import flush
"""
from __future__ import annotations

# RECURSION GUARD — set before any imports that might trigger Claude Code hooks
import os
os.environ["CLAUDE_INVOKED_BY"] = "memory_flush"

import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "scripts" / "flush.log"
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [flush] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from memex.config import Config
from memex.llm_client import LLMClient
from memex.note_writer import append_item
from memex.state import ProjectState

FLUSH_PROMPT = """\
You are a knowledge extraction assistant. Read the following AI coding session transcript and extract items worth remembering long-term.

For each item, assign one tag:
- DECISION: a non-obvious choice made (technology, architecture, approach) with clear rationale
- INSIGHT: something learned that would be useful next time (how-to, debugging lesson, pattern)
- PATTERN: a reusable cross-project pattern or technique
- SKIP: routine conversation, small talk, nothing worth keeping

Return ONLY valid JSON in this format:
{{
  "items": [
    {{
      "tag": "DECISION",
      "concept": "short concept name (3-5 words)",
      "content": "clear, self-contained description of what was decided/learned/discovered"
    }}
  ]
}}

If nothing is worth keeping, return: {{"items": []}}

Transcript:
{transcript}"""


def flush(
    raw_file: Path,
    project_id: str,
    memex_dir: Optional[Path] = None,
) -> None:
    """Extract knowledge from raw_file and append to Obsidian notes."""
    if memex_dir is None:
        memex_dir = Path.home() / ".memex"

    config = Config(memex_dir=memex_dir)
    state = ProjectState(state_dir=config.state_dir, project_id=project_id)

    if not raw_file.exists():
        logging.info("raw file not found, skipping: %s", raw_file)
        return

    content = raw_file.read_text().strip()
    if not content:
        logging.info("raw file empty, skipping: %s", raw_file)
        return

    logging.info("flush triggered — project=%s raw=%s chars=%d", project_id, raw_file.name, len(content))

    prompt = FLUSH_PROMPT.replace("{transcript}", content)
    client = LLMClient.from_config(config, stage="flush")

    try:
        response = client.complete(prompt=prompt, max_tokens=2048)
        data = json.loads(response.text)
    except (json.JSONDecodeError, Exception) as e:
        logging.error("LLM response parse error: %s", e)
        return

    items = data.get("items", [])
    logging.info("extracted %d items", len(items))

    for item in items:
        tag = item.get("tag", "SKIP")
        concept = item.get("concept", "general")
        item_content = item.get("content", "")
        if not item_content or tag == "SKIP":
            continue
        append_item(
            tag=tag,
            content=item_content,
            concept=concept,
            project_id=project_id,
            notes_dir=config.notes_dir,
        )

    # Update state
    state.last_flush_session_id = raw_file.stem
    state.last_flush_timestamp = time.time()
    state.save()

    # Check if we should trigger compile (past compile_after_hour AND new content written)
    if items and datetime.now().hour >= config.compile_after_hour:
        compile_script = ROOT / "scripts" / "compile.py"
        if compile_script.exists():
            logging.info("triggering compile.py (past %d:00 with new content)", config.compile_after_hour)
            subprocess.Popen(
                [sys.executable, str(compile_script), project_id, str(memex_dir)],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def main() -> None:
    if len(sys.argv) < 3:
        logging.error("Usage: flush.py <raw_file> <project_id>")
        sys.exit(1)

    raw_file = Path(sys.argv[1])
    project_id = sys.argv[2]
    memex_dir_str = os.environ.get("MEMEX_DIR")
    memex_dir = Path(memex_dir_str) if memex_dir_str else None

    flush(raw_file=raw_file, project_id=project_id, memex_dir=memex_dir)


if __name__ == "__main__":
    main()
