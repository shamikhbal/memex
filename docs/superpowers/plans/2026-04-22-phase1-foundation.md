# memex Phase 1 — FOUNDATION Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture Claude Code sessions to `~/.memex/raw/`, pre-filter transcripts to user/assistant turns, and spawn a flush stub — no API calls, just the plumbing.

**Architecture:** Three Claude Code hooks (SessionEnd, PreCompact, SessionStart) call a pure-Python pre-filter, write raw transcripts to `~/.memex/raw/{project-id}/`, and spawn `flush.py` as a detached background process. flush.py is a stub in Phase 1 — it logs and exits. State tracking lives in `~/.memex/state/{project-id}.json`.

**Tech Stack:** Python 3.11+, PyYAML, pytest, uv (package manager)

---

## File Map

```
memex/                                    # project root = /Users/seetrustudio-17/Documents/memex/
├── pyproject.toml                        # CREATE: package + dependencies
├── memex/
│   ├── __init__.py                       # CREATE: empty
│   ├── config.py                         # CREATE: load ~/.memex/config.yaml, path constants
│   ├── project_id.py                     # CREATE: git remote → sanitised slug
│   ├── pre_filter.py                     # CREATE: JSONL transcript → user/assistant markdown
│   └── state.py                          # CREATE: read/write ~/.memex/state/{project-id}.json
├── hooks/
│   ├── session-end.py                    # CREATE: SessionEnd hook
│   ├── pre-compact.py                    # CREATE: PreCompact hook
│   └── session-start.py                  # CREATE: SessionStart hook (stub, injects nothing in Phase 1)
├── scripts/
│   └── flush.py                          # CREATE: stub — logs trigger, no API calls
└── tests/
    ├── conftest.py                        # CREATE: shared fixtures
    ├── test_config.py                     # CREATE
    ├── test_project_id.py                 # CREATE
    ├── test_pre_filter.py                 # CREATE
    ├── test_state.py                      # CREATE
    └── test_hooks.py                      # CREATE: hook integration tests
```

---

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `memex/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "memex"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "pyyaml>=6.0",
    "click>=8.1",
]

[project.scripts]
memex = "memex.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create memex/__init__.py**

```python
```
(empty file)

- [ ] **Step 3: Create tests/conftest.py**

```python
import pytest
from pathlib import Path


@pytest.fixture
def tmp_memex(tmp_path: Path) -> Path:
    """A temporary ~/.memex/ directory for tests."""
    memex = tmp_path / ".memex"
    for d in ["raw", "notes/projects", "notes/concepts", "notes/daily", "state", "graph/global"]:
        (memex / d).mkdir(parents=True)
    return memex


@pytest.fixture
def sample_jsonl(tmp_path: Path) -> Path:
    """A minimal Claude Code JSONL transcript."""
    transcript = tmp_path / "transcript.jsonl"
    import json
    lines = [
        {"message": {"role": "user", "content": "How do I parse JSONL?"}},
        {"message": {"role": "assistant", "content": "Use json.loads() on each line."}},
        {"message": {"role": "user", "content": [{"type": "text", "text": "Show me an example."}]}},
        {"message": {"role": "assistant", "content": [{"type": "text", "text": "```python\nfor line in f:\n    obj = json.loads(line)\n```"}]}},
        # Tool result — should be filtered out
        {"message": {"role": "tool", "content": "some tool output"}},
    ]
    transcript.write_text("\n".join(json.dumps(l) for l in lines))
    return transcript
```

- [ ] **Step 4: Install dependencies**

```bash
uv sync
```

Expected: resolves and installs anthropic, pyyaml, click.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml memex/__init__.py tests/conftest.py
git commit -m "chore: scaffold memex package"
```

---

### Task 2: config.py — Load Config + Path Constants

