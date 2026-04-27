import pytest
from pathlib import Path
from memex.config import Config


def test_default_config_has_required_keys(tmp_memex: Path):
    cfg = Config(memex_dir=tmp_memex)
    assert cfg.flush_model == "claude-haiku-4-5-20251001"
    assert cfg.flush_provider == "anthropic"
    assert cfg.compile_model == "claude-sonnet-4-6"
    assert cfg.compile_provider == "anthropic"
    assert cfg.max_context_chars == 15000
    assert cfg.max_turns == 30
    assert cfg.max_inject_chars == 20000
    assert cfg.max_flush_chars == 50000
    assert cfg.compile_after_hour == 18


def test_config_path_constants(tmp_memex: Path):
    cfg = Config(memex_dir=tmp_memex)
    assert cfg.raw_dir == tmp_memex / "raw"
    assert cfg.notes_dir == tmp_memex / "notes"
    assert cfg.state_dir == tmp_memex / "state"
    assert cfg.graph_dir == tmp_memex / "graph" / "global" / "graphify-out"


def test_config_loads_from_yaml(tmp_memex: Path):
    import yaml
    yaml_content = {
        "flush": {"provider": "openai", "model": "gpt-4o-mini", "base_url": "http://localhost:11434", "max_flush_chars": 30000},
        "compile": {"provider": "anthropic", "model": "claude-sonnet-4-6", "base_url": None},
        "pre_filter": {"max_context_chars": 8000, "max_turns": 20},
        "session_start": {"max_inject_chars": 10000, "compile_after_hour": 20},
    }
    (tmp_memex / "config.yaml").write_text(yaml.dump(yaml_content))
    cfg = Config(memex_dir=tmp_memex)
    assert cfg.flush_provider == "openai"
    assert cfg.flush_model == "gpt-4o-mini"
    assert cfg.flush_base_url == "http://localhost:11434"
    assert cfg.max_context_chars == 8000
    assert cfg.max_flush_chars == 30000
    assert cfg.compile_after_hour == 20
