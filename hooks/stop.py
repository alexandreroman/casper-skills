#!/usr/bin/env python3
"""Stop: end the turn — report where the work stands, and reconcile the bar.

What a turn ending means is not a constant, so this hook reads the workspace
before it writes to it (`progress.py::turn_end_actions` holds the rule):

  - a `blocked` or `error` on the sidebar is the agent's own verdict about
    something outside the turn, so nothing is reported over it;
  - a progress bar still up means work that outlives the turn — background
    subagents left running — so the turn ends `working`;
  - anything else ends `done`.

Done is reported explicitly because nothing else can derive it: `casper status
set working` (user-prompt-submit.sh / pre-tool-use.sh) puts the workspace under
Casper's explicit-authority latch, suppressing its terminal-scraping detector
until a state releases it. Casper collapses done back to idle once the
workspace is seen.

`status` and `progress` are independent surfaces, so the bar is reconciled here
too. The turn boundary is the one moment the agent is known not to be running,
which makes it both the place a bar the task mirror says the work is done with
is dropped (see `progress.py::reconcile`) and the only place the mirror itself
can be deleted without racing a tool call. A bar with no mirror behind it — the
agent that has no task tool and ran `casper progress` itself — is deliberately
left standing, and is exactly the bar that now holds the turn at `working`;
`hooks/session-end.sh` clears it.
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

    path = None
    tasks = []
    try:
        path = progress.state_path(payload.get("session_id", "default"))
        tasks = list(progress.load(path).values())
    except Exception:
        # An unusable state directory costs the mirror, nothing else: the
        # reads and the status call below still run, on the terms an agent
        # with no task tool at all already gets.
        path = None

    # Two reads and up to two writes inside one hook budget (hooks.json), so
    # no single call may spend it all.
    state = casper.agent_state(timeout=1)
    bar_up = casper.bar_is_up(timeout=1)
    for args in progress.turn_end_actions(tasks, state, bar_up):
        casper.run(args, timeout=1)

    # Nothing in flight means the mirror holds no work still running — it
    # emptied out, or never held anything — and no tool call is running to
    # race the unlink. Anything left here now would outlive the session. Note
    # this is a wider condition than the one that clears the bar: the mirror
    # is this hook's own bookkeeping, so an empty one is always safe to drop.
    if path is not None and progress.nothing_in_flight(tasks):
        try:
            progress.discard(path)
        except Exception:
            pass


if __name__ == "__main__":
    main()