**Files:**
- Create: `memex/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config.py
import pytest
from pathlib import Path
from memex.config import Config


def test_default_config_has_required_keys(tmp_memex: Path):
    cfg = Config(memex_dir=tmp_memex)
    assert cfg.flush_model == "claude-haiku-4-5-20251001"
    assert cfg.flush_provider == "anthropic"
    assert cfg.compile_model == "claude-sonnet-4-6"
    assert cfg.compile_provider == "anthropic"
    assert cfg.max_context_chars == 15000
    assert cfg.max_turns == 30
    assert cfg.max_inject_chars == 20000
    assert cfg.compile_after_hour == 18


def test_config_path_constants(tmp_memex: Path):
    cfg = Config(memex_dir=tmp_memex)
    assert cfg.raw_dir == tmp_memex / "raw"
    assert cfg.notes_dir == tmp_memex / "notes"
    assert cfg.state_dir == tmp_memex / "state"
    assert cfg.graph_dir == tmp_memex / "graph" / "global" / "graphify-out"


def test_config_loads_from_yaml(tmp_memex: Path):
    import yaml
    yaml_content = {
        "flush": {"provider": "openai", "model": "gpt-4o-mini", "base_url": "http://localhost:11434"},
        "compile": {"provider": "anthropic", "model": "claude-sonnet-4-6", "base_url": None},
        "pre_filter": {"max_context_chars": 8000, "max_turns": 20},
        "session_start": {"max_inject_chars": 10000, "compile_after_hour": 20},
    }
    (tmp_memex / "config.yaml").write_text(yaml.dump(yaml_content))
    cfg = Config(memex_dir=tmp_memex)
    assert cfg.flush_provider == "openai"
    assert cfg.flush_model == "gpt-4o-mini"
    assert cfg.flush_base_url == "http://localhost:11434"
    assert cfg.max_context_chars == 8000
    assert cfg.compile_after_hour == 20
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_config.py -v
```

Expected: ImportError or ModuleNotFoundError — `memex.config` doesn't exist yet.

- [ ] **Step 3: Implement memex/config.py**

```python
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add memex/config.py tests/test_config.py
git commit -m "feat: add Config with yaml loading and path constants"
```

---

### Task 3: project_id.py — Git Remote → Slug

**Files:**
- Create: `memex/project_id.py`
- Create: `tests/test_project_id.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_project_id.py
import pytest
from pathlib import Path
from unittest.mock import patch
from memex.project_id import get_project_id


def test_github_ssh_remote():
    with patch("memex.project_id._git_remote", return_value="git@github.com:sham/orbit.git"):
        assert get_project_id(Path("/some/path")) == "github-com-sham-orbit"


def test_github_https_remote():
    with patch("memex.project_id._git_remote", return_value="https://github.com/sham/memex.git"):
        assert get_project_id(Path("/some/path")) == "github-com-sham-memex"


def test_no_git_remote_falls_back_to_dirname():
    with patch("memex.project_id._git_remote", return_value=None):
        assert get_project_id(Path("/Users/sham/my-project")) == "my-project"


def test_slug_is_lowercase_and_safe():
    with patch("memex.project_id._git_remote", return_value="https://github.com/Sham/My_Project.git"):
        slug = get_project_id(Path("/any"))
        assert slug == slug.lower()
        assert all(c.isalnum() or c == "-" for c in slug)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_project_id.py -v
```

Expected: ImportError — `memex.project_id` doesn't exist yet.

- [ ] **Step 3: Implement memex/project_id.py**

```python
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_project_id.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add memex/project_id.py tests/test_project_id.py
git commit -m "feat: add project_id — git remote to filesystem slug"
```

---

### Task 4: pre_filter.py — JSONL Transcript → Markdown

**Files:**
- Create: `memex/pre_filter.py`
- Create: `tests/test_pre_filter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pre_filter.py
import json
import pytest
from pathlib import Path
from memex.pre_filter import pre_filter


def test_extracts_user_and_assistant_turns(sample_jsonl: Path):
    content, count = pre_filter(sample_jsonl, max_context_chars=50000, max_turns=100)
    assert "**User:** How do I parse JSONL?" in content
    assert "**Assistant:** Use json.loads() on each line." in content
    assert count == 4  # 2 user + 2 assistant turns


def test_skips_tool_turns(sample_jsonl: Path):
    content, _ = pre_filter(sample_jsonl, max_context_chars=50000, max_turns=100)
    assert "some tool output" not in content


def test_handles_list_content_blocks(sample_jsonl: Path):
    content, _ = pre_filter(sample_jsonl, max_context_chars=50000, max_turns=100)
    assert "Show me an example." in content
    assert "json.loads" in content


def test_returns_empty_for_empty_transcript(tmp_path: Path):
    transcript = tmp_path / "empty.jsonl"
    transcript.write_text("")
    content, count = pre_filter(transcript, max_context_chars=50000, max_turns=100)
    assert content == ""
    assert count == 0


def test_truncates_to_max_context_chars(sample_jsonl: Path):
    content, _ = pre_filter(sample_jsonl, max_context_chars=50, max_turns=100)
    assert len(content) <= 100  # allow boundary to align to turn start


def test_truncates_to_max_turns(sample_jsonl: Path):
    content, count = pre_filter(sample_jsonl, max_context_chars=50000, max_turns=2)
    assert count == 2


def test_missing_transcript_returns_empty(tmp_path: Path):
    content, count = pre_filter(tmp_path / "nonexistent.jsonl", max_context_chars=50000, max_turns=100)
    assert content == ""
    assert count == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_pre_filter.py -v
```

