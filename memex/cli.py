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


@main.command()
@click.option("--memex-dir", envvar="MEMEX_DIR", default=None, type=click.Path())
def doctor(memex_dir: Optional[str]) -> None:
    """Check memex system health."""
    config = Config(memex_dir=Path(memex_dir) if memex_dir else Path.home() / ".memex")

    def row(ok: bool, name: str, detail: str) -> None:
        symbol = "✓" if ok else "✗"
        click.echo(f"  {symbol}  {name}: {detail}")

    # Notes dir
    row(
        config.notes_dir.exists(),
        "notes dir",
        str(config.notes_dir) if config.notes_dir.exists() else f"missing ({config.notes_dir})",
    )

    # graphify binary
    graphify_path = shutil.which("graphify")
    row(
        bool(graphify_path),
        "graphify",
        "installed" if graphify_path else "not installed — run: pip install graphifyy",
    )

    # hooks in ~/.claude/settings.json
    hooks_ok = False
    settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
            raw = json.dumps(settings.get("hooks", {}))
            hooks_ok = "session" in raw.lower() and "flush" in raw.lower()
        except Exception:
            pass
    row(hooks_ok, "hooks", "registered" if hooks_ok else "not registered — run: memex install")

    # Last flush / compile timestamps from state files
    last_flush: Optional[float] = None
    last_compile: Optional[float] = None
    if config.state_dir.exists():
        for f in config.state_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                ts = data.get("last_flush_timestamp")
                if ts and (last_flush is None or ts > last_flush):
                    last_flush = ts
                ts = data.get("last_compile_timestamp")
                if ts and (last_compile is None or ts > last_compile):
                    last_compile = ts
            except Exception:
                pass

    flush_str = datetime.fromtimestamp(last_flush).strftime("%Y-%m-%d %H:%M") if last_flush else "never"
    compile_str = datetime.fromtimestamp(last_compile).strftime("%Y-%m-%d %H:%M") if last_compile else "never"
    click.echo(f"  –  last flush: {flush_str}")
    click.echo(f"  –  last compile: {compile_str}")
