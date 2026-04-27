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
@click.option("--project", "-p", default=None, help="Limit search to a specific project")
@click.option("--max", "-n", default=20, type=int, help="Maximum results (default: 20)")
@click.argument("question", nargs=-1, required=True)
def recall(memex_dir: Optional[str], project: Optional[str], max: int, question: tuple[str, ...]) -> None:
    """Search vault notes for keyword matches. Usage: memex recall "deployment strategy" """
    from memex.search import search

    config = Config(memex_dir=Path(memex_dir) if memex_dir else Path.home() / ".memex")
    query_text = " ".join(question)
    result = search(config.notes_dir, query_text, project_id=project, max_results=max)

    if not result.hits:
        click.echo(f"  No matches found for '{query_text}'.")
        return

    click.echo(f"  Found {result.file_count} file(s) — {len(result.hits)} hits:")
    for hit in result.hits:
        heading_display = f" ({hit.heading})" if hit.heading != "(top)" else ""
        click.echo(f"    {hit.file}:{hit.line_number}{heading_display}")
        click.echo(f"      {hit.snippet}")
    click.echo()


@main.command()
@click.option("--memex-dir", envvar="MEMEX_DIR", default=None, type=click.Path())
@click.option("--project", "-p", default=None, help="Limit search to a specific project")
@click.argument("question", nargs=-1, required=True)
def search(memex_dir: Optional[str], project: Optional[str], question: tuple[str, ...]) -> None:
    """Alias for 'recall'. Search vault notes for keyword matches."""
    # Delegate to recall handler
    from memex.search import search as do_search

    config = Config(memex_dir=Path(memex_dir) if memex_dir else Path.home() / ".memex")
    query_text = " ".join(question)
    result = do_search(config.notes_dir, query_text, project_id=project)

    if not result.hits:
        click.echo(f"  No matches found for '{query_text}'.")
        return

    click.echo(f"  Found {result.file_count} file(s) — {len(result.hits)} hits:")
    for hit in result.hits:
        heading_display = f" ({hit.heading})" if hit.heading != "(top)" else ""
        click.echo(f"    {hit.file}:{hit.line_number}{heading_display}")
        click.echo(f"      {hit.snippet}")
    click.echo()


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


def _interactive_platform_select() -> str:
    """Prompt user to choose which AI platform(s) to install hooks for."""
    click.echo()
    click.echo("  memex — personal memory system")
    click.echo("  Install hooks for your AI coding agent:")
    click.echo()

    # Detect existing installations
    cc_exists = (Path.home() / ".claude" / "settings.json").exists()
    cc_has_memex = False
    if cc_exists:
        try:
            data = json.loads((Path.home() / ".claude" / "settings.json").read_text())
            raw = json.dumps(data.get("hooks", {}))
            cc_has_memex = "session-end" in raw and "session-start" in raw
        except Exception:
            pass

    fd_exists = (Path.home() / ".factory" / "settings.json").exists()
    fd_has_memex = False
    if fd_exists:
        try:
            data = json.loads((Path.home() / ".factory" / "settings.json").read_text())
            raw = json.dumps(data.get("hooks", {}))
            fd_has_memex = "session-end" in raw and "session-start" in raw
        except Exception:
            pass

    cc_label = "Claude Code"
    if cc_has_memex:
        cc_label += " (already installed)"
    elif cc_exists:
        cc_label += " (hooks config exists)"

    fd_label = "Factory Droid"
    if fd_has_memex:
        fd_label += " (already installed + skill)"
    elif fd_exists:
        fd_label += " (hooks config exists)"

    click.echo(f"  1. {cc_label}")
    click.echo(f"  2. {fd_label}")
    click.echo("  3. Both")
    click.echo()

    choice = click.prompt(
        "  Select platform",
        type=click.Choice(["1", "2", "3"]),
        default="1",
        show_choices=False,
    )
    click.echo()
    return {"1": "claude", "2": "factory", "3": "all"}[choice]


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
@click.option(
    "--platform",
    default=None,
    type=click.Choice(["claude", "factory", "all"], case_sensitive=False),
    help="Target AI platform. If omitted, prompts interactively.",
)
def install(memex_dir: Optional[str], platform: Optional[str]) -> None:
    """Create ~/.memex/ structure and register hooks with your AI platform."""
    resolved_memex = Path(memex_dir) if memex_dir else Path.home() / ".memex"
    hooks_dir = Path(__file__).parent / "hooks"
    hook_commands = {
        "SessionEnd": f"{sys.executable} {hooks_dir / 'session-end.py'}",
        "PreCompact": f"{sys.executable} {hooks_dir / 'pre-compact.py'}",
        "SessionStart": f"{sys.executable} {hooks_dir / 'session-start.py'}",
    }

    # Interactive platform selection (only when running in a real terminal)
    if platform is None:
        if sys.stdin.isatty():
            platform = _interactive_platform_select()
        else:
            platform = "claude"

    platforms: list[str] = ["claude", "factory"] if platform == "all" else [platform]

    # Create directory structure (once)
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

    # Install hooks for each platform
    for p in platforms:
        if p == "factory":
            settings_path = Path.home() / ".factory" / "settings.json"
            platform_label = "factory (Droid)"
        else:
            settings_path = Path.home() / ".claude" / "settings.json"
            platform_label = "claude"

        hooks_changed = merge_hooks(settings_path, hook_commands)
        if hooks_changed:
            click.echo(f"  \u2713  registered hooks in {settings_path} ({platform_label})")
        else:
            click.echo(f"  \u2013  hooks already registered in {settings_path} ({platform_label})")

        # Copy memex SKILL to Factory skills directory
        if p == "factory":
            skill_src = Path(__file__).parent.parent / ".factory" / "skills" / "memex"
            skill_dst = Path.home() / ".factory" / "skills" / "memex"
            if skill_src.exists() and not skill_dst.exists():
                shutil.copytree(skill_src, skill_dst)
                click.echo(f"  \u2713  installed memex skill to {skill_dst}")
            elif skill_dst.exists():
                click.echo(f"  \u2013  memex skill already installed ({skill_dst})")

    click.echo("\nmemex install complete. Start a new session to activate.")


