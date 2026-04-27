"""Installer: creates ~/.memex/ and registers hooks with supported platforms (Claude Code, Factory Droid)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

_REQUIRED_DIRS = [
    "raw",
    "notes/projects",
    "notes/concepts",
    "notes/daily",
    "state",
    "graph/global/graphify-out",
]

_DEFAULT_CONFIG = {
    "flush": {
        "provider": "anthropic",
        "model": "claude-haiku-4-5-20251001",
        "base_url": None,
        "max_flush_chars": 50000,
    },
    "compile": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "base_url": None,
    },
    "pre_filter": {
        "max_context_chars": 15000,
        "max_turns": 30,
    },
    "session_start": {
        "max_inject_chars": 20000,
        "compile_after_hour": 18,
    },
}

# Platform settings paths and hook event mappings
_CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
_FACTORY_SETTINGS = Path.home() / ".factory" / "settings.json"


def _factory_hook_entry(command: str) -> dict:
    """Build a Factory Droid hook entry (matcher + hooks list)."""
    return {
        "matcher": "",
        "hooks": [{"type": "command", "command": command}],
    }


def create_memex_dir(memex_dir: Path) -> list[str]:
    """
    Create required ~/.memex/ subdirectories.
    Returns list of directory paths newly created (empty list if all existed).
    """
    created: list[str] = []
    for rel in _REQUIRED_DIRS:
        d = memex_dir / rel
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(str(d))
    return created


def write_default_config(memex_dir: Path) -> bool:
    """
    Write default config.yaml to memex_dir if it doesn't already exist.
    Returns True if written, False if already existed.
    """
    config_path = memex_dir / "config.yaml"
    if config_path.exists():
        return False
    config_path.write_text(yaml.dump(_DEFAULT_CONFIG, default_flow_style=False))
    return True


def _command_registered(hooks_list: list, command: str) -> bool:
    """Return True if command string is already in any hook entry in the list."""
    for entry in hooks_list:
        for hook in entry.get("hooks", []):
            if hook.get("command") == command:
                return True
    return False


def _script_basename(command: str) -> str:
    """Extract the hook script filename from a command string (last token)."""
    return command.split()[-1].split("/")[-1]


def _purge_stale_memex_entries(
    event_list: list, basenames: set[str], current_commands: set[str]
) -> tuple[list, bool]:
    """
    Remove entries whose command matches a memex script basename but is NOT
    one of the current exact commands (i.e. stale path/interpreter).
    Returns (filtered_list, changed).
    """
    filtered = [
        entry for entry in event_list
        if not any(
            _script_basename(hook.get("command", "")) in basenames
            and hook.get("command") not in current_commands
            for hook in entry.get("hooks", [])
        )
    ]
    return filtered, len(filtered) != len(event_list)


def merge_hooks(
    settings_path: Path,
    hook_commands: dict[str, str],
) -> bool:
    """
    Add memex hook entries to a platform settings file without removing existing hooks.

    Stale memex entries (same hook script filename, different path/interpreter)
    are removed before adding fresh entries to prevent accumulation on reinstall.

    hook_commands: {"EventName": "/absolute/path/to/hook.py", ...}

    Returns True if any changes were made, False if all already registered.
    Creates settings file if it doesn't exist.
    """
    if settings_path.exists():
        try:
            data: dict = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}
        settings_path.parent.mkdir(parents=True, exist_ok=True)

    hooks: dict = data.setdefault("hooks", {})
    changed = False

    # Build set of hook script basenames we own (e.g. {"session-end.py", ...})
    memex_basenames = {_script_basename(cmd) for cmd in hook_commands.values()}

    for event, command in hook_commands.items():
        event_list: list = hooks.setdefault(event, [])

        # Remove stale memex entries for this event before checking/adding
        cleaned, purged = _purge_stale_memex_entries(
            event_list, memex_basenames, set(hook_commands.values())
        )
        if purged:
            hooks[event] = cleaned
            event_list = cleaned
            changed = True

        if not _command_registered(event_list, command):
            event_list.append(_factory_hook_entry(command))
            changed = True

    if changed:
        settings_path.write_text(json.dumps(data, indent=2))

    return changed


def remove_hooks(settings_path: Path, hook_commands: dict[str, str]) -> bool:
    """
    Remove memex hook entries from settings.json.

    hook_commands: {"EventName": "/absolute/path/to/hook.py", ...}

    Returns True if any changes were made, False if nothing was registered.
    """
    if not settings_path.exists():
        return False

    try:
        data: dict = json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False

    hooks: dict = data.get("hooks", {})
    commands_to_remove = set(hook_commands.values())
    changed = False

    for event, event_list in hooks.items():
        filtered = [
            entry for entry in event_list
            if not any(
                hook.get("command") in commands_to_remove
                for hook in entry.get("hooks", [])
            )
        ]
        if len(filtered) != len(event_list):
            hooks[event] = filtered
            changed = True

    if changed:
        settings_path.write_text(json.dumps(data, indent=2))

    return changed
