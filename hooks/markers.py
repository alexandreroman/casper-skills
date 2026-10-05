#!/usr/bin/env python3
"""Keep the per-session markers in step with a hook.

Two markers live under the data dir: the agent's own notify
(hooks/lib/notified.py) and a dialog's `blocked` (hooks/lib/dialog.py).

  tool       PreToolUse: advance the notify marker; the dialog is over.
  tool-done  PostToolUse: the dialog's tool ran, so report `working` again.
  clear      UserPromptSubmit, SessionEnd: drop both.

The Bash hooks call this only when there is something to do, so the tool-call
hot path stays in Bash.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hooks.lib import casper, dialog, notified


def _quietly(step, *args):
    # A marker that cannot be kept costs a duplicate notification or a stale
    # `blocked`, never the tool call or the prompt this hook runs alongside.
    try:
        return step(*args)
    except Exception:
        return None


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    if not isinstance(payload, dict):
        return

    session_id = payload.get("session_id", "default")
    command = sys.argv[1:]
    if command == ["tool"]:
        _quietly(notified.observe_tool, payload)
        _quietly(dialog.close, session_id)
    elif command == ["tool-done"]:
        if _quietly(dialog.close, session_id):
            casper.run(["status", "set", "working"], timeout=1)
    elif command == ["clear"]:
        _quietly(notified.clear, session_id)
        _quietly(dialog.close, session_id)


if __name__ == "__main__":
    main()
