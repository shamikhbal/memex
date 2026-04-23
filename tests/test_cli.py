# tests/test_cli.py
import json
import pytest
from click.testing import CliRunner
from pathlib import Path
from unittest.mock import patch
from datetime import date, timedelta


def test_serve_errors_if_graphify_not_installed(tmp_memex: Path):
    from memex.cli import main
    runner = CliRunner()
    with patch("memex.cli.shutil.which", return_value=None):
        result = runner.invoke(main, ["serve", "--memex-dir", str(tmp_memex)])
    assert result.exit_code != 0
    assert "not installed" in result.output


def test_serve_errors_if_graph_json_missing(tmp_memex: Path):
    from memex.cli import main
    runner = CliRunner()
    with patch("memex.cli.shutil.which", return_value="/usr/bin/graphify"):
        result = runner.invoke(main, ["serve", "--memex-dir", str(tmp_memex)])
    assert result.exit_code != 0
    assert "graph.json not found" in result.output


def test_serve_launches_graphify_mcp_server(tmp_memex: Path):
    from memex.cli import main
    runner = CliRunner()
    graph_dir = tmp_memex / "graph" / "global" / "graphify-out"
    graph_dir.mkdir(parents=True, exist_ok=True)
    (graph_dir / "graph.json").write_text("{}")

    with patch("memex.cli.shutil.which", return_value="/usr/bin/graphify"), \
         patch("memex.cli.subprocess.run") as mock_run:
        result = runner.invoke(main, ["serve", "--memex-dir", str(tmp_memex)])

    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "-m" in cmd
    assert "graphify.serve" in cmd
    assert str(graph_dir / "graph.json") in cmd


def test_doctor_reports_graphify_not_installed(tmp_memex: Path):
    from memex.cli import main
    runner = CliRunner()
    with patch("memex.cli.shutil.which", return_value=None):
        result = runner.invoke(main, ["doctor", "--memex-dir", str(tmp_memex)])
    assert result.exit_code == 0
    assert "graphify" in result.output
    assert "not installed" in result.output


def test_doctor_reports_graphify_installed(tmp_memex: Path):
    from memex.cli import main
    runner = CliRunner()
    with patch("memex.cli.shutil.which", return_value="/usr/bin/graphify"):
        result = runner.invoke(main, ["doctor", "--memex-dir", str(tmp_memex)])
    assert result.exit_code == 0
    assert "graphify" in result.output
    assert "installed" in result.output


def test_doctor_reports_never_when_no_state(tmp_memex: Path):
    from memex.cli import main
    runner = CliRunner()
    with patch("memex.cli.shutil.which", return_value="/usr/bin/graphify"):
        result = runner.invoke(main, ["doctor", "--memex-dir", str(tmp_memex)])
    assert result.exit_code == 0
    assert "last flush" in result.output
    assert "never" in result.output


def test_doctor_reports_last_flush_timestamp(tmp_memex: Path):
    from memex.cli import main
    runner = CliRunner()
    state_dir = tmp_memex / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "test-project.json").write_text(json.dumps({
        "last_flush_session_id": "abc",
        "last_flush_timestamp": 1745280000.0,
        "last_compile_timestamp": None,
        "daily_hash": None,
        "total_cost": 0.0,
    }))
    with patch("memex.cli.shutil.which", return_value="/usr/bin/graphify"):
        result = runner.invoke(main, ["doctor", "--memex-dir", str(tmp_memex)])
    flush_line = next(ln for ln in result.output.splitlines() if "last flush" in ln)
    assert "never" not in flush_line


def test_install_creates_memex_structure(tmp_path: Path):
    from memex.cli import main
    runner = CliRunner()
    memex_dir = tmp_path / ".memex"
    (tmp_path / ".claude").mkdir()

    with patch("memex.cli.Path.home", return_value=tmp_path):
        result = runner.invoke(main, ["install", "--memex-dir", str(memex_dir)])

    assert result.exit_code == 0
    assert (memex_dir / "raw").exists()
    assert (memex_dir / "notes" / "projects").exists()
    assert (memex_dir / "config.yaml").exists()


