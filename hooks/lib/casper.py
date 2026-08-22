"""The `casper` CLI boundary, and the one table mapping normalized lifecycle
events to CLI calls.

EVENT_ACTIONS covers only the events whose mapping is a fixed constant.
session-start, blocked and tasks-changed depend on their payload, so each
entry point computes its own (`hooks/session-start.py`, `hooks/blocked.py`,
`progress.py::actions_for`, and the opencode plugin's counterparts) while
still routing every call through run(), so the guards apply uniformly.

turn-end straddles the two: the status call below is the whole of it here, but
the entry point then reconciles the progress bar against the agent's task
state (`progress.py::reconcile`) so a bar cannot outlive the turn that set it.

tests/test_event_conformance.sh pins the fixed events against this table, and
tests/test_cross_agent_conformance.sh compares every agent's argv — the
payload-dependent mappings included — against each other. A mapping neither
reaches is the one place drift can still happen silently.
"""
import os
import subprocess

EVENT_ACTIONS: "dict[str, list[list[str]]]" = {
    "turn-start":    [["status", "set", "working"]],
    "tool-activity": [["status", "set", "working"]],
    "turn-end":      [["status", "set", "done"]],
    "session-end":   [["status", "set", "done"]],
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