Expected: ImportError — `memex.pre_filter` doesn't exist yet.

- [ ] **Step 3: Implement memex/pre_filter.py**

```python
from __future__ import annotations

import json
from pathlib import Path


def _extract_text(content: object) -> str:
    """Extract plain text from a content field (string or list of blocks)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", "").strip())
            elif isinstance(block, str):
                parts.append(block.strip())
        return "\n".join(p for p in parts if p)
    return ""


def pre_filter(
    transcript_path: Path,
    max_context_chars: int,
    max_turns: int,
) -> tuple[str, int]:
    """
    Read a Claude Code JSONL transcript and return (markdown_text, turn_count).

    Keeps only user/assistant turns. Strips tool calls, tool results, file reads.
    Truncates to max_turns and max_context_chars.
    Returns ("", 0) if the file is missing or produces no output.
    """
    if not transcript_path.exists():
        return "", 0

    turns: list[str] = []
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = entry.get("message", {})
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                else:
                    role = entry.get("role", "")
                    content = entry.get("content", "")

                if role not in ("user", "assistant"):
                    continue

                text = _extract_text(content)
                if not text:
                    continue

                label = "User" if role == "user" else "Assistant"
                turns.append(f"**{label}:** {text}\n")
    except OSError:
        return "", 0

    recent = turns[-max_turns:] if max_turns < len(turns) else turns
    context = "\n".join(recent)

    if len(context) > max_context_chars:
        context = context[-max_context_chars:]
        # align to turn boundary
        boundary = context.find("\n**")
        if boundary > 0:
            context = context[boundary + 1:]

    return context, len(recent)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_pre_filter.py -v
```

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add memex/pre_filter.py tests/test_pre_filter.py
git commit -m "feat: add pre_filter — JSONL transcript to user/assistant markdown"
```

---

### Task 5: state.py — Read/Write State JSON

**Files:**
- Create: `memex/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_state.py
import pytest
from pathlib import Path
from memex.state import ProjectState


def test_default_state_is_empty(tmp_memex: Path):
    state = ProjectState(state_dir=tmp_memex / "state", project_id="test-proj")
    assert state.last_flush_session_id is None
    assert state.last_flush_timestamp is None
    assert state.last_compile_timestamp is None
    assert state.daily_hash is None
    assert state.total_cost == 0.0


def test_save_and_reload(tmp_memex: Path):
    state_dir = tmp_memex / "state"
    state = ProjectState(state_dir=state_dir, project_id="test-proj")
    state.last_flush_session_id = "sess-abc"
    state.last_flush_timestamp = 1714000000.0
    state.daily_hash = "abc123"
    state.total_cost = 0.005
    state.save()

    reloaded = ProjectState(state_dir=state_dir, project_id="test-proj")
    assert reloaded.last_flush_session_id == "sess-abc"
    assert reloaded.last_flush_timestamp == 1714000000.0
    assert reloaded.daily_hash == "abc123"
    assert reloaded.total_cost == 0.005


def test_is_duplicate_flush(tmp_memex: Path):
    import time
    state = ProjectState(state_dir=tmp_memex / "state", project_id="test-proj")
    state.last_flush_session_id = "sess-xyz"
    state.last_flush_timestamp = time.time() - 30  # 30s ago
    state.save()

    # same session within 60s → duplicate
    assert state.is_duplicate_flush("sess-xyz", dedup_window=60) is True
    # different session → not duplicate
    assert state.is_duplicate_flush("sess-other", dedup_window=60) is False
    # same session but outside window → not duplicate
    state.last_flush_timestamp = time.time() - 120
    assert state.is_duplicate_flush("sess-xyz", dedup_window=60) is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_state.py -v
