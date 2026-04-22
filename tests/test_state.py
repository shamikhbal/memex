import pytest
from pathlib import Path
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
