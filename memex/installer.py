from __future__ import annotations

import json
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


def merge_hooks(settings_path: Path, hook_commands: dict[str, str]) -> bool:
    """
    Add memex hook entries to settings.json without removing existing hooks.

    hook_commands: {"EventName": "/absolute/path/to/hook.py", ...}

    Returns True if any changes were made, False if all already registered.
    Creates settings.json if it doesn't exist.
    """
    if settings_path.exists():
        try:
            data: dict = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    hooks: dict = data.setdefault("hooks", {})
    changed = False

    for event, command in hook_commands.items():
        event_list: list = hooks.setdefault(event, [])
        if not _command_registered(event_list, command):
            event_list.append({
                "matcher": "",
                "hooks": [{"type": "command", "command": command}],
            })
            changed = True

    if changed:
        settings_path.write_text(json.dumps(data, indent=2))

    return changed
