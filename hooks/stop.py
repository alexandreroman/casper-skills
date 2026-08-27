#!/usr/bin/env python3
"""Stop: end the turn — report done, and reconcile the progress bar.

Done is reported explicitly because nothing else can derive it: the first
`casper status set working` (user-prompt-submit.sh / pre-tool-use.sh) puts the
workspace under Casper's explicit-authority latch, permanently suppressing its
terminal-scraping detector. Casper collapses done back to idle once the
workspace is seen.

`status` and `progress` are independent surfaces, so the bar is reconciled
here too. The turn boundary is the one moment the agent is known not to be
running, which makes it both the place a bar the task mirror says the work is
done with is dropped (see `progress.py::reconcile`) and the only place the
mirror itself can be deleted without racing a tool call. A bar with no mirror
behind it — the agent that has no task tool and ran `casper progress` itself —
is deliberately left standing; `hooks/session-end.sh` is what clears that one.
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
        # Nothing in flight means the mirror holds no work still running —
        # it emptied out, or never held anything — and no tool call is
        # running to race the unlink. Anything left here now would outlive
        # the session. Note this is a wider condition than the one that
        # clears the bar: the mirror is this hook's own bookkeeping, so an
        # empty one is always safe to drop.
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
