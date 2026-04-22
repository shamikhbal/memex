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
