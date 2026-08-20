#!/usr/bin/env python3
"""SessionStart: reset the workspace surfaces and inject the guidance.

Claude Code and Codex send an identical payload here, including the same
`source` values (startup | resume | clear | compact), so one implementation
serves both.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hooks.lib import casper
from hooks.lib.guidance import TEXT

# `resume` and `compact` continue an existing session, so the info panel still
# describes work this session knows about. Any other source is a fresh
# conversation, whose panel would describe work it knows nothing about.
CONTINUING = {"resume", "compact"}


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    casper.run(["status", "set", "idle"], timeout=1)
    casper.run(["progress", "clear"], timeout=1)
    if payload.get("source") not in CONTINUING:
        casper.run(["info", "clear"], timeout=1)

    # SessionStart stdout is added to the agent's context.
    sys.stdout.write(TEXT)


if __name__ == "__main__":
    main()