@main.command()
@click.option("--memex-dir", envvar="MEMEX_DIR", default=None, type=click.Path())
@click.option(
    "--platform",
    default=None,
    type=click.Choice(["claude", "factory", "all"], case_sensitive=False),
    help="Target AI platform. If omitted, prompts interactively.",
)
@click.option(
    "--delete-data",
    is_flag=True,
    default=False,
    help="Also delete ~/.memex/ (notes, raw transcripts, state). Cannot be undone.",
)
@click.confirmation_option(prompt="Remove memex hooks from your AI platform settings?")
def uninstall(memex_dir: Optional[str], platform: Optional[str], delete_data: bool) -> None:
    """Remove memex hooks from platform settings (and optionally delete ~/.memex/)."""
    hooks_dir = Path(__file__).parent / "hooks"
    hook_commands = {
        "SessionEnd": f"{sys.executable} {hooks_dir / 'session-end.py'}",
        "PreCompact": f"{sys.executable} {hooks_dir / 'pre-compact.py'}",
        "SessionStart": f"{sys.executable} {hooks_dir / 'session-start.py'}",
    }

    if platform is None:
        if sys.stdin.isatty():
            platform = _interactive_platform_select()
        else:
            platform = "claude"

    platforms: list[str] = ["claude", "factory"] if platform == "all" else [platform]

    for p in platforms:
        if p == "factory":
            settings_path = Path.home() / ".factory" / "settings.json"
            platform_label = "factory (Droid)"
        else:
            settings_path = Path.home() / ".claude" / "settings.json"
            platform_label = "claude"

        hooks_changed = remove_hooks(settings_path, hook_commands)
        if hooks_changed:
            click.echo(f"  \u2713  removed hooks from {settings_path} ({platform_label})")
        else:
            click.echo(f"  \u2013  no memex hooks found in {settings_path} ({platform_label})")

        if p == "factory":
            skill_dst = Path.home() / ".factory" / "skills" / "memex"
            if skill_dst.exists():
                shutil.rmtree(skill_dst)
                click.echo(f"  \u2713  removed memex skill from {skill_dst}")

    if delete_data:
        resolved_memex = Path(memex_dir) if memex_dir else Path.home() / ".memex"
        if resolved_memex.exists():
            shutil.rmtree(resolved_memex)
            click.echo(f"  \u2713  deleted {resolved_memex}")
        else:
            click.echo(f"  \u2013  {resolved_memex} not found, skipped")
    else:
        resolved_memex = Path(memex_dir) if memex_dir else Path.home() / ".memex"
        click.echo(f"  \u2013  kept {resolved_memex} (pass --delete-data to remove)")

    click.echo("\nmemex uninstalled. Restart your AI platform for changes to take effect.")
