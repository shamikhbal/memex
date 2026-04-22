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
