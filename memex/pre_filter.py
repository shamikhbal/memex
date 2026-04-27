from __future__ import annotations

import json
from pathlib import Path


def truncate_transcript(text: str, max_chars: int) -> str:
    """
    Truncate a markdown transcript to max_chars, keeping the most recent
    portion and aligning to a turn boundary (``**User:**`` or ``**Assistant:**``).

    If the text is already within the limit, it is returned unchanged.
    """
    if len(text) <= max_chars:
        return text

    truncated = text[-max_chars:]
    boundary = truncated.find("\n**")
    if boundary > 0:
        truncated = truncated[boundary + 1:]

    return truncated


def _extract_text(content: object) -> str:
    """Extract plain text from a content field (string or list of blocks)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", "").strip())
            elif isinstance(block, str):
                parts.append(block.strip())
        return "\n".join(p for p in parts if p)
    return ""


def pre_filter(
    transcript_path: Path,
    max_context_chars: int,
    max_turns: int,
) -> tuple[str, int]:
    """
    Read a Claude Code JSONL transcript and return (markdown_text, turn_count).

    Keeps only user/assistant turns. Strips tool calls, tool results, file reads.
    Truncates to max_turns and max_context_chars.
    Returns ("", 0) if the file is missing or produces no output.
    """
    if not transcript_path.exists():
        return "", 0

    turns: list[str] = []
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = entry.get("message", {})
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                else:
                    role = entry.get("role", "")
                    content = entry.get("content", "")

                if role not in ("user", "assistant"):
                    continue

                text = _extract_text(content)
                if not text:
                    continue

                label = "User" if role == "user" else "Assistant"
                turns.append(f"**{label}:** {text}\n")
    except OSError:
        return "", 0

    recent = turns[-max_turns:] if max_turns < len(turns) else turns
    context = "\n".join(recent)

    if len(context) > max_context_chars:
        context = context[-max_context_chars:]
        # align to turn boundary
        boundary = context.find("\n**")
        if boundary > 0:
            context = context[boundary + 1:]

    return context, len(recent)
