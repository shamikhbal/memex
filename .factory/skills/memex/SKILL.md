---
name: memex
description: Persistent memory across Droid sessions. Captures decisions, insights, reminders, failures, and project context into an Obsidian-compatible vault. Use memex recall, memex status, memex inject to query and manage memory. Hooks automatically capture session transcripts and inject context on session start.
user-invocable: true
disable-model-invocation: false
---

# memex — Persistent AI Memory

## Architecture

Hooks automatically capture session transcripts and inject context. The CLI provides manual access:

## Commands

- `memex status` — List projects and their status (active/paused/dormant/completed)
- `memex recall "keyword"` — Search the vault for matches across all notes
- `memex recall -p project-name "keyword"` — Search within a specific project
- `memex inject` — Preview what context gets injected at session start
- `memex doctor` — Check memex health (hooks registered, graphify available)
- `memex search "keyword"` — Alias for recall

## Memory Categories (auto-extracted from sessions)

| Tag | File | Purpose |
|-----|------|---------|
| DECISION | `decisions.md` | Architecture choices with rationale |
| INSIGHT | `{concept}.md` | Lessons learned |
| PATTERN | `concepts/{pattern}.md` | Cross-project patterns |
| REMINDER | `reminders.md` | Follow-up tasks with deadlines |
| POST_MORTEM | `post-mortems.md` | Failures with root cause + prevention |
| EXPLORE | `explore-{concept}.md` | Brainstorms and ideas |
| SUMMARY | `daily/{date}.md` | Session diary entries |

## Before Making Decisions

Always check `memex inject` or `memex recall` for existing context, decisions, and reminders before making significant architectural choices or repeating previously learned lessons.
