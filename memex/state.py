from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ProjectState:
    state_dir: Path
    project_id: str
    last_flush_session_id: Optional[str] = None
    last_flush_timestamp: Optional[float] = None
    last_compile_timestamp: Optional[float] = None
    daily_hash: Optional[str] = None
    total_cost: float = 0.0

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

    def _path(self) -> Path:
        return self.state_dir / f"{self.project_id}.json"

    def save(self) -> None:
        data = {
            "last_flush_session_id": self.last_flush_session_id,
            "last_flush_timestamp": self.last_flush_timestamp,
            "last_compile_timestamp": self.last_compile_timestamp,
            "daily_hash": self.daily_hash,
            "total_cost": self.total_cost,
        }
        self._path().write_text(json.dumps(data, indent=2))

    def is_duplicate_flush(self, session_id: str, dedup_window: int = 60) -> bool:
        """Return True if this session was flushed within dedup_window seconds."""
        if self.last_flush_session_id != session_id:
            return False
        if self.last_flush_timestamp is None:
            return False
        return (time.time() - self.last_flush_timestamp) < dedup_window
