#!/usr/bin/env python3
"""Stop: end the turn — report done, and reconcile the progress bar.

Report done explicitly. Every workspace this plugin drives is under Casper's
explicit-authority latch from the very first `casper status set working` call
onward (user-prompt-submit.sh / pre-tool-use.sh) — which permanently
suppresses Casper's terminal-scraping detector for it, so detection can never
derive "done" here on its own. Casper collapses this back to idle once the
workspace is selected (seen).

Then reconcile the bar against the session's task mirror. `status` and
`progress` are two independent surfaces, and until this hook existed nothing
kept them in agreement: a bar set during the turn survived every later turn
until the session restarted, so a workspace could sit at done/idle while still
advertising an in-flight step. The turn boundary is the one moment the agent
is known not to be running, so it is where a bar that no longer describes live
work has to go. See `hooks/lib/progress.py::reconcile` for what survives it.
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
    except Exception:
        # An unusable state directory must not fail the turn; the status call
        # above already landed, which is the more important of the two.
        return

    for args in progress.reconcile(tasks):
        casper.run(args, timeout=1)


if __name__ == "__main__":
    main()
