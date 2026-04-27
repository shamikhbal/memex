# tests/test_installer.py
import json
import pytest
from pathlib import Path

from memex.installer import create_memex_dir, write_default_config, merge_hooks


# ── create_memex_dir ─────────────────────────────────────────────────────────

def test_create_memex_dir_creates_required_subdirs(tmp_path: Path):
    memex = tmp_path / ".memex"
    created = create_memex_dir(memex)
    required = [
        memex / "raw",
        memex / "notes" / "projects",
        memex / "notes" / "concepts",
        memex / "notes" / "daily",
        memex / "state",
        memex / "graph" / "global" / "graphify-out",
    ]
    for d in required:
        assert d.exists(), f"missing: {d}"
    assert len(created) > 0


def test_create_memex_dir_is_idempotent(tmp_path: Path):
    memex = tmp_path / ".memex"
    create_memex_dir(memex)
    created_second = create_memex_dir(memex)
    assert created_second == []


# ── write_default_config ─────────────────────────────────────────────────────

def test_write_default_config_creates_yaml(tmp_path: Path):
    memex = tmp_path / ".memex"
    memex.mkdir()
    result = write_default_config(memex)
    assert result is True
    config_path = memex / "config.yaml"
    assert config_path.exists()
    import yaml
    data = yaml.safe_load(config_path.read_text())
    assert data["flush"]["model"] == "claude-haiku-4-5-20251001"
    assert data["flush"]["max_flush_chars"] == 50000
    assert data["compile"]["model"] == "claude-sonnet-4-6"
    assert data["pre_filter"]["max_context_chars"] == 15000
    assert data["session_start"]["max_inject_chars"] == 20000


def test_write_default_config_skips_if_exists(tmp_path: Path):
    memex = tmp_path / ".memex"
    memex.mkdir()
    (memex / "config.yaml").write_text("existing: true\n")
    result = write_default_config(memex)
    assert result is False
    assert "existing: true" in (memex / "config.yaml").read_text()


# ── merge_hooks ───────────────────────────────────────────────────────────────

def test_merge_hooks_creates_settings_json_if_absent(tmp_path: Path):
    settings = tmp_path / "settings.json"
    commands = {"SessionEnd": "/hooks/session-end.py"}
    changed = merge_hooks(settings, commands)
    assert changed is True
    assert settings.exists()
    data = json.loads(settings.read_text())
    assert "SessionEnd" in data["hooks"]


def test_merge_hooks_adds_all_three_events(tmp_path: Path):
    settings = tmp_path / "settings.json"
    commands = {
        "SessionEnd": "/hooks/session-end.py",
        "PreCompact": "/hooks/pre-compact.py",
        "SessionStart": "/hooks/session-start.py",
    }
    merge_hooks(settings, commands)
    data = json.loads(settings.read_text())
    for event in ("SessionEnd", "PreCompact", "SessionStart"):
        assert event in data["hooks"]


def test_merge_hooks_is_idempotent(tmp_path: Path):
    settings = tmp_path / "settings.json"
    commands = {"SessionEnd": "/hooks/session-end.py"}
    merge_hooks(settings, commands)
    changed = merge_hooks(settings, commands)
    assert changed is False
    data = json.loads(settings.read_text())
    cmds = [
        h["command"]
        for entry in data["hooks"]["SessionEnd"]
        for h in entry.get("hooks", [])
    ]
    assert cmds.count("/hooks/session-end.py") == 1


def test_merge_hooks_replaces_stale_entries_on_reinstall(tmp_path: Path):
    """Re-installing with a different path/interpreter must not accumulate duplicates."""
    settings = tmp_path / "settings.json"
    # First install: old venv / old path
    merge_hooks(settings, {"SessionEnd": "/old/venv/python /old/hooks/session-end.py"})
    # Second install: new venv / new path (same basename, different prefix)
    changed = merge_hooks(settings, {"SessionEnd": "/new/venv/python /new/hooks/session-end.py"})
    assert changed is True
    data = json.loads(settings.read_text())
    cmds = [
        h["command"]
        for entry in data["hooks"]["SessionEnd"]
        for h in entry.get("hooks", [])
    ]
    assert len(cmds) == 1, f"Expected 1 entry, got {cmds}"
    assert cmds[0] == "/new/venv/python /new/hooks/session-end.py"


def test_merge_hooks_preserves_existing_hooks(tmp_path: Path):
    settings = tmp_path / "settings.json"
    existing = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "", "hooks": [{"type": "command", "command": "/other/hook.py"}]}
            ]
        }
    }
    settings.write_text(json.dumps(existing))
    merge_hooks(settings, {"SessionEnd": "/hooks/session-end.py"})
    data = json.loads(settings.read_text())
    assert "PreToolUse" in data["hooks"]
    assert "SessionEnd" in data["hooks"]


def test_merge_hooks_creates_parent_dir_for_factory_settings(tmp_path: Path):
    """When ~/.factory/settings.json doesn't exist, parent is created automatically."""
    factory_dir = tmp_path / ".factory"
    settings = factory_dir / "settings.json"
    # Neither directory nor file exists
    assert not factory_dir.exists()
    merge_hooks(settings, {"SessionEnd": "/hooks/session-end.py"})
    assert settings.exists()
    assert factory_dir.is_dir()