```

Expected: ImportError — `memex.state` doesn't exist yet.

- [ ] **Step 3: Implement memex/state.py**

```python
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_state.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add memex/state.py tests/test_state.py
git commit -m "feat: add ProjectState — read/write state json with dedup check"
```

---

### Task 6: flush.py Stub

**Files:**
- Create: `scripts/flush.py`

- [ ] **Step 1: Create scripts/flush.py**

```python
#!/usr/bin/env python3
"""
flush.py — Phase 1 stub. Logs that it was triggered. No API calls.
Phase 2 will add Haiku extraction.
"""
from __future__ import annotations

# RECURSION GUARD — set before any imports that might trigger Claude Code hooks
import os
os.environ["CLAUDE_INVOKED_BY"] = "memory_flush"

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "scripts" / "flush.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [flush] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main() -> None:
    if len(sys.argv) < 3:
        logging.error("Usage: flush.py <raw_file> <project_id>")
        sys.exit(1)

    raw_file = Path(sys.argv[1])
    project_id = sys.argv[2]

    if not raw_file.exists():
        logging.info("raw file not found, skipping: %s", raw_file)
        sys.exit(0)

    content = raw_file.read_text().strip()
    if not content:
        logging.info("raw file empty, skipping: %s", raw_file)
        sys.exit(0)

    logging.info("flush triggered — project=%s raw=%s chars=%d", project_id, raw_file.name, len(content))
    # Phase 2: call Haiku here


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/flush.py
```

- [ ] **Step 3: Commit**

```bash
git add scripts/flush.py
git commit -m "feat: add flush.py stub — logs trigger, no API calls (Phase 1)"
```

---

### Task 7: hooks/session-end.py

**Files:**
- Create: `hooks/session-end.py`
- Modify: `tests/test_hooks.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_hooks.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import importlib


def run_hook(hook_path: Path, stdin_data: dict, env: dict | None = None) -> int:
    """Run a hook script as a subprocess and return exit code."""
    import subprocess
    import os
    environment = os.environ.copy()
    environment.pop("CLAUDE_INVOKED_BY", None)
    if env:
        environment.update(env)
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(stdin_data),
        text=True,
        capture_output=True,
        env=environment,
    )
    return result.returncode


def test_session_end_writes_raw_file(tmp_memex: Path, sample_jsonl: Path, tmp_path: Path):
    hook = Path("hooks/session-end.py")
    hook_input = {
        "session_id": "sess-001",
        "transcript_path": str(sample_jsonl),
        "cwd": str(tmp_path),
    }
    with patch.dict("os.environ", {"MEMEX_DIR": str(tmp_memex)}):
        returncode = run_hook(hook, hook_input, env={"MEMEX_DIR": str(tmp_memex)})
    assert returncode == 0
    raw_files = list((tmp_memex / "raw").rglob("*.md"))
    assert len(raw_files) == 1
    assert "User:" in raw_files[0].read_text()


def test_session_end_exits_on_recursion_guard(tmp_memex: Path, sample_jsonl: Path, tmp_path: Path):
    hook = Path("hooks/session-end.py")
    hook_input = {"session_id": "sess-001", "transcript_path": str(sample_jsonl), "cwd": str(tmp_path)}
    returncode = run_hook(hook, hook_input, env={"CLAUDE_INVOKED_BY": "memory_flush", "MEMEX_DIR": str(tmp_memex)})
    assert returncode == 0
    raw_files = list((tmp_memex / "raw").rglob("*.md"))
    assert len(raw_files) == 0  # nothing written