def test_install_registers_hooks_in_settings(tmp_path: Path):
    from memex.cli import main
    runner = CliRunner()
    memex_dir = tmp_path / ".memex"
    (tmp_path / ".claude").mkdir()
    settings_path = tmp_path / ".claude" / "settings.json"

    with patch("memex.cli.Path.home", return_value=tmp_path):
        runner.invoke(main, ["install", "--memex-dir", str(memex_dir)])

    assert settings_path.exists()
    data = json.loads(settings_path.read_text())
    assert "SessionEnd" in data["hooks"]
    assert "SessionStart" in data["hooks"]
    assert "PreCompact" in data["hooks"]


def test_install_is_idempotent(tmp_path: Path):
    from memex.cli import main
    runner = CliRunner()
    memex_dir = tmp_path / ".memex"
    (tmp_path / ".claude").mkdir()

    with patch("memex.cli.Path.home", return_value=tmp_path):
        runner.invoke(main, ["install", "--memex-dir", str(memex_dir)])
        result2 = runner.invoke(main, ["install", "--memex-dir", str(memex_dir)])

    assert result2.exit_code == 0


def test_inject_returns_empty_when_no_notes(tmp_memex: Path, tmp_path: Path):
    from memex.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["inject", "--memex-dir", str(tmp_memex), "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_inject_shows_index_content(tmp_memex: Path, tmp_path: Path):
    from memex.cli import main
    runner = CliRunner()
    notes = tmp_memex / "notes" / "projects" / "test-proj"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "_index.md").write_text("project index content\n")

    with patch("memex.project_id.get_project_id", return_value="test-proj"):
        result = runner.invoke(main, ["inject", "--memex-dir", str(tmp_memex), "--cwd", str(tmp_path)])

    assert result.exit_code == 0
    assert "project index content" in result.output


def test_status_list_shows_all_projects(tmp_memex: Path):
    from memex.cli import main
    runner = CliRunner()
    notes = tmp_memex / "notes"
    today = date.today().isoformat()

    proj1 = notes / "projects" / "alpha"
    proj1.mkdir(parents=True, exist_ok=True)
    (proj1 / "decisions.md").write_text(f"## {today}\n\nDecision.\n")

    old_date = (date.today() - timedelta(days=15)).isoformat()
    proj2 = notes / "projects" / "beta"
    proj2.mkdir(parents=True, exist_ok=True)
    (proj2 / "decisions.md").write_text(f"## {old_date}\n\nOld decision.\n")

    result = runner.invoke(main, ["status", "--memex-dir", str(tmp_memex)])
    assert result.exit_code == 0
    assert "alpha" in result.output
    assert "active" in result.output
    assert "beta" in result.output
    assert "paused" in result.output


def test_status_show_single_project(tmp_memex: Path):
    from memex.cli import main
    runner = CliRunner()
    notes = tmp_memex / "notes"
    today = date.today().isoformat()
    proj = notes / "projects" / "memex"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "decisions.md").write_text(f"## {today}\n\nDecision.\n")

    result = runner.invoke(main, ["status", "--memex-dir", str(tmp_memex), "memex"])
    assert result.exit_code == 0
    assert "memex" in result.output
    assert "active" in result.output


def test_status_set_override(tmp_memex: Path):
    from memex.cli import main
    from memex.state import ProjectState
    runner = CliRunner()
    notes = tmp_memex / "notes"
    today = date.today().isoformat()
    proj = notes / "projects" / "memex"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "decisions.md").write_text(f"## {today}\n\nDecision.\n")

    result = runner.invoke(main, ["status", "--memex-dir", str(tmp_memex), "memex", "completed"])
    assert result.exit_code == 0
    assert "completed" in result.output

    state = ProjectState(state_dir=tmp_memex / "state", project_id="memex")
    assert state.status_override == "completed"


def test_status_auto_clears_override(tmp_memex: Path):
    from memex.cli import main
    from memex.state import ProjectState
    runner = CliRunner()
    notes = tmp_memex / "notes"
    today = date.today().isoformat()
    proj = notes / "projects" / "memex"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "decisions.md").write_text(f"## {today}\n\nDecision.\n")

    runner.invoke(main, ["status", "--memex-dir", str(tmp_memex), "memex", "completed"])
    result = runner.invoke(main, ["status", "--memex-dir", str(tmp_memex), "memex", "auto"])
    assert result.exit_code == 0
    assert "active" in result.output

    state = ProjectState(state_dir=tmp_memex / "state", project_id="memex")
    assert state.status_override is None
