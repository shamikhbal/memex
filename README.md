# memex

> Claude Code has no memory. memex fixes that.

Every session you start from zero. Decisions you made last week, patterns you figured out, that architecture trade-off you debated for an hour — gone. You re-explain yourself to your AI every single time.

memex runs silently in the background, captures everything, compiles it into structured knowledge, and injects the right context back at the start of every session. Your AI remembers — so you don't have to repeat yourself.

---

## How it works

Five layers, fully automatic:

```
Session ends
  → hooks/session-end.py captures the transcript
  → scripts/flush.py extracts decisions, patterns, concepts → ~/.memex/notes/
  → scripts/compile.py rewrites project index + builds knowledge graph
  → hooks/session-start.py injects budgeted context into your next session
  → memex serve exposes the full knowledge graph as an MCP server
```

Your notes live in `~/.memex/notes/` as plain Obsidian-compatible markdown with wikilinks — readable, portable, yours. Related concepts are automatically cross-linked with `[[wikilinks]]`, making the vault navigable in Obsidian's graph view.

---

## Compatibility

| Tool | Status |
|------|--------|
| Claude Code (CLI + desktop) | ✅ Full support |
| Copilot CLI | 🔜 Planned |
| Cursor / Windsurf | 🔜 Planned |

**Requirements:**
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (package manager)
- Claude Code
- An LLM provider: Anthropic API key, Ollama (local or cloud), or any OpenAI-compatible endpoint — see [Custom providers](#custom-providers)

---

## Setup

```bash
# 1. Clone and install
git clone https://github.com/sham/memex.git
cd memex
uv sync

# 2. One-command setup — creates ~/.memex/ and registers Claude Code hooks
memex install

# 3. Verify everything looks good
memex doctor
```

That's it. Start a new Claude Code session and memex is live.

---

## Usage

memex is mostly invisible — it runs on session hooks automatically. The CLI is for debugging and manual control.

### `memex doctor`
Check system health: directory structure, graphify binary, hook registration, last flush and compile timestamps.

```
  ✓  notes dir: /Users/sham/.memex/notes
  ✓  graphify: installed
  ✓  hooks: registered
  –  last flush: 2026-04-22 14:31
  –  last compile: 2026-04-22 18:05
```

### `memex inject`
Preview exactly what would be injected into your next session context — useful for debugging what Claude sees at startup.

```bash
memex inject
memex inject --cwd /path/to/project
```

### `memex status`
Show project status or set a manual override. Status is auto-derived from note recency (`active` ≤7 days, `paused` ≤30 days, `dormant` otherwise) and controls injection budget.

```bash
memex status                        # list all projects with status and last activity
memex status my-project             # show status for one project
memex status my-project active      # pin to active
memex status my-project auto        # clear override, revert to auto-derive
```

Valid statuses: `active`, `paused`, `dormant`, `completed`.

### `memex compile`
Manually compile project notes into a project index (`_index.md`) and rebuild the knowledge graph. Normally this runs automatically after 6pm, but you can trigger it anytime.

```bash
memex compile              # compile current project (auto-detected from CWD)
memex compile my-project   # compile a specific project by ID
```

### `memex query`
Query the knowledge graph from the command line. No LLM call — uses graph traversal to find relevant nodes.

```bash
memex query what decisions were made about hooks?
memex query ollama configuration
```

### `memex explain`
Explain a node and its neighbors in the knowledge graph.

```bash
memex explain "hook installer"
```

### `memex path`
Find the shortest path between two concepts in the graph.

```bash
memex path "merge hooks" "stale entries"
```

### `memex serve`
Start the graphify MCP server — connects Claude Code (and other MCP clients) to the full knowledge graph for structured queries.

```bash
memex serve
```

Add to your Claude Code MCP config to enable graph queries during sessions.

### `memex install`
Idempotent setup command — safe to run multiple times. Creates `~/.memex/` structure, writes default `config.yaml`, and registers the three Claude Code hooks.

```bash
memex install
```

### `memex uninstall`
Remove memex hooks from Claude Code settings. Your notes and data in `~/.memex/` are kept by default.

```bash
memex uninstall                  # removes hooks, keeps ~/.memex/ intact
memex uninstall --delete-data    # also deletes ~/.memex/ (irreversible)
```

Prompts for confirmation before making any changes. Restart Claude Code after running for changes to take effect.

---

## What gets captured

- **Decisions** — architecture choices, trade-offs, why you chose X over Y
- **Insights** — lessons learned, debugging discoveries, how-tos worth remembering
- **Patterns** — recurring approaches, conventions, things that work in your codebase
- **Explorations** — brainstorms, ideation, design space discussions worth revisiting
- **Daily digest** — cross-project summary of what you worked on

What gets **ignored**: tool outputs, file reads, boilerplate — only your actual thinking is kept.

Items extracted outside a git project (e.g. from `~`) are always routed to the daily note. If the LLM recognises that an item belongs to a known project it routes it there automatically, even across sessions.

---

## Context injection budget

memex never dumps everything into your context. It allocates a fixed budget (default 20,000 chars) split across source tiers:

| Source | Budget | Notes |
|--------|--------|-------|
| Project index (`_index.md`) | 35% | halved for dormant projects |
| Decisions log | 15% | active projects only |
| Today's daily note | 20% | always included |
| Top concepts (graph-ranked) | remaining | always included |

Concept notes are ranked by graph connectivity — the most referenced ideas surface first.

Project status (`active`, `paused`, `dormant`, `completed`) is derived automatically from note recency and controls how much project context is injected. Use `memex status` to view or override it.

---

## Custom providers

memex supports any OpenAI-compatible endpoint (Ollama, Together, local models) alongside Anthropic. Configure per pipeline stage in `~/.memex/config.yaml`:

```yaml
# Anthropic (default)
flush:
  provider: anthropic
  model: claude-haiku-4-5-20251001
  base_url: null

compile:
  provider: anthropic
  model: claude-sonnet-4-6
  base_url: null
```

```yaml
# Ollama (local or cloud)
flush:
  provider: ollama
  model: qwen3:8b                       # or any Ollama model
  base_url: http://127.0.0.1:11434/v1

compile:
  provider: ollama
  model: qwen3:14b
  base_url: http://127.0.0.1:11434/v1
```

```yaml
# OpenAI-compatible endpoint (Together, etc.)
flush:
  provider: openai
  model: gpt-4o-mini
  base_url: https://api.together.xyz/v1  # optional, defaults to OpenAI
```

Shared settings:

```yaml
flush:
  model: claude-haiku-4-5-20251001
  max_flush_chars: 50000   # truncate long transcripts before LLM call

pre_filter:
  max_context_chars: 15000
  max_turns: 30

session_start:
  max_inject_chars: 20000
  compile_after_hour: 18    # auto-compile triggers after 6pm (set to 0 for every session)
```

---

## Directory structure

```
~/.memex/
├── config.yaml
├── flush.log                   # hook and pipeline logs
├── raw/                        # pre-filtered session transcripts
│   └── {project-id}/
├── notes/                      # Obsidian-compatible vault with [[wikilinks]]
│   ├── projects/
│   │   └── {project-id}/
│   │       ├── _index.md       # auto-maintained project overview
│   │       └── decisions.md    # append-only decision log
│   ├── concepts/               # cross-project patterns (wikilinked)
│   └── daily/                  # daily digests
├── graph/
│   └── global/graphify-out/
│       ├── graph.json          # knowledge graph (graphify format)
│       └── GRAPH_REPORT.md     # god nodes, communities, structure
└── state/
    └── {project-id}.json       # timestamps, cost tracking
```

---

## How project identity works

memex uses your **git remote URL** as the project ID — not the folder name. This means projects survive renames and work correctly across machines.

No remote but inside a git repo? Falls back to the directory name.

**No git repo at all?** (e.g. sessions started from `~` or a plain folder) — no project ID is assigned. All extracted notes go to the daily directory instead of a project folder.

---

## License

MIT
