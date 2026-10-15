"""Whether the agent already told the user, in its own words, that it needs them.

The session guidance has the agent run `casper notify` itself whenever it is
about to wait on the user, and it then usually opens the very dialog
hooks/blocked.py reports: an AskUserQuestion, a permission prompt. Each of
those reached the user twice, once in the agent's words and once in the hook's
generic ones. Casper drops a repeat notification only within 3 seconds, and
Claude Code sends its Notification(permission_prompt) about 6 seconds after the
dialog opens, so nothing downstream could catch the pair.

So the agent's own notify is recorded in a per-session marker, and blocked.py
still reports `blocked` while it stands but leaves the notifying to the agent.
The marker spans one blocking episode, advanced by PreToolUse:

  armed      the agent ran `casper notify`.
  attached   the next real tool call started. It is the one that opens the
             dialog the agent announced, so its prompt is still covered.
  (removed)  the real tool call after that: the agent moved on, and a prompt
             from here on is a new wait the user has not been told about.
             The next prompt, turn end and session end remove it too.

A tool call that only runs `casper` (`casper status set blocked`, typically) is
bookkeeping, not work, and leaves the marker where it is.

The opencode plugin keeps the same three states in memory
(.opencode/plugin/casper.js), and tests/test_cross_agent_conformance.sh holds
the two to the same outcome.
"""
import os
import re
import tempfile

from hooks.lib import progress

ARMED = "armed"
ATTACHED = "attached"

# A `casper` invocation in command position: at the start of the command, or
# right after a separator (`;`, `&&`, `||`, `|`, `(`, `{`, a newline). That
# keeps a `grep "casper notify"` from reading as the agent notifying. The `{`
# matters: agents often wrap the pair as `[ -n "$CASPER_WORKSPACE_ID" ] &&
# { casper notify ...; casper status set blocked; }`, and missing it let the
# dialog's own notification follow the agent's.
_CASPER_CALL = re.compile(r"(?:^|[;&|({\n])\s*casper\s+([a-z]+)")


def casper_subcommands(tool_input) -> list:
    """The `casper` subcommands a tool call runs, in order. Empty for none.

    Claude Code's Bash tool sends `command` as a string. An argv list (`bash
    -lc "..."`) is joined one element per line, so each element is searched
    as a command of its own.
    """
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if isinstance(command, list):
        command = "\n".join(str(part) for part in command)
    if not isinstance(command, str):
        return []
    return _CASPER_CALL.findall(command)


def marker_path(session_id: str) -> str:
    return os.path.join(progress.data_dir(), f"{session_id}.notified")


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _write(path, state) -> None:
    # Atomic for the same reason as progress.save: parallel tool calls each
    # run their own hook, and none may read a half-written marker.
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".notified")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(state)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def observe_tool(payload) -> None:
    """Advance the session's marker for one PreToolUse payload."""
    path = marker_path(payload.get("session_id", "default"))
    subcommands = casper_subcommands(payload.get("tool_input"))
    if "notify" in subcommands:
        _write(path, ARMED)
    elif subcommands:
        return
    elif _read(path) == ARMED:
        _write(path, ATTACHED)
    else:
        clear(payload.get("session_id", "default"))


def clear(session_id: str) -> None:
    try:
        os.unlink(marker_path(session_id))
    except OSError:
        pass


def agent_notified(session_id: str) -> bool:
    """True while the agent's own notify covers the wait being reported."""
    return _read(marker_path(session_id)) in (ARMED, ATTACHED)
