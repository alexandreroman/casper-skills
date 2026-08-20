#!/usr/bin/env python3
"""Report the blocked state: the agent is waiting on the user mid-turn.

Claude Code routes every kind of notice through one Notification event, so its
payloads need a strict allowlist. Codex has a typed PermissionRequest event,
which by definition already means "waiting on the user" and needs no filter.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hooks.lib import casper

# Only these two mean "waiting on the user mid-task for something other than
# the next prompt". Every other type, including idle_prompt, auth_success, and
# any future one, stays silent: Casper's own detection covers ordinary
# idle/turn-end events, so notifying here would duplicate it.
#
# agent_needs_input is excluded deliberately. It plausibly also means "needs
# the user", but it is not confirmed to fire for a plain CLI session inside a
# Casper terminal, so acting on it would be guesswork.
BLOCKING_NOTIFICATION_TYPES = {"permission_prompt", "elicitation_dialog"}

FRIENDLY = {
    "permission_prompt": "The agent needs your permission to continue",
    "elicitation_dialog": "The agent needs additional input",
}


def _message(payload) -> str:
    """Prefer the agent's own wording; fall back to something specific."""
    if payload.get("message"):
        return payload["message"]

    if payload.get("hook_event_name") == "PermissionRequest":
        tool_input = payload.get("tool_input")
        description = tool_input.get("description") if isinstance(tool_input, dict) else None
        target = description or payload.get("tool_name") or "an action"
        return f"The agent needs your approval: {target}"

    return FRIENDLY.get(payload.get("notification_type", ""),
                        "The agent needs your attention")


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Empty or malformed stdin: nothing actionable, exit quietly.
        return

    event = payload.get("hook_event_name")
    if event == "Notification":
        if payload.get("notification_type") not in BLOCKING_NOTIFICATION_TYPES:
            return
    elif event != "PermissionRequest":
        return

    # Two sequential casper calls share the hook's 3s budget (hooks.json), so
    # cap each at 1s: even a stalled first call leaves room for the notify.
    casper.run(["status", "set", "blocked"], timeout=1)
    casper.run(["notify", "--message", _message(payload)], timeout=1)


if __name__ == "__main__":
    main()
