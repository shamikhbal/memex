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
from memex.installer import create_memex_dir, merge_hooks, remove_hooks, write_default_config


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
            hooks_ok = "session-end" in raw and "session-start" in raw
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


@main.command()
@click.option("--memex-dir", envvar="MEMEX_DIR", default=None, type=click.Path())
@click.option("--cwd", default=".", type=click.Path(), help="Project directory (defaults to CWD)")
def inject(memex_dir: Optional[str], cwd: str) -> None:
    """Preview what session-start would inject into the context window."""
    from memex.inject import build_context
    from memex.project_id import get_project_id

    config = Config(memex_dir=Path(memex_dir) if memex_dir else Path.home() / ".memex")
    project_id = get_project_id(Path(cwd))
    graph_json = config.graph_dir / "graph.json"

    context = build_context(
        config,
        project_id,
        graph_json=graph_json if graph_json.exists() else None,
    )
    if context:
        click.echo(context)


@main.command()
@click.option("--memex-dir", envvar="MEMEX_DIR", default=None, type=click.Path())
@click.argument("question", nargs=-1, required=True)
def query(memex_dir: Optional[str], question: tuple[str, ...]) -> None:
    """Query the knowledge graph. Usage: memex query what decisions were made?"""
    config = Config(memex_dir=Path(memex_dir) if memex_dir else Path.home() / ".memex")
    graph_json = config.graph_dir / "graph.json"

    if not graph_json.exists():
        click.echo(f"  ✗  graph.json not found at {graph_json}. Run 'memex compile' first.", err=True)
        sys.exit(1)

    subprocess.run(["graphify", "query", " ".join(question), "--graph", str(graph_json)])


@main.command()
@click.option("--memex-dir", envvar="MEMEX_DIR", default=None, type=click.Path())
@click.argument("nodes", nargs=2, required=True)
def path(memex_dir: Optional[str], nodes: tuple[str, str]) -> None:
    """Find shortest path between two nodes. Usage: memex path "node A" "node B" """
    config = Config(memex_dir=Path(memex_dir) if memex_dir else Path.home() / ".memex")
    graph_json = config.graph_dir / "graph.json"

    if not graph_json.exists():
        click.echo(f"  ✗  graph.json not found at {graph_json}. Run 'memex compile' first.", err=True)
        sys.exit(1)

    subprocess.run(["graphify", "path", nodes[0], nodes[1], "--graph", str(graph_json)])


@main.command()
@click.option("--memex-dir", envvar="MEMEX_DIR", default=None, type=click.Path())
@click.argument("node", required=True)
def explain(memex_dir: Optional[str], node: str) -> None:
    """Explain a node and its neighbors. Usage: memex explain "hook installer" """
    config = Config(memex_dir=Path(memex_dir) if memex_dir else Path.home() / ".memex")
    graph_json = config.graph_dir / "graph.json"

    if not graph_json.exists():
        click.echo(f"  ✗  graph.json not found at {graph_json}. Run 'memex compile' first.", err=True)
        sys.exit(1)

    subprocess.run(["graphify", "explain", node, "--graph", str(graph_json)])


@main.command()
@click.option("--memex-dir", envvar="MEMEX_DIR", default=None, type=click.Path())
@click.argument("project_id", required=False)
def compile(memex_dir: Optional[str], project_id: Optional[str]) -> None:
    """Compile project notes into _index.md and update the knowledge graph."""
    from memex.project_id import get_project_id
    from memex.scripts.compile import compile_project

    resolved_memex = Path(memex_dir) if memex_dir else Path.home() / ".memex"

    if not project_id:
        project_id = get_project_id(Path.cwd())

    click.echo(f"  compiling project: {project_id}")
    compile_project(project_id=project_id, memex_dir=resolved_memex)
    click.echo(f"  ✓  done")


_VALID_STATUSES = {"active", "paused", "dormant", "completed"}


