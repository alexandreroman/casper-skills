"""The `casper` CLI boundary, and the one table mapping normalized lifecycle
events to CLI calls.

EVENT_ACTIONS covers the events whose mapping is a fixed constant. The events
whose mapping depends on payload — session-start, blocked, tasks-changed — are
computed by their own entry points (`hooks/session-start.py`,
`hooks/blocked.py`, `hooks/lib/progress.py::actions_for`, and the opencode
plugin's own counterparts), which still route every call through run() so the
guards apply uniformly.

turn-end sits across both: its status call is this table's, and every entry
point reads it from here, but the entry point then reconciles the progress bar
against the agent's task state (`progress.py::reconcile`) so a bar cannot
outlive the turn that set it. Reading turn-end from the table therefore gives
you only half of it.

tests/test_event_conformance.sh and tests/test_cross_agent_conformance.sh pin
every agent's argv against EVENT_ACTIONS, so the fixed events cannot drift
apart silently. The payload-dependent ones are not derived from this table, so
they get their own dedicated checks instead:
tests/test_cross_agent_conformance.sh separately compares the session-start
triple and the blocked pair each entry point hardcodes against the opencode
plugin's, the progress mapping against `progress.py::actions_for`, and every
agent's whole turn-end sequence against the others under the same task list. A
mapping this file does not reach and no test compares is the one place drift
can still happen silently.
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
