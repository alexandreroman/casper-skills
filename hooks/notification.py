#!/usr/bin/env python3
import json, subprocess, sys

FRIENDLY = {
    "permission_prompt": "Claude needs your permission to continue",
    "elicitation_dialog": "Claude needs additional input",
}

# Strict allowlist: only these two types mean "Claude is waiting on the user
# mid-task for something other than the next prompt" (a permission grant, extra
# tool input) — that's exactly the "blocked" state. Every other type, including
# idle_prompt, auth_success, and any unknown/future notification_type, stays
# silent by design: Casper's detection engine covers ordinary idle/turn-end
# events on its own, so notifying here would just duplicate it.
#
# agent_needs_input is deliberately excluded, even though it plausibly also
# means "needs the user": it is not confirmed to fire for a plain Claude Code
# CLI session inside a Casper terminal, so acting on it would be guesswork.
BLOCKING_TYPES = {"permission_prompt", "elicitation_dialog"}

def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Empty or malformed stdin: nothing actionable, exit quietly.
        return
    notification_type = payload.get("notification_type", "")
    if notification_type not in BLOCKING_TYPES:
        return
    # Two sequential casper calls share the hook's 3s budget (see hooks.json),
    # so cap each at 1s: even a stalled first call leaves room for the notify.
    try:
        subprocess.run(
            ["casper", "status", "set", "blocked"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1,
        )
    except Exception:
        pass
    # Prefer Claude Code's own message (more specific) over the canned text.
    message = payload.get("message") or FRIENDLY.get(notification_type, "Claude needs your attention")
    try:
        subprocess.run(
            ["casper", "notify", "--message", message],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1,
        )
    except Exception:
        pass

if __name__ == "__main__":
    main()
