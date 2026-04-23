import pytest
from pathlib import Path
from datetime import date, timedelta
from memex.state import ProjectState


def test_default_state_is_empty(tmp_memex: Path):
    state = ProjectState(state_dir=tmp_memex / "state", project_id="test-proj")
    assert state.last_flush_session_id is None
    assert state.last_flush_timestamp is None
    assert state.last_compile_timestamp is None
    assert state.daily_hash is None
    assert state.total_cost == 0.0


def test_save_and_reload(tmp_memex: Path):
    state_dir = tmp_memex / "state"
    state = ProjectState(state_dir=state_dir, project_id="test-proj")
    state.last_flush_session_id = "sess-abc"
    state.last_flush_timestamp = 1714000000.0
    state.daily_hash = "abc123"
    state.total_cost = 0.005
    state.save()

    reloaded = ProjectState(state_dir=state_dir, project_id="test-proj")
    assert reloaded.last_flush_session_id == "sess-abc"
    assert reloaded.last_flush_timestamp == 1714000000.0
    assert reloaded.daily_hash == "abc123"
    assert reloaded.total_cost == 0.005


def test_is_duplicate_flush(tmp_memex: Path):
    import time
    state = ProjectState(state_dir=tmp_memex / "state", project_id="test-proj")
    state.last_flush_session_id = "sess-xyz"
    state.last_flush_timestamp = time.time() - 30  # 30s ago
    state.save()

    # same session within 60s → duplicate
    assert state.is_duplicate_flush("sess-xyz", dedup_window=60) is True
    # different session → not duplicate
    assert state.is_duplicate_flush("sess-other", dedup_window=60) is False
    # same session but outside window → not duplicate
    state.last_flush_timestamp = time.time() - 120
    assert state.is_duplicate_flush("sess-xyz", dedup_window=60) is False


def test_derive_status_active_recent_notes(tmp_memex: Path):
    """Project with notes from today is active."""
    state = ProjectState(state_dir=tmp_memex / "state", project_id="test-proj")
    notes_dir = tmp_memex / "notes"
    proj_dir = notes_dir / "projects" / "test-proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    (proj_dir / "decisions.md").write_text(f"## {today}\n\nSome decision.\n")
    assert state.derive_status(notes_dir) == "active"


def test_derive_status_paused_after_7_days(tmp_memex: Path):
    """Project with last note 10 days ago is paused."""
    state = ProjectState(state_dir=tmp_memex / "state", project_id="test-proj")
    notes_dir = tmp_memex / "notes"
    proj_dir = notes_dir / "projects" / "test-proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    old_date = (date.today() - timedelta(days=10)).isoformat()
    (proj_dir / "decisions.md").write_text(f"## {old_date}\n\nOld decision.\n")
    assert state.derive_status(notes_dir) == "paused"


def test_derive_status_dormant_after_30_days(tmp_memex: Path):
    """Project with last note 45 days ago is dormant."""
    state = ProjectState(state_dir=tmp_memex / "state", project_id="test-proj")
    notes_dir = tmp_memex / "notes"
    proj_dir = notes_dir / "projects" / "test-proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    old_date = (date.today() - timedelta(days=45)).isoformat()
    (proj_dir / "decisions.md").write_text(f"## {old_date}\n\nAncient decision.\n")
    assert state.derive_status(notes_dir) == "dormant"


def test_derive_status_no_notes_is_dormant(tmp_memex: Path):
    """Project with no notes at all is dormant."""
    state = ProjectState(state_dir=tmp_memex / "state", project_id="test-proj")
    notes_dir = tmp_memex / "notes"
    assert state.derive_status(notes_dir) == "dormant"


def test_derive_status_respects_override(tmp_memex: Path):
    """Manual override takes precedence over auto-derive."""
    state = ProjectState(state_dir=tmp_memex / "state", project_id="test-proj")
    notes_dir = tmp_memex / "notes"
    proj_dir = notes_dir / "projects" / "test-proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    (proj_dir / "decisions.md").write_text(f"## {today}\n\nRecent decision.\n")
    state.set_override("completed")
    state.save()
    assert state.derive_status(notes_dir) == "completed"


def test_clear_override(tmp_memex: Path):
    """Clearing override reverts to auto-derive."""
    state = ProjectState(state_dir=tmp_memex / "state", project_id="test-proj")
    notes_dir = tmp_memex / "notes"
    proj_dir = notes_dir / "projects" / "test-proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    (proj_dir / "decisions.md").write_text(f"## {today}\n\nRecent decision.\n")
    state.set_override("completed")
    state.save()
    state.clear_override()
    assert state.derive_status(notes_dir) == "active"


def test_override_persists_across_reload(tmp_memex: Path):
    """Override survives save/reload cycle."""
    state_dir = tmp_memex / "state"
    state = ProjectState(state_dir=state_dir, project_id="test-proj")
    state.set_override("paused")
    state.save()
    reloaded = ProjectState(state_dir=state_dir, project_id="test-proj")
    assert reloaded.status_override == "paused"
