"""Progress-bar computation, shared by every agent.

Two shapes of input converge here. Claude Code and Codex report task changes
one at a time, so their entry point keeps a per-session mirror on disk and
feeds the whole mirror in. opencode's todo.updated carries the entire list on
every change, so it feeds that list in directly and never touches the mirror.
"""
import contextlib
import fcntl
import json
import os
import tempfile


def actions_for(tasks):
    """Map a task list to casper argv.

    Returns [["progress","clear"]] when there is nothing to show, None when
    the bar should be left exactly as it is, else the progress set call.
    """
    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("status") == "completed")

    if total == 0 or completed == total:
        return [["progress", "clear"]]

    label = next(
        (t.get("label") for t in tasks
         if t.get("status") == "in_progress" and t.get("label")),
        None,
    )
    if not label:
        # No in-progress task carries a real label, so there is nothing honest
        # to display. Leave the bar alone rather than invent text.
        return None

    # casper reads --current as the 1-based index of the current task, so the
    # in-progress one sits at completed + 1.
    return [["progress", "set",
             "--total", str(total),
             "--current", str(completed + 1),
             "--label", label]]


def state_path(session_id: str) -> str:
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA") or "/tmp/casper-skills"
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, f"{session_id}.json")


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, ValueError):
        # A corrupt mirror is recoverable: reset rather than wedge the bar for
        # the rest of the session.
        return {}


def save(path, state) -> None:
    # Atomic: write a sibling temp file, then os.replace. A reader can only
    # ever see a complete file.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@contextlib.contextmanager
def locked(path):
    """Hold an exclusive inter-process lock across a read-modify-write.

    One hook process runs per tool call, so several race within a turn. The
    .lock file is deliberately never unlinked: removing it would let one
    process create a fresh inode while another still holds the old one.
    """
    with open(path + ".lock", "w") as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