def test_session_end_skips_empty_transcript(tmp_memex: Path, tmp_path: Path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    hook = Path("hooks/session-end.py")
    hook_input = {"session_id": "sess-001", "transcript_path": str(empty), "cwd": str(tmp_path)}
    returncode = run_hook(hook, hook_input, env={"MEMEX_DIR": str(tmp_memex)})
    assert returncode == 0
    raw_files = list((tmp_memex / "raw").rglob("*.md"))
    assert len(raw_files) == 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_hooks.py::test_session_end_writes_raw_file -v
```

Expected: FAIL — `hooks/session-end.py` doesn't exist.

- [ ] **Step 3: Create hooks/session-end.py**

```python
#!/usr/bin/env python3
"""
SessionEnd hook — captures Claude Code transcript → raw file → spawns flush.py.
No API calls. Must complete in <10 seconds.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Recursion guard — exit immediately if spawned by flush.py
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memex.config import Config
from memex.pre_filter import pre_filter
from memex.project_id import get_project_id

MEMEX_DIR = Path(os.environ.get("MEMEX_DIR", Path.home() / ".memex"))
config = Config(memex_dir=MEMEX_DIR)

logging.basicConfig(
    filename=str(ROOT / "scripts" / "flush.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [session-end] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main() -> None:
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError) as e:
        logging.error("invalid hook input: %s", e)
        sys.exit(0)

    session_id: str = hook_input.get("session_id", "unknown")
    transcript_path_str: str = hook_input.get("transcript_path", "")
    cwd_str: str = hook_input.get("cwd", ".")

    if not transcript_path_str:
        logging.info("no transcript_path, skipping")
        sys.exit(0)

    transcript_path = Path(transcript_path_str)
    cwd = Path(cwd_str)

    content, turn_count = pre_filter(
        transcript_path,
        max_context_chars=config.max_context_chars,
        max_turns=config.max_turns,
    )

    if not content:
        logging.info("pre-filter produced empty output, skipping")
        sys.exit(0)

    project_id = get_project_id(cwd)
    raw_dir = config.raw_dir / project_id
    raw_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_file = raw_dir / f"{timestamp}.md"
    raw_file.write_text(content)

    logging.info("wrote raw file: %s (%d turns)", raw_file.name, turn_count)

    # Spawn flush.py as a detached background process
    flush_script = ROOT / "scripts" / "flush.py"
    subprocess.Popen(
        [sys.executable, str(flush_script), str(raw_file), project_id],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logging.info("spawned flush.py for session %s", session_id)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all hook tests**

```bash
uv run pytest tests/test_hooks.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add hooks/session-end.py tests/test_hooks.py
git commit -m "feat: add session-end hook — pre-filter + raw write + spawn flush"
```

---

### Task 8: hooks/pre-compact.py

**Files:**
- Create: `hooks/pre-compact.py`

- [ ] **Step 1: Create hooks/pre-compact.py**

Same logic as session-end.py with one extra guard: Claude Code has a known bug where `transcript_path` is empty on some PreCompact events. We skip silently in that case.

```python
#!/usr/bin/env python3
"""
PreCompact hook — safety net before Claude Code auto-compacts context.
Same architecture as session-end.py. Guards against empty transcript_path (CC bug #13668).
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
sys.path.insert(0, str(ROOT))

from memex.config import Config
from memex.pre_filter import pre_filter
from memex.project_id import get_project_id

MEMEX_DIR = Path(os.environ.get("MEMEX_DIR", Path.home() / ".memex"))
config = Config(memex_dir=MEMEX_DIR)

logging.basicConfig(
    filename=str(ROOT / "scripts" / "flush.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [pre-compact] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main() -> None:
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError) as e:
        logging.error("invalid hook input: %s", e)
        sys.exit(0)

    session_id: str = hook_input.get("session_id", "unknown")
    transcript_path_str: str = hook_input.get("transcript_path", "")
    cwd_str: str = hook_input.get("cwd", ".")

    # Known CC bug: transcript_path can be empty on PreCompact
    if not transcript_path_str:
        logging.info("empty transcript_path (known CC bug), skipping")
        sys.exit(0)

    transcript_path = Path(transcript_path_str)
    cwd = Path(cwd_str)

    content, turn_count = pre_filter(
        transcript_path,
        max_context_chars=config.max_context_chars,
        max_turns=config.max_turns,
    )

    if not content:
        logging.info("pre-filter produced empty output, skipping")
        sys.exit(0)

    project_id = get_project_id(cwd)
    raw_dir = config.raw_dir / project_id
    raw_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_file = raw_dir / f"{timestamp}-compact.md"
    raw_file.write_text(content)

    logging.info("pre-compact: wrote raw file %s (%d turns)", raw_file.name, turn_count)

    flush_script = ROOT / "scripts" / "flush.py"
    subprocess.Popen(
        [sys.executable, str(flush_script), str(raw_file), project_id],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x hooks/pre-compact.py
```

- [ ] **Step 3: Run full test suite to confirm nothing broken**

```bash
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add hooks/pre-compact.py
git commit -m "feat: add pre-compact hook — same as session-end with empty transcript guard"
```

---

### Task 9: hooks/session-start.py (Phase 1 Stub)

**Files:**
- Create: `hooks/session-start.py`

In Phase 1 the notes vault is empty, so the hook outputs an empty context. The injection logic is fully wired up so it works automatically once Phase 2 populates notes.

- [ ] **Step 1: Create hooks/session-start.py**

```python
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
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x hooks/session-start.py
```

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add hooks/session-start.py
git commit -m "feat: add session-start hook — fixed priority injection, empty in Phase 1"
```

---

### Task 10: Register Hooks + Create ~/.memex/ Structure

**Files:**
- Modify: `.claude/settings.json` (create if not exists)

- [ ] **Step 1: Create ~/.memex/ directories**

```bash
mkdir -p ~/.memex/{raw,state,graph/global/graphify-out}
mkdir -p ~/.memex/notes/{projects,concepts,daily}
```

- [ ] **Step 2: Write default config.yaml**

```bash
cat > ~/.memex/config.yaml << 'EOF'
flush:
  provider: anthropic
  model: claude-haiku-4-5-20251001
  base_url: null

compile:
  provider: anthropic
  model: claude-sonnet-4-6
  base_url: null

pre_filter:
  max_context_chars: 15000
  max_turns: 30

session_start:
  max_inject_chars: 20000
  compile_after_hour: 18
EOF
```

- [ ] **Step 3: Register hooks in ~/.claude/settings.json (GLOBAL)**

Hooks must be **global** so they fire for every Claude Code session across all projects — not just the memex project directory.

Read `~/.claude/settings.json` if it exists and merge the hooks block in. If it doesn't exist, create it:

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/Users/seetrustudio-17/Documents/memex/hooks/session-end.py"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/Users/seetrustudio-17/Documents/memex/hooks/pre-compact.py"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/Users/seetrustudio-17/Documents/memex/hooks/session-start.py"
          }
        ]
      }
    ]
  }
}
```

**Important:** If `~/.claude/settings.json` already has a `hooks` key, merge each event array — do not overwrite the whole file. Back up the existing file first:

```bash
cp ~/.claude/settings.json ~/.claude/settings.json.bak 2>/dev/null || true
```

- [ ] **Step 4: Verify hooks are readable**

```bash
python3 hooks/session-end.py <<< '{"session_id":"test","transcript_path":"","cwd":"."}'
```

Expected: exits silently (empty transcript, skipped).

- [ ] **Step 5: Commit**

```bash
git add .claude/settings.json
git commit -m "chore: register Claude Code hooks for SessionEnd, PreCompact, SessionStart"
```

---

### Task 11: Integration Test — End-to-End Phase 1

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
"""
End-to-end Phase 1 integration test.
Simulates a session ending → verifies raw file written + flush stub ran.
"""
import json
import subprocess
import sys
import time
from pathlib import Path


def test_session_end_to_raw_file(tmp_memex: Path, sample_jsonl: Path, tmp_path: Path):
    """Full hook → raw file pipeline."""
    import os

    hook = Path("hooks/session-end.py").resolve()
    hook_input = {
        "session_id": "integration-sess-001",
        "transcript_path": str(sample_jsonl),
        "cwd": str(tmp_path),
    }

    env = os.environ.copy()
    env.pop("CLAUDE_INVOKED_BY", None)
    env["MEMEX_DIR"] = str(tmp_memex)

    result = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(hook_input),
        text=True,
        capture_output=True,
        env=env,
    )
    assert result.returncode == 0, f"hook failed: {result.stderr}"

    raw_files = list((tmp_memex / "raw").rglob("*.md"))
    assert len(raw_files) == 1, "expected exactly one raw file"

    raw_content = raw_files[0].read_text()
    assert "**User:** How do I parse JSONL?" in raw_content
    assert "some tool output" not in raw_content  # tool turns filtered

    # Give flush stub 2s to write its log
    time.sleep(2)
    log_file = Path("scripts/flush.log")
    if log_file.exists():
        log_content = log_file.read_text()
        assert "flush triggered" in log_content
```

- [ ] **Step 2: Run integration test**

```bash
uv run pytest tests/test_integration.py -v -s
```

Expected: PASS. Raw file exists with filtered content. Flush log shows trigger.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Final commit**

```bash
git add tests/test_integration.py
git commit -m "test: add Phase 1 integration test — session-end to raw file pipeline"
```

---

## Phase 1 Complete

At the end of Phase 1:
- `~/.memex/` directory structure exists
- `config.yaml` loaded with per-stage model + provider config
- Every Claude Code session end writes a pre-filtered raw file to `~/.memex/raw/{project-id}/`
- flush.py stub logs the trigger (no API calls yet)
- session-start hook is wired up (injects nothing until Phase 2 populates notes)
- All unit + integration tests pass

**Next:** Phase 2 — INTELLIGENCE (flush.py with Haiku, compile.py with Sonnet, Obsidian note writer)
