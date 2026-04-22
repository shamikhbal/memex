from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from memex.config import Config


@click.group()
def main() -> None:
    """memex — personal memory system."""
    pass


@main.command()
@click.option("--memex-dir", envvar="MEMEX_DIR", default=None, type=click.Path())
def serve(memex_dir: Optional[str]) -> None:
    """Start the graphify MCP server (stdio)."""
    config = Config(memex_dir=Path(memex_dir) if memex_dir else Path.home() / ".memex")
    graph_json = config.graph_dir / "graph.json"

    if not shutil.which("graphify"):
        click.echo("ERROR: graphify not installed. Run: pip install graphifyy", err=True)
        sys.exit(1)

    if not graph_json.exists():
        click.echo(
            f"ERROR: graph.json not found at {graph_json}. Run 'memex compile' first.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Starting graphify MCP server ({graph_json}) ...")
    subprocess.run([sys.executable, "-m", "graphify.serve", str(graph_json)])
