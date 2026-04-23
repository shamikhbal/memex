# tests/test_inject.py
import json
import pytest
from datetime import date, timedelta
from pathlib import Path

from memex.config import Config
from memex.inject import build_context, _read_capped_lines, _tier_budget


# ── helpers ─────────────────────────────────────────────────────────────────

def make_notes(tmp_memex: Path, project_id: str = "test-proj") -> Path:
    notes = tmp_memex / "notes"
    proj = notes / "projects" / project_id
    proj.mkdir(parents=True, exist_ok=True)
    (notes / "concepts").mkdir(parents=True, exist_ok=True)
    (notes / "daily").mkdir(parents=True, exist_ok=True)
    return notes


# ── _read_capped_lines ───────────────────────────────────────────────────────

def test_read_capped_lines_returns_empty_for_missing_file(tmp_path: Path):
    text, used = _read_capped_lines(tmp_path / "nope.md", 1000)
    assert text == ""
    assert used == 0


def test_read_capped_lines_truncates_at_line_boundary(tmp_path: Path):
    f = tmp_path / "test.md"
    f.write_text("line one\nline two\nline three\n")
    text, used = _read_capped_lines(f, 15)  # "line one\n" = 9 chars fits; "line two\n" = 9 → 18 > 15
    assert text == "line one\n"
    assert used == 9


def test_read_capped_lines_full_content_when_under_budget(tmp_path: Path):
    f = tmp_path / "test.md"
    f.write_text("short\n")
    text, used = _read_capped_lines(f, 1000)
    assert text == "short\n"
    assert used == 6


# ── _tier_budget ─────────────────────────────────────────────────────────────

def test_tier_budget_project_is_50_percent():
    assert _tier_budget(20000, "project") == 10000


def test_tier_budget_daily_is_20_percent():
    assert _tier_budget(20000, "daily") == 4000


def test_tier_budget_index_is_35_percent():
    assert _tier_budget(20000, "index") == 7000


def test_tier_budget_decisions_is_15_percent():
    assert _tier_budget(20000, "decisions") == 3000


# ── build_context ────────────────────────────────────────────────────────────

def test_build_context_returns_empty_when_no_notes(tmp_memex: Path):
    cfg = Config(memex_dir=tmp_memex)
    result = build_context(cfg, "test-proj")
    assert result == ""


def test_build_context_includes_index_and_decisions(tmp_memex: Path):
    notes = make_notes(tmp_memex)
    today = date.today().isoformat()
    (notes / "projects" / "test-proj" / "_index.md").write_text("project summary\n")
    (notes / "projects" / "test-proj" / "decisions.md").write_text(f"## {today}\n\narch decision\n")
    cfg = Config(memex_dir=tmp_memex)
    result = build_context(cfg, "test-proj")
    assert "project summary" in result
    assert "arch decision" in result


def test_build_context_includes_todays_daily(tmp_memex: Path):
    notes = make_notes(tmp_memex)
    today = date.today().isoformat()
    (notes / "daily" / f"{today}.md").write_text("daily entry\n")
    cfg = Config(memex_dir=tmp_memex)
    result = build_context(cfg, "test-proj")
    assert "daily entry" in result


def test_build_context_project_budget_caps_index(tmp_memex: Path):
    notes = make_notes(tmp_memex)
    # Write an _index.md larger than 35% of max_inject_chars (default 20000 → 7000)
    big_content = "x\n" * 4000  # 8000 chars
    (notes / "projects" / "test-proj" / "_index.md").write_text(big_content)
    cfg = Config(memex_dir=tmp_memex)
    result = build_context(cfg, "test-proj")
    # index section should be capped at ~7000 chars
    index_section = [s for s in result.split("---") if "_index.md" in s][0]
    assert len(index_section) < 8000


def test_build_context_concepts_appear_after_project_and_daily(tmp_memex: Path):
    notes = make_notes(tmp_memex)
    (notes / "projects" / "test-proj" / "_index.md").write_text("project summary\n")
    (notes / "concepts" / "python.md").write_text("python concept\n")
    cfg = Config(memex_dir=tmp_memex)
    result = build_context(cfg, "test-proj")
    assert "project summary" in result
    assert "python concept" in result
    assert result.index("project summary") < result.index("python concept")


