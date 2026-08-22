#!/usr/bin/env python3
"""Stop: end the turn — report done, and reconcile the progress bar.

Done is reported explicitly because nothing else can derive it: the first
`casper status set working` (user-prompt-submit.sh / pre-tool-use.sh) puts the
workspace under Casper's explicit-authority latch, permanently suppressing its
terminal-scraping detector. Casper collapses done back to idle once the
workspace is seen.

`status` and `progress` are independent surfaces, so the bar is reconciled
here too. The turn boundary is the one moment the agent is known not to be
running, which makes it both the only place a bar describing no live work can
be dropped (see `progress.py::reconcile`) and the only place the task mirror
can be deleted without racing a tool call.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hooks.lib import casper, progress


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    # Two calls inside a 3s hook budget, so neither may spend the default 2s.
    casper.emit("turn-end", timeout=1)

    try:
        path = progress.state_path(payload.get("session_id", "default"))
        tasks = list(progress.load(path).values())
        actions = progress.reconcile(tasks)
        # Nothing in flight means the mirror describes work that is over, and
        # no tool call is running to race the unlink. Anything left here now
        # would outlive the session.
        if progress.nothing_in_flight(tasks):
            progress.discard(path)
    except Exception:
        # An unusable state directory must not fail the turn; the status call
        # above already landed, which is the more important of the two.
        return

    for args in actions:
        casper.run(args, timeout=1)


if __name__ == "__main__":
    main()
