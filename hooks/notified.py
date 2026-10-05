#!/usr/bin/env python3
"""Keep the agent-notified marker (hooks/lib/notified.py) in step with a hook.

`tool` advances it for one PreToolUse payload; `clear` drops it, at the next
prompt or at session end. The Bash hooks call this only when there is
something to do, so the PreToolUse hot path stays in Bash.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hooks.lib import notified


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    if not isinstance(payload, dict):
        return

    try:
        if sys.argv[1:] == ["tool"]:
            notified.observe_tool(payload)
        elif sys.argv[1:] == ["clear"]:
            notified.clear(payload.get("session_id", "default"))
    except Exception:
        # A marker that cannot be kept costs a duplicate notification, never
        # the tool call or the prompt this hook runs alongside.
        pass


if __name__ == "__main__":
    main()
