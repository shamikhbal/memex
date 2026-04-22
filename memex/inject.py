from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from memex.config import Config


# Budget fractions (sum of index + decisions = project 0.50)
_FRACTIONS = {
    "project": 0.50,
    "index": 0.35,
    "decisions": 0.15,
    "daily": 0.20,
    # concepts gets whatever is left after project + daily
}


def _tier_budget(max_inject_chars: int, tier: str) -> int:
    """Return the char budget for the given tier name."""
    return int(max_inject_chars * _FRACTIONS[tier])


def _read_capped_lines(path: Path, budget: int) -> tuple[str, int]:
    """
    Read file content up to budget chars, truncating at a line boundary.
    Returns (content, chars_used). Returns ("", 0) if file is missing.
    """
    if not path.exists():
        return "", 0
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return "", 0
    if len(raw) <= budget:
        return raw, len(raw)
    truncated = raw[:budget]
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[: last_newline + 1]
    return truncated, len(truncated)


def _select_concepts(
    concepts_dir: Path,
    budget: int,
    graph_json: Optional[Path] = None,
) -> list[Path]:
    """
    Return up to 3 concept .md files ordered by relevance.
    Uses graph node degree if graph_json exists and is parseable; falls back to mtime.
    """
    if not concepts_dir.exists():
        return []

    candidates = list(concepts_dir.glob("*.md"))
    if not candidates:
        return []

    if graph_json and graph_json.exists():
        try:
            import json as _json
            data = _json.loads(graph_json.read_text())
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])
            degree: dict[str, int] = {}
            for edge in edges:
                for key in ("source", "target"):
                    nid = edge.get(key, "")
                    if nid:
                        degree[nid] = degree.get(nid, 0) + 1
            stem_to_degree: dict[str, int] = {}
            for node in nodes:
                nid = node.get("id", "")
                stem = Path(node.get("path", nid)).stem
                stem_to_degree[stem] = degree.get(nid, 0)
            candidates.sort(
                key=lambda f: stem_to_degree.get(f.stem, 0),
                reverse=True,
            )
        except Exception:
            candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    else:
        candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    return candidates[:3]


def build_context(
    config: Config,
    project_id: str,
    graph_json: Optional[Path] = None,
) -> str:
    """
    Build the injection context string from ~/.memex/notes/.

    Budget allocation (of max_inject_chars):
      - _index.md:     35%
      - decisions.md:  15%
      - daily note:    20%
      - concepts:      remaining

    Returns empty string if no notes exist.
    """
    notes = config.notes_dir
    total = config.max_inject_chars
    sections: list[str] = []

    # Project tier
    index_path = notes / "projects" / project_id / "_index.md"
    index_content, _ = _read_capped_lines(index_path, _tier_budget(total, "index"))
    if index_content:
        sections.append(f"## _index.md\n\n{index_content}")

    decisions_path = notes / "projects" / project_id / "decisions.md"
    decisions_content, _ = _read_capped_lines(decisions_path, _tier_budget(total, "decisions"))
    if decisions_content:
        sections.append(f"## decisions.md\n\n{decisions_content}")

    # Daily tier
    daily_path = notes / "daily" / f"{date.today().isoformat()}.md"
    daily_content, _ = _read_capped_lines(daily_path, _tier_budget(total, "daily"))
    if daily_content:
        sections.append(f"## {daily_path.name}\n\n{daily_content}")

    # Concepts tier — whatever budget remains
    used_so_far = sum(len(s) for s in sections)
    concepts_budget = max(0, total - used_so_far)
    concept_files = _select_concepts(notes / "concepts", concepts_budget, graph_json)
    for p in concept_files:
        if concepts_budget <= 0:
            break
        content, used = _read_capped_lines(p, concepts_budget)
        if content:
            sections.append(f"## {p.stem}\n\n{content}")
            concepts_budget -= used

    return "\n\n---\n\n".join(sections)
