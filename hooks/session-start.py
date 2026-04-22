#!/usr/bin/env python3
"""
SessionStart hook — injects knowledge from ~/.memex/notes/ into session context.
Priority order (capped at max_inject_chars):
  1. notes/projects/{project-id}/_index.md
  2. notes/projects/{project-id}/decisions.md
  3. notes/daily/YYYY-MM-DD.md (today)
  4. Top 3 notes/concepts/ by most-recently-modified
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memex.config import Config
from memex.project_id import get_project_id

MEMEX_DIR = Path(os.environ.get("MEMEX_DIR", Path.home() / ".memex"))
config = Config(memex_dir=MEMEX_DIR)


def read_capped(path: Path, budget: int) -> tuple[str, int]:
    """Read file content up to budget chars. Returns (content, chars_used)."""
    if not path.exists():
        return "", 0
    text = path.read_text(encoding="utf-8")
    if len(text) > budget:
        text = text[:budget]
    return text, len(text)


def main() -> None:
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        hook_input = {}

    cwd_str: str = hook_input.get("cwd", ".")
    cwd = Path(cwd_str)
    project_id = get_project_id(cwd)

    notes = config.notes_dir
    budget = config.max_inject_chars
    sections: list[str] = []

    priority_files = [
        notes / "projects" / project_id / "_index.md",
        notes / "projects" / project_id / "decisions.md",
        notes / "daily" / f"{date.today().isoformat()}.md",
    ]

    for p in priority_files:
        if budget <= 0:
            break
        content, used = read_capped(p, budget)
        if content:
            sections.append(f"## {p.name}\n\n{content}")
            budget -= used

    # Top 3 concept notes by recency
    concepts_dir = notes / "concepts"
    if concepts_dir.exists() and budget > 0:
        concept_files = sorted(
            concepts_dir.glob("*.md"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[:3]
        for p in concept_files:
            if budget <= 0:
                break
            content, used = read_capped(p, budget)
            if content:
                sections.append(f"## {p.stem}\n\n{content}")
                budget -= used

    context = "\n\n---\n\n".join(sections) if sections else ""

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
