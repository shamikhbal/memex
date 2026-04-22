# memex Phase 2 — INTELLIGENCE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flush.py stub with a real Haiku extraction pipeline that tags, routes, and appends session knowledge to the Obsidian vault, and add a compile.py that updates project index notes and triggers graphify at end-of-day.

**Architecture:** flush.py calls a thin `LLMClient` wrapper (supports anthropic + openai-compatible providers), receives structured JSON from Haiku, and delegates to `note_writer.py` which appends date-stamped content to the correct Obsidian note. compile.py runs at end-of-day: Sonnet rewrites each project's `_index.md` as a summary, then triggers `graphify --update` if installed.

**Tech Stack:** Python 3.11+, anthropic SDK, openai SDK (for OSS endpoints), PyYAML, pytest + unittest.mock

---

## File Map

```
memex/
├── llm_client.py          # CREATE: thin LLM wrapper — anthropic + openai-compatible
├── note_writer.py         # CREATE: append-only note writer with date stamps + routing
scripts/
├── flush.py               # MODIFY: replace stub with real Haiku extraction
├── compile.py             # CREATE: Sonnet _index.md updater + graphify trigger
tests/
├── test_llm_client.py     # CREATE
├── test_note_writer.py    # CREATE
├── test_flush_real.py     # CREATE (mocked LLM)
├── test_compile.py        # CREATE (mocked LLM)
pyproject.toml             # MODIFY: add openai>=1.0 dependency
```

---

### Task 1: Add openai dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read pyproject.toml**

Read `/Users/seetrustudio-17/Documents/memex/pyproject.toml` to see current dependencies.

- [ ] **Step 2: Add openai to dependencies**

In the `dependencies` list, add `"openai>=1.0"` after the existing entries:

```toml
dependencies = [
    "anthropic>=0.40.0",
    "pyyaml>=6.0",
    "click>=8.1",
    "openai>=1.0",
]
```

- [ ] **Step 3: Sync dependencies**

```bash
cd /Users/seetrustudio-17/Documents/memex && uv sync --extra dev
```

Expected: openai package installed.

- [ ] **Step 4: Verify**

```bash
/Users/seetrustudio-17/Documents/memex/.venv/bin/python -c "import openai; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add openai dependency for provider abstraction"
```

---

### Task 2: llm_client.py — Provider Abstraction

**Files:**
- Create: `memex/llm_client.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_llm_client.py
import pytest
from unittest.mock import patch, MagicMock
from memex.llm_client import LLMClient, LLMResponse


def test_llm_response_has_text():
    r = LLMResponse(text="hello")
    assert r.text == "hello"


def test_anthropic_client_calls_messages_api():
    client = LLMClient(provider="anthropic", model="claude-haiku-4-5-20251001", base_url=None)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="result text")]

    with patch("memex.llm_client.anthropic") as mock_anthropic:
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response
        result = client.complete(prompt="test prompt", max_tokens=100)

    assert result.text == "result text"
    mock_anthropic.Anthropic.return_value.messages.create.assert_called_once()
    call_kwargs = mock_anthropic.Anthropic.return_value.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
    assert call_kwargs["max_tokens"] == 100
    assert call_kwargs["messages"][0]["content"] == "test prompt"


def test_openai_compatible_client_calls_chat_api():
    client = LLMClient(provider="openai", model="gpt-4o-mini", base_url="http://localhost:11434")
    mock_choice = MagicMock()
    mock_choice.message.content = "openai result"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("memex.llm_client.openai") as mock_openai:
        mock_openai.OpenAI.return_value.chat.completions.create.return_value = mock_response
        result = client.complete(prompt="test prompt", max_tokens=200)

    assert result.text == "openai result"
    mock_openai.OpenAI.assert_called_once_with(base_url="http://localhost:11434", api_key="ollama")


def test_unknown_provider_raises():
    client = LLMClient(provider="unknown", model="x", base_url=None)
    with pytest.raises(ValueError, match="Unknown provider"):
        client.complete(prompt="hi", max_tokens=10)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/seetrustudio-17/Documents/memex && uv run pytest tests/test_llm_client.py -v
```

Expected: ImportError — `memex.llm_client` doesn't exist.

- [ ] **Step 3: Create memex/llm_client.py**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import anthropic
import openai


@dataclass
class LLMResponse:
    text: str


