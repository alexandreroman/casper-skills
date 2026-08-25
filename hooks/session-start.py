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
from hooks.lib import guidance

# `resume` and `compact` continue an existing session, so the info panel still
# describes work this session knows about. Any other source is a fresh
# conversation, whose panel would describe work it knows nothing about.
CONTINUING = {"resume", "compact"}


def plugin_root() -> str:
    """Where this plugin is installed, under either agent's name for it."""
    return (os.environ.get("CLAUDE_PLUGIN_ROOT")
            or os.environ.get("PLUGIN_ROOT")
            or "")


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    # SessionStart stdout is added to the agent's context. Write it before
    # any casper call: the hook runs inside a fixed time budget, and a
    # stalled or slow `casper` call must not cost the session its whole
    # context injection, which is the more important of the two effects.
    #
    # The skill's path lands in the guidance absolute: this is the one moment
    # where where-the-plugin-lives is known, and spending it turns "find the
    # casper skill" into one file read with nothing to resolve. Codex's own
    # name for the variable is PLUGIN_ROOT and it exports CLAUDE_PLUGIN_ROOT
    # only as a compatibility mirror, so the native name is the fallback
    # rather than a second thing to keep in sync.
    sys.stdout.write(guidance.render(plugin_root()))

    casper.run(["status", "set", "idle"], timeout=1)
    casper.run(["progress", "clear"], timeout=1)
    if payload.get("source") not in CONTINUING:
        casper.run(["info", "clear"], timeout=1)


if __name__ == "__main__":
    main()
