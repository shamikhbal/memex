#!/usr/bin/env python3
"""
flush.py — Phase 1 stub. Logs that it was triggered. No API calls.
Phase 2 will add Haiku extraction.
"""
from __future__ import annotations

# RECURSION GUARD — set before any imports that might trigger Claude Code hooks
import os
os.environ["CLAUDE_INVOKED_BY"] = "memory_flush"

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "scripts" / "flush.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [flush] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main() -> None:
    if len(sys.argv) < 3:
        logging.error("Usage: flush.py <raw_file> <project_id>")
        sys.exit(1)

    raw_file = Path(sys.argv[1])
    project_id = sys.argv[2]

    if not raw_file.exists():
        logging.info("raw file not found, skipping: %s", raw_file)
        sys.exit(0)

    content = raw_file.read_text().strip()
    if not content:
        logging.info("raw file empty, skipping: %s", raw_file)
        sys.exit(0)

    logging.info("flush triggered — project=%s raw=%s chars=%d", project_id, raw_file.name, len(content))
    # Phase 2: call Haiku here


if __name__ == "__main__":
    main()
