# memex — Design Spec
**Date:** 2026-04-22  
**Status:** Approved

---

## What We Are Building

A zero-friction, self-building second brain that passively captures everything across AI coding sessions, compiles it into structured knowledge, and makes it instantly queryable.

No daemon. No persistent process to babysit. A simple spawn chain triggered by hooks.

---

## Architecture Overview

```
Claude Code hook fires
  → session-end.py / pre-compact.py (hook, <1s, no API)
      → pre_filter(transcript) → raw/{project-id}/{timestamp}.md
      → spawns flush.py (detached, Haiku)
          → extract + tag + route → append to notes/
          → if past 6pm + daily changed → spawns compile.py (detached, Sonnet)
              → merge + append-only update → notes/
              → graphify --update → graph/global/graphify-out/

Claude Code session starts
  → session-start.py (hook, <1s, no API)
      → reads notes in fixed priority order
      → injects up to 20,000 chars into session context
```

The five layers:
- **Layer 1 — CAPTURE:** Claude Code hooks + pre-filter
- **Layer 2 — COMPILE:** flush agent (Haiku) + compile agent (Sonnet) → Obsidian notes
- **Layer 3 — KNOWLEDGE:** Obsidian vault at `~/.memex/notes/`
- **Layer 4 — GRAPH:** graphify runs on vault → queryable graph + MCP server
- **Layer 5 — QUERY:** session-start injection + graphify MCP + memex CLI

---

## Directory Structure

```
~/.memex/
├── config.yaml                    # per-stage model config
├── raw/
│   └── {project-id}/
│       └── {timestamp}.md         # pre-filtered transcript dump
├── notes/                         # Obsidian vault root
│   ├── projects/
│   │   └── {project-id}/
│   │       ├── _index.md          # auto-maintained project overview
│   │       ├── decisions.md       # append-only decision log (date-stamped)
│   │       └── {concept}.md       # per-concept notes (append-only)
│   ├── concepts/                  # cross-project promoted concepts
│   ├── daily/
│   │   └── {YYYY-MM-DD}.md        # cross-project daily digest
├── graph/
│   └── global/
│       └── graphify-out/          # graphify output (graph.json, obsidian/, wiki/)
└── state/
    └── {project-id}.json          # hashes, last-compiled, token costs (audit only)
```

**Project identity:** `git remote get-url origin` in the session's cwd, sanitised to a filesystem-safe slug. Falls back to `cwd` basename if no git remote.

---

## config.yaml Format

```yaml
flush:
  provider: anthropic       # anthropic | openai | ollama
  model: claude-haiku-4-5-20251001
  base_url: null            # override for OSS/custom endpoints

compile:
  provider: anthropic
  model: claude-sonnet-4-6
  base_url: null

pre_filter:
  max_context_chars: 15000
  max_turns: 30

session_start:
  max_inject_chars: 20000
  compile_after_hour: 18    # trigger compile if past this hour (local time)
```

---

## Layer 1: Capture

### Hooks

Three hooks registered in `.claude/settings.json`:

| Hook | Event | Responsibility |
|------|-------|----------------|
| `session-end.py` | SessionEnd | pre-filter → write raw → spawn flush.py |
| `pre-compact.py` | PreCompact | same as session-end (safety net before compaction) |
| `session-start.py` | SessionStart | read notes → inject context |

**Recursion guard:** All hooks check `CLAUDE_INVOKED_BY=memory_flush` env var and `sys.exit(0)` immediately if set. Prevents flush.py's Agent SDK call from re-firing hooks.

**Why PreCompact + SessionEnd?** Long sessions trigger multiple auto-compactions. Without PreCompact, context between compactions is lost before SessionEnd fires.

### Pre-filter (pure Python, no LLM)

Runs inside the hook before spawning, keeps the hook under 1s:

1. Read Claude Code JSONL at `transcript_path` from stdin
2. Extract only `user` / `assistant` turns — skip tool calls, tool results, file reads
3. Collapse consecutive whitespace, strip boilerplate
4. Truncate to last N turns if over `max_context_chars`
5. Write to `raw/{project-id}/{timestamp}.md`
6. Return empty string if nothing useful — flush.py exits early if empty

**JSONL parsing:**
```python
entry = json.loads(line)
msg = entry.get("message", {})
role = msg.get("role", "")       # "user" or "assistant"
content = msg.get("content", "") # string or list of {"type": "text", "text": "..."} blocks
```

---

## Layer 2: Intelligence

### flush.py (Haiku, detached background process)

**Spawn method:** `subprocess.Popen(..., start_new_session=True)` on Mac/Linux.

**Steps:**
1. Set `CLAUDE_INVOKED_BY=memory_flush` before any imports
2. Read `raw/{project-id}/{timestamp}.md`
3. Exit early if empty, or if same session flushed within 60s (dedup via `state/{project-id}.json`)
4. Call model with `max_turns=2`, `allowed_tools=[]`