@main.command()
@click.option("--memex-dir", envvar="MEMEX_DIR", default=None, type=click.Path())
@click.argument("project_id", required=False)
@click.argument("new_status", required=False)
def status(memex_dir: Optional[str], project_id: Optional[str], new_status: Optional[str]) -> None:
    """Show or set project status. Usage: memex status [PROJECT] [STATUS|auto]"""
    from memex.state import ProjectState

    config = Config(memex_dir=Path(memex_dir) if memex_dir else Path.home() / ".memex")
    projects_dir = config.notes_dir / "projects"

    if not projects_dir.exists():
        click.echo("No projects found.")
        return

    # Set or clear override
    if project_id and new_status:
        state = ProjectState(state_dir=config.state_dir, project_id=project_id)
        if new_status == "auto":
            state.clear_override()
            state.save()
            derived = state.derive_status(config.notes_dir)
            click.echo(f"  {project_id}: override cleared -> {derived}")
        elif new_status in _VALID_STATUSES:
            state.set_override(new_status)
            state.save()
            click.echo(f"  {project_id}: set to {new_status}")
        else:
            click.echo(f"Invalid status: {new_status}. Use: {', '.join(sorted(_VALID_STATUSES))}, or auto", err=True)
            sys.exit(1)
        return

    # Show single project
    if project_id:
        state = ProjectState(state_dir=config.state_dir, project_id=project_id)
        derived = state.derive_status(config.notes_dir)
        latest = state._latest_note_date(config.notes_dir)
        latest_str = latest.isoformat() if latest else "never"
        override_marker = " (override)" if state.status_override else ""
        click.echo(f"  {project_id}: {derived}{override_marker}  last activity: {latest_str}")
        return

    # List all projects
    project_dirs = sorted(d.name for d in projects_dir.iterdir() if d.is_dir())
    if not project_dirs:
        click.echo("No projects found.")
        return

    click.echo(f"  {'Project':<20} {'Status':<12} {'Last Activity'}")
    for pid in project_dirs:
        state = ProjectState(state_dir=config.state_dir, project_id=pid)
        derived = state.derive_status(config.notes_dir)
        latest = state._latest_note_date(config.notes_dir)
        latest_str = latest.isoformat() if latest else "never"
        click.echo(f"  {pid:<20} {derived:<12} {latest_str}")


@main.command()
@click.option("--memex-dir", envvar="MEMEX_DIR", default=None, type=click.Path())
def install(memex_dir: Optional[str]) -> None:
    """Create ~/.memex/ structure and register Claude Code hooks."""
    resolved_memex = Path(memex_dir) if memex_dir else Path.home() / ".memex"
    hooks_dir = Path(__file__).parent / "hooks"
    hook_commands = {
        "SessionEnd": f"{sys.executable} {hooks_dir / 'session-end.py'}",
        "PreCompact": f"{sys.executable} {hooks_dir / 'pre-compact.py'}",
        "SessionStart": f"{sys.executable} {hooks_dir / 'session-start.py'}",
    }
    settings_path = Path.home() / ".claude" / "settings.json"

    created_dirs = create_memex_dir(resolved_memex)
    if created_dirs:
        for d in created_dirs:
            click.echo(f"  \u2713  created {d}")
    else:
        click.echo("  \u2013  ~/.memex/ directories already exist")

    wrote_config = write_default_config(resolved_memex)
    if wrote_config:
        click.echo(f"  \u2713  wrote {resolved_memex / 'config.yaml'}")
    else:
        click.echo(f"  \u2013  config.yaml already exists, skipped")

    hooks_changed = merge_hooks(settings_path, hook_commands)
    if hooks_changed:
        click.echo(f"  \u2713  registered hooks in {settings_path}")
    else:
        click.echo(f"  \u2013  hooks already registered in {settings_path}")

    click.echo("\nmemex install complete. Start a new Claude Code session to activate.")


@main.command()
@click.option("--memex-dir", envvar="MEMEX_DIR", default=None, type=click.Path())
@click.option(
    "--delete-data",
    is_flag=True,
    default=False,
    help="Also delete ~/.memex/ (notes, raw transcripts, state). Cannot be undone.",
)
@click.confirmation_option(prompt="Remove memex hooks from Claude Code settings?")
def uninstall(memex_dir: Optional[str], delete_data: bool) -> None:
    """Remove memex hooks from Claude Code settings (and optionally delete ~/.memex/)."""
    hooks_dir = Path(__file__).parent / "hooks"
    hook_commands = {
        "SessionEnd": f"{sys.executable} {hooks_dir / 'session-end.py'}",
        "PreCompact": f"{sys.executable} {hooks_dir / 'pre-compact.py'}",
        "SessionStart": f"{sys.executable} {hooks_dir / 'session-start.py'}",
    }
    settings_path = Path.home() / ".claude" / "settings.json"

    hooks_changed = remove_hooks(settings_path, hook_commands)
    if hooks_changed:
        click.echo(f"  ✓  removed hooks from {settings_path}")
    else:
        click.echo(f"  –  no memex hooks found in {settings_path}")

    if delete_data:
        resolved_memex = Path(memex_dir) if memex_dir else Path.home() / ".memex"
        if resolved_memex.exists():
            shutil.rmtree(resolved_memex)
            click.echo(f"  ✓  deleted {resolved_memex}")
        else:
            click.echo(f"  –  {resolved_memex} not found, skipped")
    else:
        resolved_memex = Path(memex_dir) if memex_dir else Path.home() / ".memex"
        click.echo(f"  –  kept {resolved_memex} (pass --delete-data to remove)")

    click.echo("\nmemex uninstalled. Restart Claude Code for changes to take effect.")