class LLMClient:
    def __init__(self, provider: str, model: str, base_url: Optional[str]) -> None:
        self.provider = provider
        self.model = model
        self.base_url = base_url

    def complete(self, prompt: str, max_tokens: int = 1024) -> LLMResponse:
        if self.provider == "anthropic":
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return LLMResponse(text=response.content[0].text)

        if self.provider in ("openai", "ollama"):
            client = openai.OpenAI(
                base_url=self.base_url,
                api_key="ollama",  # required by openai SDK even for local endpoints
            )
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return LLMResponse(text=response.choices[0].message.content)

        raise ValueError(f"Unknown provider: {self.provider!r}. Use 'anthropic', 'openai', or 'ollama'.")

    @classmethod
    def from_config(cls, config: object, stage: str) -> "LLMClient":
        """Create from a Config object. stage is 'flush' or 'compile'."""
        return cls(
            provider=getattr(config, f"{stage}_provider"),
            model=getattr(config, f"{stage}_model"),
            base_url=getattr(config, f"{stage}_base_url"),
        )
```

- [ ] **Step 4: Run to confirm pass**

```bash
uv run pytest tests/test_llm_client.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add memex/llm_client.py tests/test_llm_client.py
git commit -m "feat: add LLMClient — anthropic + openai-compatible provider abstraction"
```

---

### Task 3: note_writer.py — Append-Only Note Writer

**Files:**
- Create: `memex/note_writer.py`
- Create: `tests/test_note_writer.py`

The note writer receives one extracted item at a time and appends it to the correct Obsidian note, date-stamped. Never overwrites existing content.

**Routing logic:**
- `DECISION` + project_id → `notes/projects/{project_id}/decisions.md`
- `INSIGHT` + project_id → `notes/projects/{project_id}/{concept_slug}.md`
- `INSIGHT` + no project_id → `notes/daily/YYYY-MM-DD.md`
- `PATTERN` → `notes/concepts/{concept_slug}.md`
- `SKIP` → nothing written

- [ ] **Step 1: Write failing tests**

```python
# tests/test_note_writer.py
import pytest
from datetime import date
from pathlib import Path
from memex.note_writer import append_item, slugify_concept


def test_slugify_concept():
    assert slugify_concept("How to Parse JSONL") == "how-to-parse-jsonl"
    assert slugify_concept("subprocess & spawning") == "subprocess-spawning"


def test_decision_routes_to_project_decisions(tmp_memex: Path):
    notes = tmp_memex / "notes"
    append_item(
        tag="DECISION",
        content="We chose queue.jsonl over sqlite for simplicity.",
        concept="queue-design",
        project_id="my-project",
        notes_dir=notes,
        today=date(2026, 4, 22),
    )
    dest = notes / "projects" / "my-project" / "decisions.md"
    assert dest.exists()
    text = dest.read_text()
    assert "## 2026-04-22" in text
    assert "We chose queue.jsonl" in text


def test_insight_with_project_routes_to_concept_note(tmp_memex: Path):
    notes = tmp_memex / "notes"
    append_item(
        tag="INSIGHT",
        content="Use json.loads() on each line to parse JSONL.",
        concept="JSONL Parsing",
        project_id="my-project",
        notes_dir=notes,
        today=date(2026, 4, 22),
    )
    dest = notes / "projects" / "my-project" / "jsonl-parsing.md"
    assert dest.exists()
    assert "json.loads" in dest.read_text()


def test_insight_without_project_routes_to_daily(tmp_memex: Path):
    notes = tmp_memex / "notes"
    append_item(
        tag="INSIGHT",
        content="Interesting general insight.",
        concept="general",
        project_id=None,
        notes_dir=notes,
        today=date(2026, 4, 22),
    )
    dest = notes / "daily" / "2026-04-22.md"
    assert dest.exists()
    assert "general insight" in dest.read_text()


def test_pattern_routes_to_concepts(tmp_memex: Path):
    notes = tmp_memex / "notes"
    append_item(
        tag="PATTERN",
        content="Always set start_new_session=True when spawning detached processes.",
        concept="Subprocess Spawning",
        project_id="any-project",
        notes_dir=notes,
        today=date(2026, 4, 22),
    )
    dest = notes / "concepts" / "subprocess-spawning.md"
    assert dest.exists()
    assert "start_new_session" in dest.read_text()


