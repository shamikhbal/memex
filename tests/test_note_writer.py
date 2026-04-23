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


def test_explore_with_project_routes_to_explore_file(tmp_memex: Path):
    notes = tmp_memex / "notes"
    append_item(
        tag="EXPLORE",
        content="What if we used GraphQL instead of REST?",
        concept="API Design Ideas",
        project_id="my-project",
        notes_dir=notes,
        today=date(2026, 4, 23),
        related=["rest-api"],
        extra_tags=["tech/graphql"],
    )
    dest = notes / "projects" / "my-project" / "explore-api-design-ideas.md"
    assert dest.exists()
    text = dest.read_text()
    assert "type/exploration" in text
    assert "GraphQL" in text
    assert "## 2026-04-23" in text


def test_explore_without_project_routes_to_daily(tmp_memex: Path):
    notes = tmp_memex / "notes"
    append_item(
        tag="EXPLORE",
        content="Random brainstorm about tooling.",
        concept="tooling-ideas",
        project_id=None,
        notes_dir=notes,
        today=date(2026, 4, 23),
    )
    dest = notes / "daily" / "2026-04-23.md"
    assert dest.exists()
    assert "tooling" in dest.read_text()


def test_target_project_routes_decision_to_matched_project(tmp_memex: Path):
    notes = tmp_memex / "notes"
    (notes / "projects" / "memex").mkdir(parents=True, exist_ok=True)
    append_item(
        tag="DECISION",
        content="Use sqlite for queue.",
        concept="queue-storage",
        project_id=None,
        notes_dir=notes,
        today=date(2026, 4, 23),
        target_project="memex",
    )
    dest = notes / "projects" / "memex" / "decisions.md"
    assert dest.exists()
    assert "sqlite" in dest.read_text()


def test_target_project_falls_back_to_daily_if_not_found(tmp_memex: Path):
    notes = tmp_memex / "notes"
    append_item(
        tag="DECISION",
        content="Use sqlite for something.",
        concept="queue-storage",
        project_id=None,
        notes_dir=notes,
        today=date(2026, 4, 23),
        target_project="nonexistent-project",
    )
    assert not (notes / "projects" / "nonexistent-project").exists()
    dest = notes / "daily" / "2026-04-23.md"
    assert dest.exists()
    assert "sqlite" in dest.read_text()


def test_target_project_routes_insight_to_matched_project(tmp_memex: Path):
    notes = tmp_memex / "notes"
    (notes / "projects" / "memex").mkdir(parents=True, exist_ok=True)
    append_item(
        tag="INSIGHT",
        content="Path.resolve() is needed before .name.",
        concept="path-resolution",
        project_id=None,
        notes_dir=notes,
        today=date(2026, 4, 23),
        target_project="memex",
    )
    dest = notes / "projects" / "memex" / "path-resolution.md"
    assert dest.exists()
    assert "resolve()" in dest.read_text()
