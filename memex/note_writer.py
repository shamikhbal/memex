from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Optional


def slugify_concept(text: str) -> str:
    """Convert a concept name to a filesystem-safe slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _format_wikilinks(related: list[str]) -> str:
    """Format related concepts as Obsidian wikilinks."""
    if not related:
        return ""
    links = " · ".join(f"[[{slugify_concept(r)}]]" for r in related)
    return f"\n\nRelated: {links}\n"


def append_item(
    tag: str,
    content: str,
    concept: str,
    project_id: Optional[str],
    notes_dir: Path,
    today: Optional[date] = None,
    related: Optional[list[str]] = None,
) -> None:
    """
    Append a single extracted item to the appropriate Obsidian note.
    Always appends — never overwrites existing content.
    """
    if tag == "SKIP":
        return

    if today is None:
        today = date.today()

    date_stamp = today.isoformat()
    concept_slug = slugify_concept(concept)

    if tag == "DECISION" and project_id:
        dest = notes_dir / "projects" / project_id / "decisions.md"
    elif tag == "INSIGHT" and project_id:
        dest = notes_dir / "projects" / project_id / f"{concept_slug}.md"
    elif tag == "INSIGHT" and not project_id:
        dest = notes_dir / "daily" / f"{date_stamp}.md"
    elif tag == "PATTERN":
        dest = notes_dir / "concepts" / f"{concept_slug}.md"
    else:
        return  # unknown tag

    dest.parent.mkdir(parents=True, exist_ok=True)

    entry = f"\n\n## {date_stamp}\n\n{content.strip()}\n"
    entry += _format_wikilinks(related or [])

    with open(dest, "a", encoding="utf-8") as f:
        f.write(entry)
