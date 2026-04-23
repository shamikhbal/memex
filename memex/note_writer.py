from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Optional


# Maps item tags to Obsidian tag prefixes
_TAG_PREFIXES = {
    "DECISION": "type/decision",
    "EXPLORE": "type/exploration",
    "INSIGHT": "type/insight",
    "PATTERN": "type/pattern",
}


def slugify_concept(text: str) -> str:
    """Convert a concept name to a filesystem-safe slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _titleize(slug: str) -> str:
    """Convert a slug back to a readable title."""
    return slug.replace("-", " ").title()


def _format_wikilinks(related: list[str]) -> str:
    """Format related concepts as Obsidian wikilinks."""
    if not related:
        return ""
    links = " · ".join(f"[[{slugify_concept(r)}]]" for r in related)
    return f"\nRelated: {links}\n"


def _build_frontmatter(
    title: str,
    tag: str,
    project_id: Optional[str],
    created: str,
    related: list[str],
    extra_tags: Optional[list[str]] = None,
) -> str:
    """Build YAML frontmatter block."""
    tags: list[str] = []
    type_tag = _TAG_PREFIXES.get(tag)
    if type_tag:
        tags.append(type_tag)
    if project_id:
        tags.append(f"project/{project_id}")
    if extra_tags:
        tags.extend(extra_tags)

    lines = ["---"]
    lines.append(f"title: {title}")
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {t}")
    lines.append(f"created: {created}")
    if related:
        lines.append("related:")
        for r in related:
            lines.append(f'  - "[[{slugify_concept(r)}]]"')
    lines.append("---")
    return "\n".join(lines)


def _build_decisions_frontmatter(project_id: str, created: str) -> str:
    """Build frontmatter specifically for the decisions log."""
    lines = [
        "---",
        f"title: Decisions — {project_id}",
        "tags:",
        "  - type/decision-log",
        f"  - project/{project_id}",
        f"created: {created}",
        "---",
        "",
        f"# Decisions — {project_id}",
        "",
        "> [!info] Decision Log",
        f"> Non-obvious choices and their rationale for **{project_id}**.",
        "",
    ]
    return "\n".join(lines)


def _build_daily_frontmatter(date_stamp: str) -> str:
    """Build frontmatter for a daily note."""
    lines = [
        "---",
        f"title: Daily — {date_stamp}",
        "tags:",
        "  - type/daily",
        f"created: {date_stamp}",
        "---",
        "",
        f"# Daily — {date_stamp}",
        "",
    ]
    return "\n".join(lines)


def append_item(
    tag: str,
    content: str,
    concept: str,
    project_id: Optional[str],
    notes_dir: Path,
    today: Optional[date] = None,
    related: Optional[list[str]] = None,
    extra_tags: Optional[list[str]] = None,
    target_project: Optional[str] = None,
) -> None:
    """
    Append a single extracted item to the appropriate Obsidian note.
    Creates frontmatter + title on first write; appends dated sections after.
    """
    if tag == "SKIP":
        return

    if today is None:
        today = date.today()

    date_stamp = today.isoformat()
    concept_slug = slugify_concept(concept)
    related = related or []

    effective_pid = project_id
    if not effective_pid and target_project:
        candidate = notes_dir / "projects" / target_project
        if candidate.exists():
            effective_pid = target_project

    if tag == "DECISION" and effective_pid:
        dest = notes_dir / "projects" / effective_pid / "decisions.md"
    elif tag == "DECISION" and not effective_pid:
        dest = notes_dir / "daily" / f"{date_stamp}.md"
    elif tag == "EXPLORE" and effective_pid:
        dest = notes_dir / "projects" / effective_pid / f"explore-{concept_slug}.md"
    elif tag == "EXPLORE" and not effective_pid:
        dest = notes_dir / "daily" / f"{date_stamp}.md"
    elif tag == "INSIGHT" and effective_pid:
        dest = notes_dir / "projects" / effective_pid / f"{concept_slug}.md"
    elif tag == "INSIGHT" and not effective_pid:
        dest = notes_dir / "daily" / f"{date_stamp}.md"
    elif tag == "PATTERN":
        dest = notes_dir / "concepts" / f"{concept_slug}.md"
    else:
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    is_new = not dest.exists()

    parts: list[str] = []

    # Write frontmatter + title on first creation
    if is_new:
        if tag == "DECISION" and effective_pid:
            parts.append(_build_decisions_frontmatter(effective_pid, date_stamp))
        elif tag in ("DECISION", "INSIGHT", "EXPLORE") and not effective_pid:
            parts.append(_build_daily_frontmatter(date_stamp))
        else:
            title = _titleize(concept_slug)
            fm = _build_frontmatter(
                title=title,
                tag=tag,
                project_id=effective_pid,
                created=date_stamp,
                related=related,
                extra_tags=extra_tags,
            )
            parts.append(fm)
            parts.append("")
            parts.append(f"# {title}")
            parts.append("")

    # Dated entry
    parts.append(f"## {date_stamp}")
    parts.append("")
    parts.append(content.strip())
    parts.append("")
    wikilinks = _format_wikilinks(related)
    if wikilinks:
        parts.append(wikilinks)

    text = "\n".join(parts)
    if not is_new:
        text = "\n" + text

    with open(dest, "a", encoding="utf-8") as f:
        f.write(text)
