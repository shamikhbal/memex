#!/usr/bin/env python3
"""
flush.py — extracts knowledge from a raw session transcript using Haiku.
Called as: python -m memex.scripts.flush <raw_file> <project_id>
Also importable as a module for testing: from memex.scripts.flush import flush
"""
from __future__ import annotations

# RECURSION GUARD — set before any imports that might trigger Claude Code hooks
import os
os.environ["CLAUDE_INVOKED_BY"] = "memory_flush"

import json
import logging
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = Path(os.environ.get("MEMEX_DIR", Path.home() / ".memex")) / "flush.log"
if not (ROOT / "__init__.py").exists():
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
- EXPLORE: brainstorm, ideation, or exploration — not a concrete decision or lesson, but worth capturing
- SUMMARY: casual or routine conversation — not technical knowledge, but a brief diary-style record of what was discussed
- REMINDER: a follow-up task, pending action, or deferred decision that needs attention in a future session. Include a deadline field (YYYY-MM-DD format) if a date was mentioned, otherwise omit it.
- POST_MORTEM: a failure, mistake, or dead-end that cost time. Include severity ("minor", "moderate", or "major") and the lesson learned plus prevention action.

For each item also provide:
- related: other concept names this item connects to. Use short, lowercase, hyphenated names (e.g. "hook-installer", "ollama-config"). Only list genuinely related concepts.
- tags: 1-3 Obsidian-style tags describing the technology or domain (e.g. "tech/python", "domain/cli", "tech/git"). Do not include type/* or project/* tags — those are added automatically.
- target_project: (optional) only set this if the item clearly belongs to one of the known projects listed below. Use the exact project name. Omit if no match.
- deadline: (REMINDER only) YYYY-MM-DD date string if a specific deadline was mentioned. Omit if no deadline given.
- severity: (POST_MORTEM only) one of "minor", "moderate", or "major".

Known projects: {known_projects}

Return ONLY valid JSON in this format:
{{
  "items": [
    {{
      "tag": "REMINDER",
      "concept": "short concept name (3-5 words)",
      "content": "what needs to be done or followed up on",
      "related": ["other-concept"],
      "tags": ["domain/security"],
      "target_project": "project-name",
      "deadline": "2026-05-15"
    }},
    {{
      "tag": "POST_MORTEM",
      "concept": "what went wrong",
      "content": "what happened, why it failed, the lesson, and how to prevent it",
      "related": ["affected-system"],
      "tags": ["tech/deployment"],
      "target_project": "project-name",
      "severity": "moderate"
    }},
    {{
      "tag": "DECISION",
      "concept": "short concept name (3-5 words)",
      "content": "clear, self-contained description of what was decided/learned/discovered",
      "related": ["other-concept", "another-concept"],
      "tags": ["tech/python", "domain/cli"],
      "target_project": "project-name"
    }}
  ]
}}

If the session was casual, still produce at least one SUMMARY item with a brief note of what was discussed. Only return {{"items": []}} if the transcript is empty or unreadable.

Transcript:
{transcript}"""


def _extract_json(text: str) -> str:
    """Strip markdown fences, extract the outermost {...} block, and repair common LLM JSON errors."""
    if not text:
        return ""
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1:
        return text
    text = text[start:end + 1]
    # Fix trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Fix missing commas between objects in arrays: "}\n  {" → "},\n  {"
    text = re.sub(r"}\s*\n(\s*\{)", r"},\n\1", text)
    return text


def _known_project_ids(notes_dir: Path) -> list[str]:
    """Return list of existing project directory names."""
    projects_dir = notes_dir / "projects"
    if not projects_dir.exists():
        return []
    return [d.name for d in projects_dir.iterdir() if d.is_dir()]


def flush(
    raw_file: Path,
    project_id: Optional[str],
    memex_dir: Optional[Path] = None,
) -> None:
    """Extract knowledge from raw_file and append to Obsidian notes."""
    if memex_dir is None:
        memex_dir = Path.home() / ".memex"

    config = Config(memex_dir=memex_dir)
    state = ProjectState(state_dir=config.state_dir, project_id=project_id or "_daily")

    if not raw_file.exists():
        logging.info("raw file not found, skipping: %s", raw_file)
        return

    content = raw_file.read_text().strip()
    if not content:
        logging.info("raw file empty, skipping: %s", raw_file)
        return

    logging.info("flush triggered — project=%s raw=%s chars=%d", project_id, raw_file.name, len(content))

    known = _known_project_ids(config.notes_dir)
    prompt = FLUSH_PROMPT.replace("{transcript}", content).replace(
        "{known_projects}", ", ".join(known) if known else "(none)"
    )
    client = LLMClient.from_config(config, stage="flush")

    try:
        response = client.complete(prompt=prompt, max_tokens=4096)
    except Exception as e:
        logging.error("LLM request failed: %s", e)
        return

    raw_text = response.text
    if not raw_text or not raw_text.strip():
        logging.error("LLM returned empty response (project=%s raw=%s)", project_id, raw_file.name)
        return

    extracted = _extract_json(raw_text)
    try:
        data = json.loads(extracted)
    except json.JSONDecodeError as e:
        logging.error(
            "LLM response parse error for project=%s raw=%s: %s — first 500 chars: %s",
            project_id, raw_file.name, e, raw_text[:500],
        )
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
            related=item.get("related", []),
            extra_tags=item.get("tags", []),
            target_project=item.get("target_project"),
            deadline=item.get("deadline"),
            severity=item.get("severity"),
        )

    written = [i for i in items if i.get("tag", "SKIP") != "SKIP" and i.get("content")]
    if written:
        state.clear_override()

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
                [sys.executable, str(compile_script), project_id or "", str(memex_dir)],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def main() -> None:
    if len(sys.argv) < 3:
        logging.error("Usage: flush.py <raw_file> <project_id>")
        sys.exit(1)

    raw_file = Path(sys.argv[1])
    project_id = sys.argv[2] or None
    memex_dir_str = os.environ.get("MEMEX_DIR")
    memex_dir = Path(memex_dir_str) if memex_dir_str else None

    flush(raw_file=raw_file, project_id=project_id, memex_dir=memex_dir)


if __name__ == "__main__":
    main()