**Flush prompt instructs the model to:**
- Tag each extracted item: `[DECISION]`, `[INSIGHT]`, `[PATTERN]`, `[SKIP]`
- Route based on tag + project context:
  - `[DECISION]` → `notes/projects/{project-id}/decisions.md` (append, date-stamped)
  - `[INSIGHT]` with project → `notes/projects/{project-id}/{concept}.md` (append, date-stamped)
  - `[INSIGHT]` without project → `notes/daily/YYYY-MM-DD.md`
  - `[PATTERN]` (reusable, cross-project) → `notes/concepts/{concept}.md`
  - `[SKIP]` → dropped
- Return `FLUSH_OK` if nothing worth saving

5. Append output to appropriate notes (append-only, date-stamped)
6. Update `state/{project-id}.json` (session hash, timestamp, token cost)
7. If `datetime.now().hour >= compile_after_hour` and daily note hash changed since last compile → spawn `compile.py` detached

**Provider abstraction:** flush.py reads `config.yaml` and builds the SDK client from `provider` + `base_url`. Supports `anthropic`, `openai`-compatible endpoints, `ollama`.

### compile.py (Sonnet, detached background process)

1. Read all notes changed since last compile (via hashes in `state/`)
2. For each changed note: Sonnet cleans formatting, resolves redundancy within the note
3. **Append-only rule:** New content always goes below existing, date-stamped. Never deletes lines.
4. Auto-maintain `notes/projects/{project-id}/_index.md` (project overview summary)
5. Run `graphify ~/.memex/notes --update --obsidian` → updates `graph/global/graphify-out/`
6. Record compile timestamp + cost in state

---

## Layer 3: Knowledge

Obsidian vault at `~/.memex/notes/`. Standard markdown with `[[wikilinks]]` + YAML frontmatter. Works natively in Obsidian — open the folder as a vault, no special plugin required.

**Merge strategy:** Append-only with date stamps across all note types. No content is ever overwritten or deleted. Notes grow as understanding evolves — the date stamps let you read the history.

---

## Layer 4: Graph

**graphify** (pip install graphifyy) runs after every compile:

```bash
graphify ~/.memex/notes --update --obsidian
```

Output: `~/.memex/graph/global/graphify-out/` (graph.json, obsidian/, wiki/, GRAPH_REPORT.md)

One global graph covering all projects. Cross-project connections are the valuable output — per-project graphs skipped for now.

**MCP server** (on demand, not always-on):

```bash
python -m graphify.serve ~/.memex/graph/global/graphify-out/graph.json
```

Started via `memex serve`. Claude Code, Copilot CLI, and other tools connect via MCP stdio.

---

## Layer 5: Query

### Session-Start Injection

`session-start.py` injects context in fixed priority order, capped at `max_inject_chars` (20,000):

1. `notes/projects/{project-id}/_index.md`
2. `notes/projects/{project-id}/decisions.md`
3. `notes/daily/YYYY-MM-DD.md` (today)
4. Top 3 notes from `notes/concepts/` by most-recently-modified

Each item appended until budget exhausted. Outputs:
```json
{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}}
```

Pure local I/O. No API calls. Runs in under 1 second.

### memex CLI

| Command | What it does |
|---------|-------------|
| `memex install` | Write hooks to `.claude/settings.json`, create `~/.memex/` dirs |
| `memex flush` | Manual trigger of flush pipeline |
| `memex compile` | Manual trigger of compile |
| `memex serve` | Start graphify MCP server |
| `memex doctor` | Check hooks registered, notes dir exists, graphify installed, last flush/compile timestamps |
| `memex status` | Show cost summary from state files |

---

## Build Phases

| Phase | Name | Scope |
|-------|------|-------|
| 1 | FOUNDATION | `~/.memex/` dirs, `config.yaml`, pre-filter, hooks skeleton, state tracking |
| 2 | INTELLIGENCE | flush.py (Haiku) + compile.py (Sonnet) + note writer |
| 3 | GRAPH | graphify integration + MCP server wiring |
| 4 | INJECTION | session-start hook + context budget logic + cross-tool ports |
| 5 | POLISH | memex CLI + `memex doctor` + cost tracking + provider abstraction |

Each phase is independently useful. Phase 1 alone gives you raw capture. Phase 2 adds intelligence. Phase 3 adds queryability.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Process model | Direct spawn (no daemon) | No persistent process to babysit; battle-tested by claude-memory-compiler |
| Queue | Dropped as active queue; state/ is audit log only | Daemon motivation removed once direct spawn chosen |
| Project identity | `git remote get-url origin` slug | Survives folder renames |
| Merge strategy | Append-only, date-stamped | No silent data loss; decisions need audit trail |
| Compile trigger | End-of-day (6pm) + hash change | Don't compile after every session; one daily compile is enough |
| Flush extraction | Tag-based routing ([DECISION]/[INSIGHT]/[PATTERN]/[SKIP]) | Compile agent uses tags to route; no cold re-classification |
| Session injection | Fixed priority order | No graphify dependency on hot path; deterministic |
| Graph scope | One global graph | Cross-project connections are the valuable output |
| Model config | provider + model + base_url per stage | OSS model swap without touching code |
| Knowledge store | Obsidian vault (markdown + wikilinks) | Native Obsidian support; graphify reads markdown natively |