def test_skip_writes_nothing(tmp_memex: Path):
    notes = tmp_memex / "notes"
    append_item(
        tag="SKIP",
        content="Nothing interesting.",
        concept="noise",
        project_id="proj",
        notes_dir=notes,
        today=date(2026, 4, 22),
    )
    assert not list(notes.rglob("*.md"))


def test_appends_to_existing_note(tmp_memex: Path):
    notes = tmp_memex / "notes"
    dest = notes / "concepts" / "subprocess-spawning.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("# Subprocess Spawning\n\nExisting content.\n")

    append_item(
        tag="PATTERN",
        content="New insight about spawning.",
        concept="subprocess-spawning",
        project_id=None,
        notes_dir=notes,
        today=date(2026, 4, 22),
    )
    text = dest.read_text()
    assert "Existing content." in text
    assert "New insight about spawning." in text
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_note_writer.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create memex/note_writer.py**

```python
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Optional


def slugify_concept(text: str) -> str:
    """Convert a concept name to a filesystem-safe slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def append_item(
    tag: str,
    content: str,
    concept: str,
    project_id: Optional[str],
    notes_dir: Path,
    today: Optional[date] = None,
) -> None:
    """
    Append a single extracted item to the appropriate Obsidian note.
    Always appends — never overwrites existing content.
    """
    if tag == "SKIP":
        return

    if today is None:
        today = date.today()

    date_stamp = today.isoformat()
    concept_slug = slugify_concept(concept)

    if tag == "DECISION" and project_id:
        dest = notes_dir / "projects" / project_id / "decisions.md"
    elif tag == "INSIGHT" and project_id:
        dest = notes_dir / "projects" / project_id / f"{concept_slug}.md"
    elif tag == "INSIGHT" and not project_id:
        dest = notes_dir / "daily" / f"{date_stamp}.md"
    elif tag == "PATTERN":
        dest = notes_dir / "concepts" / f"{concept_slug}.md"
    else:
        return  # unknown tag

    dest.parent.mkdir(parents=True, exist_ok=True)

    entry = f"\n\n## {date_stamp}\n\n{content.strip()}\n"

    with open(dest, "a", encoding="utf-8") as f:
        f.write(entry)
```

- [ ] **Step 4: Run to confirm pass**

```bash
uv run pytest tests/test_note_writer.py -v
```

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add memex/note_writer.py tests/test_note_writer.py
git commit -m "feat: add note_writer — append-only Obsidian note routing with date stamps"
```

---

### Task 4: scripts/flush.py — Real Haiku Extraction

**Files:**
- Modify: `scripts/flush.py`
- Create: `tests/test_flush_real.py`

Replace the Phase 1 stub with real Haiku extraction. The LLM receives the transcript, returns structured JSON, each item is appended via `note_writer`.

**Haiku prompt** — instructs the model to return JSON only:

```
You are a knowledge extraction assistant. Read the following AI coding session transcript and extract items worth remembering long-term.

For each item, assign one tag:
- DECISION: a non-obvious choice made (technology, architecture, approach) with clear rationale
- INSIGHT: something learned that would be useful next time (how-to, debugging lesson, pattern)
- PATTERN: a reusable cross-project pattern or technique
- SKIP: routine conversation, small talk, nothing worth keeping

Return ONLY valid JSON in this format:
{
  "items": [
    {
      "tag": "DECISION",
      "concept": "short concept name (3-5 words)",
      "content": "clear, self-contained description of what was decided/learned/discovered"
    }
  ]
}

If nothing is worth keeping, return: {"items": []}

Transcript:
{transcript}
```

- [ ] **Step 1: Write failing tests**

```python
# tests/test_flush_real.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from memex.llm_client import LLMResponse


def make_llm_response(items: list) -> LLMResponse:
    return LLMResponse(text=json.dumps({"items": items}))


