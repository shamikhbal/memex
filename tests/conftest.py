import pytest
from pathlib import Path


@pytest.fixture
def tmp_memex(tmp_path: Path) -> Path:
    """A temporary ~/.memex/ directory for tests."""
    memex = tmp_path / ".memex"
    for d in ["raw", "notes/projects", "notes/concepts", "notes/daily", "state", "graph/global"]:
        (memex / d).mkdir(parents=True)
    return memex


@pytest.fixture
def sample_jsonl(tmp_path: Path) -> Path:
    """A minimal Claude Code JSONL transcript."""
    transcript = tmp_path / "transcript.jsonl"
    import json
    lines = [
        {"message": {"role": "user", "content": "How do I parse JSONL?"}},
        {"message": {"role": "assistant", "content": "Use json.loads() on each line."}},
        {"message": {"role": "user", "content": [{"type": "text", "text": "Show me an example."}]}},
        {"message": {"role": "assistant", "content": [{"type": "text", "text": "```python\nfor line in f:\n    obj = json.loads(line)\n```"}]}},
        # Tool result — should be filtered out
        {"message": {"role": "tool", "content": "some tool output"}},
    ]
    transcript.write_text("\n".join(json.dumps(l) for l in lines))
    return transcript