# ── graph-aware concept scoring ───────────────────────────────────────────────

def test_build_context_graph_orders_concepts_by_degree(tmp_memex: Path):
    """Concept files with more graph edges appear first."""
    notes = make_notes(tmp_memex)
    (notes / "concepts" / "low.md").write_text("low degree concept\n")
    (notes / "concepts" / "high.md").write_text("high degree concept\n")

    graph_dir = tmp_memex / "graph" / "global" / "graphify-out"
    graph_dir.mkdir(parents=True, exist_ok=True)
    graph_json = graph_dir / "graph.json"
    graph_json.write_text(json.dumps({
        "nodes": [
            {"id": "low-node", "path": "low.md"},
            {"id": "high-node", "path": "high.md"},
        ],
        "edges": [
            {"source": "high-node", "target": "other1"},
            {"source": "high-node", "target": "other2"},
            {"source": "low-node", "target": "other1"},
        ],
    }))

    cfg = Config(memex_dir=tmp_memex)
    result = build_context(cfg, "test-proj", graph_json=graph_json)
    assert result.index("high degree concept") < result.index("low degree concept")


def test_build_context_falls_back_to_mtime_on_bad_graph(tmp_memex: Path):
    """If graph.json is malformed, concept selection falls back to mtime ordering."""
    import time
    notes = make_notes(tmp_memex)
    p1 = notes / "concepts" / "older.md"
    p1.write_text("older concept\n")
    time.sleep(0.05)
    p2 = notes / "concepts" / "newer.md"
    p2.write_text("newer concept\n")

    graph_dir = tmp_memex / "graph" / "global" / "graphify-out"
    graph_dir.mkdir(parents=True, exist_ok=True)
    bad_graph = graph_dir / "graph.json"
    bad_graph.write_text("not valid json {{{{")

    cfg = Config(memex_dir=tmp_memex)
    result = build_context(cfg, "test-proj", graph_json=bad_graph)
    assert result.index("newer concept") < result.index("older concept")


# ── status-aware budget ───────────────────────────────────────────────────────

def test_build_context_active_includes_all_tiers(tmp_memex: Path):
    """Active project gets full budget: index + decisions."""
    from memex.inject import build_context
    config = Config(memex_dir=tmp_memex)
    notes = tmp_memex / "notes"
    proj = notes / "projects" / "test-proj"
    proj.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    (proj / "_index.md").write_text("Project overview.\n")
    (proj / "decisions.md").write_text(f"## {today}\n\nA decision.\n")
    context = build_context(config, "test-proj")
    assert "Project overview" in context
    assert "A decision" in context


def test_build_context_paused_includes_index_only(tmp_memex: Path):
    """Paused project gets index only, no decisions."""
    from memex.inject import build_context
    config = Config(memex_dir=tmp_memex)
    notes = tmp_memex / "notes"
    proj = notes / "projects" / "test-proj"
    proj.mkdir(parents=True, exist_ok=True)
    old_date = (date.today() - timedelta(days=15)).isoformat()
    (proj / "_index.md").write_text("Project overview.\n")
    (proj / "decisions.md").write_text(f"## {old_date}\n\nAn old decision.\n")
    context = build_context(config, "test-proj")
    assert "Project overview" in context
    assert "An old decision" not in context


def test_build_context_dormant_includes_index_capped(tmp_memex: Path):
    """Dormant project gets index at half budget."""
    from memex.inject import build_context
    config = Config(memex_dir=tmp_memex)
    notes = tmp_memex / "notes"
    proj = notes / "projects" / "test-proj"
    proj.mkdir(parents=True, exist_ok=True)
    old_date = (date.today() - timedelta(days=60)).isoformat()
    long_content = "x" * 10000 + "\n"
    (proj / "_index.md").write_text(long_content)
    (proj / "decisions.md").write_text(f"## {old_date}\n\nVery old decision.\n")
    context = build_context(config, "test-proj")
    assert len(context) < _tier_budget(config.max_inject_chars, "index")
    assert "Very old decision" not in context
