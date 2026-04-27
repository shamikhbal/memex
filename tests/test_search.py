# tests/test_search.py
import pytest
from pathlib import Path
from memex.search import search, SearchResult, Hit, _extract_heading, _build_snippet


def make_vault(notes_dir: Path) -> None:
    """Set up a minimal vault for search testing."""
    (notes_dir / "concepts").mkdir(parents=True, exist_ok=True)
    (notes_dir / "daily").mkdir(parents=True, exist_ok=True)
    (notes_dir / "projects" / "my-project").mkdir(parents=True, exist_ok=True)

    (notes_dir / "concepts" / "python.md").write_text(
        "# Python\n\n## Debugging\n\nUse pdb for interactive debugging.\n## Performance\n\nUse cProfile for profiling.\n"
    )
    (notes_dir / "concepts" / "git.md").write_text(
        "# Git\n\n## Workflow\n\nAlways branch off main and use rebase.\n"
    )
    (notes_dir / "projects" / "my-project" / "decisions.md").write_text(
        "# Decisions\n\n## 2026-04-22\n\nChose PostgreSQL over MongoDB for relational integrity.\n"
    )
    (notes_dir / "daily" / f"2026-04-22.md").write_text(
        "# Daily\n\nWorked on database migration scripts.\n"
    )


def test_search_finds_single_match(tmp_memex: Path):
    make_vault(tmp_memex / "notes")
    result = search(tmp_memex / "notes", "pdb")
    assert len(result.hits) == 1
    assert result.hits[0].file == "concepts/python.md"


def test_search_finds_multiple_matches(caplog, tmp_memex: Path):
    import logging
    caplog.set_level(logging.WARNING)
    make_vault(tmp_memex / "notes")
    result = search(tmp_memex / "notes", "PostgreSQL")
    # Should match decisions.md
    hits = [h for h in result.hits if "PostgreSQL" in h.line]
    assert len(hits) >= 1
    assert any("decisions.md" in h.file for h in hits)


def test_search_no_matches(tmp_memex: Path):
    make_vault(tmp_memex / "notes")
    result = search(tmp_memex / "notes", "nonexistent")
    assert len(result.hits) == 0
    assert result.file_count == 0


def test_search_respects_max_results(tmp_memex: Path):
    make_vault(tmp_memex / "notes")
    (tmp_memex / "notes" / "concepts" / "many.md").write_text(
        "\n".join([f"Line {i} mentioning pdb here" for i in range(30)])
    )
    result = search(tmp_memex / "notes", "pdb", max_results=5)
    assert len(result.hits) == 5


def test_search_project_specific(tmp_memex: Path):
    make_vault(tmp_memex / "notes")
    result = search(tmp_memex / "notes", "PostgreSQL", project_id="my-project")
    assert len(result.hits) >= 1
    # Should only find hits in my-project files
    for hit in result.hits:
        assert "my-project" in hit.file


def test_search_returns_empty_for_missing_notes_dir(tmp_path: Path):
    result = search(tmp_path / "nonexistent", "anything")
    assert len(result.hits) == 0


def test_extract_heading_finds_closest():
    lines = [
        "## Introduction",
        "Some text.",
        "## Debugging",
        "More text.",
        "Hit here.",
    ]
    assert _extract_heading(lines, 4) == "Debugging"


def test_extract_heading_returns_top_for_no_heading():
    lines = ["Some text without heading.", "Hit here."]
    assert _extract_heading(lines, 1) == "(top)"


def test_build_snippet_bolds_query():
    result = _build_snippet("Use pdb for interactive debugging.", "pdb")
    assert "**pdb**" in result


def test_build_snippet_handles_multiword_query():
    result = _build_snippet("Interactive debugging with pdb tool.", "pdb")
    assert "**pdb**" in result


def test_search_result_properties():
    r = SearchResult(query="test")
    r.hits = [
        Hit(file="a.md", path=Path("a.md"), heading="h1", line="x", line_number=1, snippet="x"),
        Hit(file="a.md", path=Path("a.md"), heading="h2", line="y", line_number=2, snippet="y"),
        Hit(file="b.md", path=Path("b.md"), heading="h3", line="z", line_number=1, snippet="z"),
    ]
    assert r.file_count == 2
    assert len(r.hits) == 3
