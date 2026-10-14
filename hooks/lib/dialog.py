"""Whether the sidebar's `blocked` is one hooks/blocked.py reported for a dialog.

blocked.py reports `blocked` as a dialog opens. Nothing tells a hook when the
user answers it: measured on Claude Code 2.1.289, an approved tool is followed
by its PostToolUse once it has run, and a denial interrupts the turn with no
event at all until the next prompt. So that `blocked` used to outlive the
dialog. When the approved call was the last of the turn, hooks/stop.py read
it back as the agent's own verdict and left the workspace blocked over a turn
that had finished.

A per-session marker records that the current `blocked` came from a dialog,
and every hook that knows the dialog is over closes it:

  PostToolUse        the approved tool ran: report `working` again
                     (hooks/post-tool-use.sh).
  PreToolUse         a new tool call started, and it reports `working` itself
                     (markers.py does for a subagent's, which reports nothing
                     otherwise).
  Stop               the turn ended: the `blocked` is not the agent's verdict,
                     so turn end reports over it.
  UserPromptSubmit,  the wait is over whatever happened to it.
  SessionEnd

A denied dialog has none of these until the next prompt, so it stays blocked,
which is right: the agent is waiting to be told what to do instead. A
`casper status set blocked` the agent ran itself never opens a marker, so it
still stands until the agent acts again.
"""
import os

from hooks.lib import progress


def marker_path(session_id: str) -> str:
    return os.path.join(progress.data_dir(), f"{session_id}.dialog")


def open_(session_id: str) -> None:
    path = marker_path(session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w"):
        pass


def close(session_id: str) -> bool:
    """Drop the marker. True when there was one, i.e. a dialog just ended."""
    try:
        os.unlink(marker_path(session_id))
        return True
    except OSError:
        return False