def test_flush_writes_decision_to_notes(tmp_memex: Path, tmp_path: Path):
    """flush() extracts a DECISION and writes it to the project decisions.md."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush

    raw_content = "**User:** Should we use sqlite or jsonl?\n**Assistant:** Use jsonl for simplicity."
    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text(raw_content)

    mock_response = make_llm_response([{
        "tag": "DECISION",
        "concept": "queue storage format",
        "content": "Chose jsonl over sqlite for simplicity — no schema needed.",
    }])

    with patch("scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(
            raw_file=raw_file,
            project_id="test-project",
            memex_dir=tmp_memex,
        )

    decisions = tmp_memex / "notes" / "projects" / "test-project" / "decisions.md"
    assert decisions.exists()
    assert "jsonl over sqlite" in decisions.read_text()


def test_flush_writes_pattern_to_concepts(tmp_memex: Path, tmp_path: Path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush

    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text("**User:** How do I spawn detached?\n**Assistant:** Use start_new_session=True.")

    mock_response = make_llm_response([{
        "tag": "PATTERN",
        "concept": "detached subprocess",
        "content": "Set start_new_session=True in Popen to fully detach the child process.",
    }])

    with patch("scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    concept_note = tmp_memex / "notes" / "concepts" / "detached-subprocess.md"
    assert concept_note.exists()
    assert "start_new_session" in concept_note.read_text()


def test_flush_skips_empty_items(tmp_memex: Path, tmp_path: Path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush

    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text("**User:** hi\n**Assistant:** hello")

    mock_response = make_llm_response([])

    with patch("scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    assert not list((tmp_memex / "notes").rglob("*.md"))


def test_flush_handles_malformed_llm_response(tmp_memex: Path, tmp_path: Path):
    """If LLM returns non-JSON, flush logs and exits gracefully — no crash."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush

    raw_file = tmp_path / "20260422T120000Z.md"
    raw_file.write_text("**User:** something\n**Assistant:** something else")

    with patch("scripts.flush.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = LLMResponse(text="not json at all")
        flush(raw_file=raw_file, project_id="test-project", memex_dir=tmp_memex)

    # No crash, no notes written
    assert not list((tmp_memex / "notes").rglob("*.md"))
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_flush_real.py -v
```

Expected: ImportError — `flush` function not importable yet.

- [ ] **Step 3: Rewrite scripts/flush.py**

Replace the entire file with:

```python
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

    prompt = FLUSH_PROMPT.format(transcript=content)
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
```

- [ ] **Step 4: Run to confirm pass**

```bash
uv run pytest tests/test_flush_real.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -v
```

Expected: all tests PASS (21 existing + 4 new = 25).

- [ ] **Step 6: Commit**

```bash
git add scripts/flush.py tests/test_flush_real.py
git commit -m "feat: flush.py — real Haiku extraction with tag routing and state tracking"
```

---

### Task 5: scripts/compile.py — Index Updater + graphify Trigger

**Files:**
- Create: `scripts/compile.py`
- Create: `tests/test_compile.py`

compile.py runs at end-of-day. It uses Sonnet to write/rewrite each project's `_index.md` (a summary of the project's notes), then triggers `graphify --update` if installed.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_compile.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from memex.llm_client import LLMResponse


def test_compile_updates_index_md(tmp_memex: Path):
    """compile() writes _index.md for a project that has notes."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.compile import compile_project

    notes = tmp_memex / "notes"
    proj_dir = notes / "projects" / "my-project"
    proj_dir.mkdir(parents=True)
    (proj_dir / "decisions.md").write_text("## 2026-04-22\n\nChose jsonl over sqlite.\n")
    (proj_dir / "jsonl-parsing.md").write_text("## 2026-04-22\n\nUse json.loads() per line.\n")

    mock_response = MagicMock()
    mock_response.text = "# my-project\n\nProject uses jsonl for queue. Key insight: json.loads() per line.\n"

    with patch("scripts.compile.LLMClient") as MockClient:
        MockClient.from_config.return_value.complete.return_value = mock_response
        compile_project(project_id="my-project", memex_dir=tmp_memex)

    index = proj_dir / "_index.md"
    assert index.exists()
    assert "my-project" in index.read_text()


def test_compile_skips_project_with_no_notes(tmp_memex: Path):
    """compile() on a project with no notes writes nothing and doesn't call LLM."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.compile import compile_project

    with patch("scripts.compile.LLMClient") as MockClient:
        compile_project(project_id="empty-project", memex_dir=tmp_memex)

    MockClient.from_config.return_value.complete.assert_not_called()
    assert not (tmp_memex / "notes" / "projects" / "empty-project" / "_index.md").exists()


def test_compile_skips_graphify_if_not_installed(tmp_memex: Path):
    """compile() doesn't crash if graphify is not installed."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.compile import compile_project

    notes = tmp_memex / "notes"
    proj_dir = notes / "projects" / "my-project"
    proj_dir.mkdir(parents=True)
    (proj_dir / "decisions.md").write_text("## 2026-04-22\n\nSome decision.\n")

    mock_response = MagicMock()
    mock_response.text = "# Summary\n"

    with patch("scripts.compile.LLMClient") as MockClient, \
         patch("scripts.compile.shutil.which", return_value=None):
        MockClient.from_config.return_value.complete.return_value = mock_response
        compile_project(project_id="my-project", memex_dir=tmp_memex)
        # No crash — graphify not found, skipped silently
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_compile.py -v
```

Expected: ImportError — `scripts.compile` doesn't exist.

- [ ] **Step 3: Create scripts/compile.py**

```python
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
You are a knowledge base curator. Read all the notes below for the project "{project_id}" and write a concise _index.md — a living overview of this project.

Include:
- What the project does (1-2 sentences)
- Key decisions made (bulleted)
- Key concepts and patterns documented (bulleted)
- Current status if determinable

Be concise. Max 300 words. Use markdown. Do not include the date.

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

    prompt = INDEX_PROMPT.format(project_id=project_id, notes_content=notes_content.strip())
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
```

- [ ] **Step 4: Run to confirm pass**

```bash
uv run pytest tests/test_compile.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -v
```

Expected: all 25+ tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/compile.py tests/test_compile.py
git commit -m "feat: compile.py — Sonnet _index.md writer + graphify trigger"
```

---

### Task 6: Phase 2 Integration Test

**Files:**
- Create: `tests/test_phase2_integration.py`

End-to-end test: fake transcript → flush (mocked LLM) → note written → compile (mocked LLM) → _index.md written.

- [ ] **Step 1: Create tests/test_phase2_integration.py**

```python
# tests/test_phase2_integration.py
"""
Phase 2 integration: session transcript → flush → note → compile → _index.md
LLM calls are mocked — no API costs.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from memex.llm_client import LLMResponse


def test_full_pipeline_transcript_to_index(tmp_memex: Path, sample_jsonl: Path, tmp_path: Path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.flush import flush
    from scripts.compile import compile_project

    # Flush: LLM extracts one DECISION
    flush_response = LLMResponse(text=json.dumps({
        "items": [{
            "tag": "DECISION",
            "concept": "json parsing approach",
            "content": "Use json.loads() on each JSONL line — no streaming parser needed.",
        }]
    }))

    with patch("scripts.flush.LLMClient") as MockFlushClient:
        MockFlushClient.from_config.return_value.complete.return_value = flush_response
        # Also patch subprocess.Popen so compile.py isn't spawned for real
        with patch("scripts.flush.subprocess.Popen"):
            flush(
                raw_file=sample_jsonl,
                project_id="integration-project",
                memex_dir=tmp_memex,
            )

    decisions = tmp_memex / "notes" / "projects" / "integration-project" / "decisions.md"
    assert decisions.exists(), "flush should have written decisions.md"
    assert "json.loads" in decisions.read_text()

    # Compile: LLM writes _index.md
    compile_response = LLMResponse(text="# integration-project\n\nUses json.loads() for JSONL parsing.\n")

    with patch("scripts.compile.LLMClient") as MockCompileClient, \
         patch("scripts.compile.shutil.which", return_value=None):
        MockCompileClient.from_config.return_value.complete.return_value = compile_response
        compile_project(project_id="integration-project", memex_dir=tmp_memex)

    index = tmp_memex / "notes" / "projects" / "integration-project" / "_index.md"
    assert index.exists(), "compile should have written _index.md"
    assert "json.loads" in index.read_text()
```

- [ ] **Step 2: Run integration test**

```bash
uv run pytest tests/test_phase2_integration.py -v -s
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

```bash
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_phase2_integration.py
git commit -m "test: Phase 2 integration — transcript to decisions.md to _index.md"
```

---

## Phase 2 Complete

At the end of Phase 2:
- Every session end: Haiku reads the raw transcript, extracts tagged items, appends them to the correct Obsidian note (date-stamped, append-only)
- Past 18:00 with new content: Sonnet writes/updates each project's `_index.md`, graphify runs if installed
- session-start hook already injects from these notes (wired in Phase 1)
- Full test coverage with mocked LLM — no API costs in CI

**Next:** Phase 3 — GRAPH (graphify integration, MCP server wiring)
