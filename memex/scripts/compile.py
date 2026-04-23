#!/usr/bin/env python3
"""
compile.py — uses Sonnet to write each project's _index.md, then triggers graphify.
Called as: python -m memex.scripts.compile <project_id> [memex_dir]
Also importable as module: from memex.scripts.compile import compile_project
"""
from __future__ import annotations

import os
os.environ["CLAUDE_INVOKED_BY"] = "memory_flush"

import logging
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = Path(os.environ.get("MEMEX_DIR", Path.home() / ".memex")) / "flush.log"
if not (ROOT / "__init__.py").exists():
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [compile] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from memex.config import Config
from memex.llm_client import LLMClient

INDEX_PROMPT = """\
You are a knowledge base curator. Read all the notes below for the project "{project_id}" and write a concise _index.md — a living overview of this project.

Include:
- What the project does (1-2 sentences)
- Key decisions made (bulleted)
- Key concepts and patterns documented (bulleted)
- Current status if determinable

Be concise. Max 300 words. Use markdown. Do not include the date.

Notes:
{notes_content}"""


def compile_project(project_id: str, memex_dir: Optional[Path] = None) -> None:
    """Write/update _index.md for a project and trigger graphify."""
    if memex_dir is None:
        memex_dir = Path.home() / ".memex"

    config = Config(memex_dir=memex_dir)
    proj_dir = config.notes_dir / "projects" / project_id

    # Collect all non-index markdown notes
    note_files = [f for f in proj_dir.glob("*.md") if f.name != "_index.md"] if proj_dir.exists() else []
    if not note_files:
        logging.info("no notes found for project %s, skipping", project_id)
        return

    notes_content = ""
    for f in sorted(note_files):
        notes_content += f"\n\n### {f.stem}\n\n{f.read_text()}"

    prompt = INDEX_PROMPT.replace("{project_id}", project_id).replace("{notes_content}", notes_content.strip())
    client = LLMClient.from_config(config, stage="compile")

    try:
        response = client.complete(prompt=prompt, max_tokens=1024)
        index_content = response.text.strip()
    except Exception as e:
        logging.error("compile LLM error for %s: %s", project_id, e)
        return

    index_path = proj_dir / "_index.md"
    index_path.write_text(index_content + "\n")
    logging.info("wrote _index.md for project %s", project_id)

    _run_graphify(memex_dir, config)


def _run_graphify(memex_dir: Path, config: "Config") -> None:
    """Extract a knowledge graph from notes using graphify's LLM pipeline."""
    try:
        from graphify.llm import extract_files_direct
        from graphify.build import build_from_json
        from graphify.cluster import cluster, score_all
        from graphify.analyze import god_nodes, surprising_connections, suggest_questions
        from graphify.report import generate
        from graphify.export import to_json
    except ImportError:
        logging.info("graphify not installed, skipping graph update")
        return

    notes_dir = memex_dir / "notes"
    out_dir = memex_dir / "graph" / "global" / "graphify-out"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Collect all markdown notes
    md_files = sorted(notes_dir.rglob("*.md"))
    if not md_files:
        logging.info("no markdown files found for graph extraction")
        return

    # Map memex provider/model to graphify backend
    provider = config.compile_provider
    base_url = config.compile_base_url
    model = config.compile_model

    if provider == "ollama":
        backend = "openai"
        api_key = "ollama"
    elif provider == "openai":
        backend = "openai"
        api_key = os.environ.get("OPENAI_API_KEY", "")
    elif provider == "anthropic":
        backend = "claude"
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    else:
        logging.error("unsupported provider for graphify: %s", provider)
        return

    try:
        # Monkey-patch base_url for ollama/custom endpoints
        if base_url and backend == "openai":
            from graphify import llm as _graphify_llm
            _graphify_llm.BACKENDS["openai"] = {
                **_graphify_llm.BACKENDS["openai"],
                "base_url": base_url,
            }

        extraction = extract_files_direct(
            files=md_files,
            backend=backend,
            api_key=api_key,
            model=model,
            root=notes_dir,
        )

        G = build_from_json(extraction)
        if G.number_of_nodes() == 0:
            logging.warning("graphify extracted 0 nodes, skipping graph write")
            return

        communities = cluster(G)
        cohesion = score_all(G, communities)
        gods = god_nodes(G)
        surprises = surprising_connections(G, communities)
        labels = {cid: f"Community {cid}" for cid in communities}
        questions = suggest_questions(G, communities, labels)

        report = generate(
            G, communities, cohesion, labels, gods, surprises,
            detection_result={
                "total_files": len(md_files),
                "total_words": sum(f.read_text().split().__len__() for f in md_files),
                "files": {"code": [], "document": [str(f) for f in md_files], "paper": [], "image": []},
            },
            token_cost=extraction.get("input_tokens", 0) and {"input_tokens": extraction.get("input_tokens", 0), "output_tokens": extraction.get("output_tokens", 0)} or {"input_tokens": 0, "output_tokens": 0},
            root=str(notes_dir),
            suggested_questions=questions,
        )
        (out_dir / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
        to_json(G, communities, str(out_dir / "graph.json"))

        logging.info(
            "graphify: %d nodes, %d edges, %d communities → %s",
            G.number_of_nodes(), G.number_of_edges(),
            len(communities), out_dir / "graph.json",
        )
    except Exception as e:
        logging.error("graphify extraction error: %s", e)


def main() -> None:
    if len(sys.argv) < 2:
        logging.error("Usage: compile.py <project_id> [memex_dir]")
        sys.exit(1)

    project_id = sys.argv[1]
    memex_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    compile_project(project_id=project_id, memex_dir=memex_dir)


if __name__ == "__main__":
    main()
