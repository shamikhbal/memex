from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

_DATE_PATTERN = re.compile(r"^## (\d{4}-\d{2}-\d{2})", re.MULTILINE)
_ACTIVE_DAYS = 7
_PAUSED_DAYS = 30


@dataclass
class ProjectState:
    state_dir: Path
    project_id: str
    last_flush_session_id: Optional[str] = None
    last_flush_timestamp: Optional[float] = None
    last_compile_timestamp: Optional[float] = None
    daily_hash: Optional[str] = None
    total_cost: float = 0.0
    status_override: Optional[str] = None
    status_override_timestamp: Optional[float] = None

    def __post_init__(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        state_file = self._path()
        if state_file.exists():
            data = json.loads(state_file.read_text())
            self.last_flush_session_id = data.get("last_flush_session_id")
            self.last_flush_timestamp = data.get("last_flush_timestamp")
            self.last_compile_timestamp = data.get("last_compile_timestamp")
            self.daily_hash = data.get("daily_hash")
            self.total_cost = data.get("total_cost", 0.0)
            self.status_override = data.get("status_override")
            self.status_override_timestamp = data.get("status_override_timestamp")

    def _path(self) -> Path:
        return self.state_dir / f"{self.project_id}.json"

    def save(self) -> None:
        data = {
            "last_flush_session_id": self.last_flush_session_id,
            "last_flush_timestamp": self.last_flush_timestamp,
            "last_compile_timestamp": self.last_compile_timestamp,
            "daily_hash": self.daily_hash,
            "total_cost": self.total_cost,
            "status_override": self.status_override,
            "status_override_timestamp": self.status_override_timestamp,
        }
        self._path().write_text(json.dumps(data, indent=2))

    def _latest_note_date(self, notes_dir: Path) -> Optional[date]:
        """Return the latest date found in ## YYYY-MM-DD headings across project .md files."""
        proj_dir = notes_dir / "projects" / self.project_id
        if not proj_dir.exists():
            return None
        latest: Optional[date] = None
        for md_file in proj_dir.glob("*.md"):
            if md_file.name == "_index.md":
                continue
            text = md_file.read_text()
            for m in _DATE_PATTERN.finditer(text):
                try:
                    d = date.fromisoformat(m.group(1))
                except ValueError:
                    continue
                if latest is None or d > latest:
                    latest = d
        return latest

    def derive_status(self, notes_dir: Path) -> str:
        """Return project status: override if set, else auto-derive from note recency."""
        if self.status_override is not None:
            return self.status_override
        latest = self._latest_note_date(notes_dir)
        if latest is None:
            return "dormant"
        delta = (date.today() - latest).days
        if delta <= _ACTIVE_DAYS:
            return "active"
        elif delta <= _PAUSED_DAYS:
            return "paused"
        else:
            return "dormant"

    def set_override(self, status: str) -> None:
        """Manually override the derived status."""
        self.status_override = status
        self.status_override_timestamp = time.time()

    def clear_override(self) -> None:
        """Remove manual override, reverting to auto-derive."""
        self.status_override = None
        self.status_override_timestamp = None

    def is_duplicate_flush(self, session_id: str, dedup_window: int = 60) -> bool:
        """Return True if this session was flushed within dedup_window seconds."""
        if self.last_flush_session_id != session_id:
            return False
        if self.last_flush_timestamp is None:
            return False
        return (time.time() - self.last_flush_timestamp) < dedup_window
