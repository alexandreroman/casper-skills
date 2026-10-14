#!/usr/bin/env python3
"""Report the blocked state: the agent is waiting on the user mid-turn.

One wait must reach the user as one notification, and the two agents that run
this hook announce a wait differently:

  - Codex fires PermissionRequest when it shows a permission prompt, and
    nothing else. That event alone means "waiting on the user", so it reports
    blocked and notifies.
  - Claude Code fires two events for every dialog, AskUserQuestion included:
    PermissionRequest as the dialog opens, then Notification with
    notification_type `permission_prompt` ("Claude needs your permission")
    about 6 seconds later, and only if the dialog is still unanswered by then.
    PermissionRequest reports blocked straight away. The Notification is the
    one that notifies, so a prompt the user answers within those seconds
    costs them no notification at all. Notification carries every other kind
    of notice too, so its types need a strict allowlist.

Either way, when the agent already ran `casper notify` for this wait, the hook
still reports blocked but leaves the notifying to the agent, whose message
says what it needs (hooks/lib/notified.py).

Nothing fires when the user answers the dialog, so the `blocked` reported here
is marked as the dialog's own (hooks/lib/dialog.py). The approved tool's
PostToolUse reports `working` again, and turn end does not mistake it for a
`blocked` the agent asserted.

Codex is told apart by PLUGIN_ROOT, its own name for the plugin root: Codex
sets it next to the CLAUDE_PLUGIN_ROOT compatibility mirror, Claude Code sets
only the latter.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hooks.lib import casper, dialog, notified

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


def _is_codex() -> bool:
    return bool(os.environ.get("PLUGIN_ROOT"))


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


def _agent_notified(payload) -> bool:
    try:
        return notified.agent_notified(payload.get("session_id", "default"))
    except Exception:
        # Unreadable state reads as "not notified": a duplicate notification
        # beats a wait nobody hears about.
        return False


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
        should_notify = True
    elif event == "PermissionRequest":
        # Under Claude Code the same dialog's Notification follows if the user
        # does not answer it, and that one notifies.
        should_notify = _is_codex()
    else:
        return

    try:
        dialog.open_(payload.get("session_id", "default"))
    except Exception:
        # Without the marker this `blocked` lasts until the next tool call or
        # prompt, as it always did.
        pass

    # Two sequential casper calls share the hook's 3s budget (hooks.json), so
    # cap each at 1s: even a stalled first call leaves room for the notify.
    casper.run(["status", "set", "blocked"], timeout=1)
    if should_notify and not _agent_notified(payload):
        # Attached, like every free-text value: a separate one that starts
        # with `-` reads as an option, and the notification is lost.
        casper.run(["notify", f"--message={_message(payload)}"], timeout=1)


if __name__ == "__main__":
    main()
