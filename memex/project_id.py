from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional


def _git_remote(cwd: Path) -> Optional[str]:
    """Return the git origin URL for cwd, or None if not a git repo / no remote."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
        url = result.stdout.strip()
        return url if result.returncode == 0 and url else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _slugify(text: str) -> str:
    """Convert arbitrary string to lowercase alphanumeric-and-hyphens slug."""
    text = text.lower()
    # strip .git suffix
    text = re.sub(r"\.git$", "", text)
    # strip protocol prefix
    text = re.sub(r"^(https?://|git@|ssh://)", "", text)
    # replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # strip leading/trailing hyphens
    return text.strip("-")


def get_project_id(cwd: Path) -> str:
    """Return a stable, filesystem-safe project identifier for the given directory."""
    remote = _git_remote(cwd)
    if remote:
        return _slugify(remote)
    return _slugify(cwd.name)
