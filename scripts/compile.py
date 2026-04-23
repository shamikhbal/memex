#!/usr/bin/env python3
"""
compile.py — uses Sonnet to write each project's _index.md, then triggers graphify.
Called as: python scripts/compile.py <project_id> [memex_dir]
Also importable as module: from scripts.compile import compile_project
"""
from __future__ import annotations

import os
os.environ["CLAUDE_INVOKED_BY"] = "memory_flush"

import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "scripts" / "flush.log"
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [compile] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from memex.config import Config
from memex.llm_client import LLMClient

INDEX_PROMPT = """\
You are a knowledge base curator writing Obsidian-flavored Markdown. Read all the notes below for the project "{project_id}" and write a concise _index.md — a living overview.

Output format (follow exactly):

1. YAML frontmatter with: title, tags (include project/{project_id} and relevant tech/* tags), status (active/paused/completed)
2. A level-1 heading: # {{project name}} — Overview
3. An Obsidian callout summarising what the project does:
   > [!info] What is {{project}}?
   > 1-2 sentence summary.
4. A "Tech Stack" or "Architecture" section using a table if applicable
5. "Key Decisions" section — bulleted, concise
6. "Concepts & Patterns" section — bulleted, concise
7. "Current Status" section — 1-2 sentences

Be concise. Max 300 words of body content (excluding frontmatter). Use wikilinks ([[concept-name]]) when referencing concepts that have their own note files.

Notes:
{notes_content}"""


def compile_project(project_id: str, memex_dir: Optional[Path] = None) -> None:
    """Write/update _index.md for a project and trigger graphify."""
    if memex_dir is None:
        memex_dir = Path.home() / ".memex"

    config = Config(memex_dir=memex_dir)
    proj_dir = config.notes_dir / "projects" / project_id

    # Collect all non-index markdown notes
    note_files = [f for f in proj_dir.glob("*.md") if f.name != "_index.md"] if proj_dir.exists() else []
    if not note_files:
        logging.info("no notes found for project %s, skipping", project_id)
        return

    notes_content = ""
    for f in sorted(note_files):
        notes_content += f"\n\n### {f.stem}\n\n{f.read_text()}"

    prompt = INDEX_PROMPT.replace("{project_id}", project_id).replace("{notes_content}", notes_content.strip())
    client = LLMClient.from_config(config, stage="compile")

    try:
        response = client.complete(prompt=prompt, max_tokens=1024)
        index_content = response.text.strip()
    except Exception as e:
        logging.error("compile LLM error for %s: %s", project_id, e)
        return

    index_path = proj_dir / "_index.md"
    index_path.write_text(index_content + "\n")
    logging.info("wrote _index.md for project %s", project_id)

    _run_graphify(memex_dir)


def _run_graphify(memex_dir: Path) -> None:
    """Run graphify --update if installed."""
    graphify_bin = shutil.which("graphify")
    if not graphify_bin:
        logging.info("graphify not installed, skipping graph update")
        return

    notes_dir = memex_dir / "notes"
    try:
        subprocess.run(
            [graphify_bin, str(notes_dir), "--update", "--obsidian"],
            timeout=120,
            capture_output=True,
        )
        logging.info("graphify --update completed")
    except subprocess.TimeoutExpired:
        logging.warning("graphify timed out")
    except Exception as e:
        logging.error("graphify error: %s", e)


def main() -> None:
    if len(sys.argv) < 2:
        logging.error("Usage: compile.py <project_id> [memex_dir]")
        sys.exit(1)

    project_id = sys.argv[1]
    memex_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    compile_project(project_id=project_id, memex_dir=memex_dir)


if __name__ == "__main__":
    main()
