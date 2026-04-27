#!/usr/bin/env python3
"""
SessionStart hook — injects knowledge from ~/.memex/notes/ into session context.

Supports both Claude Code and Factory Droid platforms:
- Claude Code: outputs hookSpecificOutput.additionalContext JSON
- Factory Droid: prints raw context text to stdout

Budget allocation (of max_inject_chars):
  _index.md      35%
  decisions.md   15%
  daily note     20%
  reminders       5%
  postmortems     5%
  concepts       remaining

Auto-triggers compile.py when last compile is from a previous day and
the hour has passed compile_after_hour.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
# Only insert when running from source repo (ROOT has no __init__.py = not inside a package)
if not (ROOT / "__init__.py").exists():
    sys.path.insert(0, str(ROOT))

from memex.config import Config
from memex.inject import build_context
from memex.project_id import get_project_id
from memex.state import ProjectState

MEMEX_DIR = Path(os.environ.get("MEMEX_DIR", Path.home() / ".memex"))
config = Config(memex_dir=MEMEX_DIR)

# Detect platform: Factory Droid sets FACTORY_PROJECT_DIR
_IS_FACTORY = bool(os.environ.get("FACTORY_PROJECT_DIR"))


def _compile_needed(state: ProjectState) -> bool:
    """Return True if compile.py should run before injection."""
    now = datetime.now()
    if now.hour < config.compile_after_hour:
        return False
    if state.last_compile_timestamp is None:
        return True
    last = datetime.fromtimestamp(state.last_compile_timestamp)
    return last.date() < date.today()


def main() -> None:
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        hook_input = {}

    # Factory passes cwd via FACTORY_PROJECT_DIR; Claude Code via stdin
    if _IS_FACTORY:
        cwd = Path(os.environ["FACTORY_PROJECT_DIR"])
    else:
        cwd_str: str = hook_input.get("cwd", ".")
        cwd = Path(cwd_str)

    project_id = get_project_id(cwd)

    state = ProjectState(state_dir=config.state_dir, project_id=project_id)

    if _compile_needed(state):
        compile_script = ROOT / "scripts" / "compile.py"
        subprocess.run(
            [sys.executable, str(compile_script), project_id],
            env={**os.environ, "MEMEX_DIR": str(MEMEX_DIR)},
            timeout=120,
        )

    graph_json = config.graph_dir / "graph.json"
    context = build_context(
        config,
        project_id,
        graph_json=graph_json if graph_json.exists() else None,
    )

    if _IS_FACTORY:
        # Factory: stdout is added as context for Droid
        if context:
            print(context)
    else:
        # Claude Code: output hookSpecificOutput JSON
        output = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            }
        }
        print(json.dumps(output))


if __name__ == "__main__":
    main()
