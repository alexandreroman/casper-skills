#!/usr/bin/env python3
"""Keep the per-session markers in step with a hook.

Two markers live under the data dir: the agent's own notify
(hooks/lib/notified.py) and a dialog's `blocked` (hooks/lib/dialog.py).

  tool       PreToolUse: advance the notify marker; the dialog is over.
  subagent-tool
             PreToolUse from a subagent: the dialog is over, so report
             `working` again; nothing else. Exits 1 when the payload is not a
             subagent's, so hooks/pre-tool-use.sh takes the agent's path.
  tool-done  PostToolUse: the dialog's tool ran, so report `working` again,
             unless that tool set a status itself.
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
    command = sys.argv[1:]
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = None
    if not isinstance(payload, dict):
        sys.exit(1 if command == ["subagent-tool"] else 0)

    session_id = payload.get("session_id", "default")
    if command == ["subagent-tool"]:
        if not payload.get("agent_id"):
            sys.exit(1)
        # Not the agent moving on, so its notify marker stays where it is. A
        # dialog's `blocked` still ends here: it may be the subagent's own
        # prompt, denied, and no other hook says so (hooks/lib/dialog.py).
        if _quietly(dialog.close, session_id):
            casper.run(["status", "set", "working"], timeout=1)
    elif command == ["tool"]:
        _quietly(notified.observe_tool, payload)
        _quietly(dialog.close, session_id)
    elif command == ["tool-done"]:
        ended = _quietly(dialog.close, session_id)
        # Codex asks approval for the agent's own `casper status set blocked`
        # until the user allows `casper` for good. That call has just run, and
        # its state is newer than anything this hook could report over it.
        sets_status = "status" in (_quietly(notified.casper_subcommands,
                                            payload.get("tool_input")) or [])
        if ended and not sets_status:
            casper.run(["status", "set", "working"], timeout=1)
    elif command == ["clear"]:
        _quietly(notified.clear, session_id)
        _quietly(dialog.close, session_id)


if __name__ == "__main__":
    main()
