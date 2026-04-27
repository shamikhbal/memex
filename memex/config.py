from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml

_DEFAULTS = {
    "flush": {
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001",
        "base_url": None,
        "max_flush_chars": 50000,
    },
    "compile": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "base_url": None,
    },
    "pre_filter": {
        "max_context_chars": 15000,
        "max_turns": 30,
    },
    "session_start": {
        "max_inject_chars": 20000,
        "compile_after_hour": 18,
    },
}


@dataclass
class Config:
    memex_dir: Path = field(default_factory=lambda: Path.home() / ".memex")

    # populated in __post_init__
    flush_provider: str = field(init=False)
    flush_model: str = field(init=False)
    flush_base_url: Optional[str] = field(init=False)
    compile_provider: str = field(init=False)
    compile_model: str = field(init=False)
    compile_base_url: Optional[str] = field(init=False)
    max_context_chars: int = field(init=False)
    max_turns: int = field(init=False)
    max_inject_chars: int = field(init=False)
    max_flush_chars: int = field(init=False)
    compile_after_hour: int = field(init=False)

    def __post_init__(self) -> None:
        data = dict(_DEFAULTS)
        config_path = self.memex_dir / "config.yaml"
        if config_path.exists():
            loaded = yaml.safe_load(config_path.read_text()) or {}
            for section, values in loaded.items():
                if section in data and isinstance(values, dict):
                    data[section] = {**data[section], **values}

        self.flush_provider = data["flush"]["provider"]
        self.flush_model = data["flush"]["model"]
        self.flush_base_url = data["flush"]["base_url"]
        self.compile_provider = data["compile"]["provider"]
        self.compile_model = data["compile"]["model"]
        self.compile_base_url = data["compile"]["base_url"]
        self.max_context_chars = data["pre_filter"]["max_context_chars"]
        self.max_turns = data["pre_filter"]["max_turns"]
        self.max_inject_chars = data["session_start"]["max_inject_chars"]
        self.max_flush_chars = data["flush"]["max_flush_chars"]
        self.compile_after_hour = data["session_start"]["compile_after_hour"]

    @property
    def raw_dir(self) -> Path:
        return self.memex_dir / "raw"

    @property
    def notes_dir(self) -> Path:
        return self.memex_dir / "notes"

    @property
    def state_dir(self) -> Path:
        return self.memex_dir / "state"

    @property
    def graph_dir(self) -> Path:
        return self.memex_dir / "graph" / "global" / "graphify-out"
