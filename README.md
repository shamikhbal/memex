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
  → scripts/flush.py (Haiku) extracts decisions, patterns, concepts → ~/.memex/notes/
  → scripts/compile.py (Sonnet) rewrites project index nightly
  → hooks/session-start.py injects budgeted context into your next session
  → memex serve exposes the full knowledge graph as an MCP server
```

Your notes live in `~/.memex/notes/` as plain Obsidian-compatible markdown — readable, portable, yours.

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
- An Anthropic API key (or any OpenAI-compatible endpoint — see [Custom providers](#custom-providers))

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
- **Patterns** — recurring approaches, conventions, things that work in your codebase
- **Concepts** — domain knowledge, library patterns, project-specific terminology
- **Daily digest** — cross-project summary of what you worked on

What gets **ignored**: tool outputs, file reads, boilerplate — only your actual thinking is kept.

---

## Context injection budget

memex never dumps everything into your context. It allocates a fixed budget (default 20,000 chars) split across source tiers:

| Source | Budget |
|--------|--------|
| Project index (`_index.md`) | 35% |
| Decisions log | 15% |
| Today's daily note | 20% |
| Top concepts (graph-ranked) | remaining |

Concept notes are ranked by graph connectivity — the most referenced ideas surface first.

---

## Custom providers

memex supports any OpenAI-compatible endpoint (Ollama, Together, local models) alongside Anthropic. Configure per pipeline stage in `~/.memex/config.yaml`:

```yaml
flush:
  provider: anthropic
  model: claude-haiku-4-5-20251001

compile:
  provider: openai          # or "anthropic"
  model: gpt-4o-mini
  base_url: http://localhost:11434   # Ollama, etc.

pre_filter:
  max_context_chars: 15000
  max_turns: 30

session_start:
  max_inject_chars: 20000
  compile_after_hour: 18    # auto-compile triggers after 6pm
```

---

## Directory structure

```
~/.memex/
├── config.yaml
├── raw/                        # pre-filtered session transcripts
│   └── {project-id}/
├── notes/                      # your knowledge vault (Obsidian-compatible)
│   ├── projects/
│   │   └── {project-id}/
│   │       ├── _index.md       # auto-maintained project overview
│   │       └── decisions.md   # append-only decision log
│   ├── concepts/               # cross-project promoted concepts
│   └── daily/                  # daily digests
├── graph/
│   └── global/graphify-out/    # compiled knowledge graph
└── state/
    └── {project-id}.json       # timestamps, cost tracking
```

---

## How project identity works

memex uses your **git remote URL** as the project ID — not the folder name. This means projects survive renames and work correctly across machines.

No git remote? Falls back to the directory name.

---

## License

MIT
