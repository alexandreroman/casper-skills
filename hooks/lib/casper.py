"""The `casper` CLI boundary, and the one table mapping normalized lifecycle
events to CLI calls.

EVENT_ACTIONS covers only the events whose mapping is a fixed constant.
session-start, turn-end, blocked and tasks-changed depend on state the table
cannot hold, so each entry point computes its own (`hooks/session-start.py`,
`hooks/stop.py` through `progress.py::turn_end_actions`, `hooks/blocked.py`,
`progress.py::actions_for`, and the opencode plugin's counterparts) while
still routing every call through run(), so the guards apply uniformly.

turn-end left the table when it stopped being a constant. What a turn ending
means depends on what the workspace is showing: a bar still up means work that
outlives the turn, and a `blocked` or `error` is the agent's own verdict, which
no hook can infer and none may overwrite. Both are read back over the CLI here
(`agent_state`, `bar_is_up`) and decided in `progress.py::turn_end_actions`.
turn-error is the one turn ending that stays a constant, because a turn the
API killed has nothing to weigh: the failure is the whole of what the
workspace has to say, so `hooks/stop-failure.sh` reports it and reads nothing
back. session-end stays constant, and is the backstop for a bar turn-end leaves
standing: it clears the bar unconditionally, so nothing the agent set by hand
can outlive the session.

tests/test_event_conformance.sh pins the fixed events against this table, and
tests/test_cross_agent_conformance.sh compares every agent's argv — the
payload-dependent mappings included — against each other. A mapping neither
reaches is the one place drift can still happen silently.
"""
import json
import os
import subprocess

EVENT_ACTIONS: "dict[str, list[list[str]]]" = {
    "turn-start":    [["status", "set", "working"]],
    "tool-activity": [["status", "set", "working"]],
    "turn-error":    [["status", "set", "error"]],
    "session-end":   [["status", "set", "done"], ["progress", "clear"]],
}


def in_workspace() -> bool:
    """True inside a terminal Casper opened."""
    return bool(os.environ.get("CASPER_WORKSPACE_ID"))


def run(args, timeout: float = 2.0) -> None:
    """Invoke `casper` fire-and-forget. Never raises, never blocks a turn."""
    if not in_workspace():
        return
    try:
        subprocess.run(
            ["casper"] + list(args),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except Exception:
        pass


def emit(event: str, timeout: float = 2.0) -> None:
    """Run every CLI call the table maps to `event`. Unknown event: no-op."""
    for args in EVENT_ACTIONS.get(event, []):
        run(args, timeout=timeout)


def query(args, timeout: float = 2.0):
    """Invoke `casper` for an answer: its parsed JSON, or None if it has none.

    The read counterpart of run(), under the same rule that Casper may never
    interrupt a turn — every failure reads as None. That covers the CLI being
    absent, the app not running, a timeout, and, deliberately, a `casper` too
    old to know the verb: it exits 64 on an unknown subcommand, so a plugin
    ahead of the app degrades to the behaviour it had before the verb existed
    rather than to an error.
    """
    if not in_workspace():
        return None
    try:
        proc = subprocess.run(
            ["casper"] + list(args),
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        return None


def agent_state(timeout: float = 2.0):
    """The state the sidebar is showing, or None when it cannot be read."""
    answer = query(["status", "get"], timeout=timeout)
    return answer.get("status") if isinstance(answer, dict) else None


def bar_is_up(timeout: float = 2.0) -> bool:
    """Whether a progress bar is on screen right now, whoever set it.

    The one question the hooks cannot answer from their own bookkeeping: the
    task mirror sees the bars a task tool drove, and nothing sees a bar the
    agent set by hand with `casper progress set`. Unreadable reads as no bar,
    which keeps turn end reporting `done` exactly as it did before.
    """
    answer = query(["progress", "get"], timeout=timeout)
    return isinstance(answer, dict) and answer.get("progress") is not None
