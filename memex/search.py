"""Full-text search across the memex Obsidian vault.

Does NOT require graphify — works directly against .md files.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Hit:
    file: str
    path: Path
    heading: str
    line: str
    line_number: int
    snippet: str


@dataclass
class SearchResult:
    query: str
    hits: list[Hit] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(set(h.path for h in self.hits))


def _extract_heading(lines: list[str], hit_idx: int) -> str:
    """Scan backwards from hit_idx to find the nearest ## heading."""
    for i in range(hit_idx, -1, -1):
        m = re.match(r"^##\s+(.+)", lines[i])
        if m:
            return m.group(1).strip()
    return "(top)"


def _build_snippet(line: str, query: str) -> str:
    """Wrap query terms in **bold** within the snippet."""
    # Split query into words, escape them
    words = [re.escape(w) for w in query.split() if len(w) > 1]
    if not words:
        return line.strip()
    pattern = re.compile("|".join(words), re.IGNORECASE)
    return pattern.sub(lambda m: f"**{m.group()}**", line.strip())


def search(
    notes_dir: Path,
    query: str,
    *,
    project_id: Optional[str] = None,
    max_results: int = 20,
) -> SearchResult:
    """Search vault .md files for query, returning hits with context."""
    result = SearchResult(query=query)

    if not notes_dir.exists():
        return result

    files: list[Path] = []
    files.extend(notes_dir.glob("*.md"))
    files.extend(notes_dir.glob("daily/*.md"))
    if project_id:
        proj_dir = notes_dir / "projects" / project_id
        if proj_dir.exists():
            files.extend(proj_dir.glob("*.md"))
    else:
        files.extend(notes_dir.glob("projects/**/*.md"))
    files.extend(notes_dir.glob("concepts/*.md"))

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    seen: set[tuple[str, str]] = set()

    for f in sorted(files):
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue

        lines = text.split("\n")
        rel_path = str(f.relative_to(notes_dir))

        for i, line in enumerate(lines):
            if not pattern.search(line):
                continue
            heading = _extract_heading(lines, i)
            snippet = _build_snippet(line, query)
            key = (rel_path, snippet)
            if key in seen:
                continue
            seen.add(key)
            result.hits.append(Hit(
                file=rel_path,
                path=f,
                heading=heading,
                line=line.strip(),
                line_number=i + 1,
                snippet=snippet,
            ))
            if len(result.hits) >= max_results:
                break
        if len(result.hits) >= max_results:
            break

    return result
