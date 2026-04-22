# tests/test_cli.py
import json
import pytest
from click.testing import CliRunner
from pathlib import Path
from unittest.mock import patch


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
