"""The `casper` CLI boundary, and the one table mapping normalized lifecycle
events to CLI calls.

EVENT_ACTIONS covers the events whose mapping is a fixed constant. The three
events whose mapping depends on payload — session-start, blocked,
tasks-changed — are computed by their own entry points, which still route
every call through run() so the guards apply uniformly.

Every agent's tests assert against this table, so a Bash hook, a Python entry
point, and the opencode plugin can never drift apart silently.
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
