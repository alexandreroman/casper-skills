"""Progress-bar computation, shared by every agent.

Two mappings live here: `actions_for`, run on every task change, and
`reconcile`, run at the turn boundary so a bar describing no live work cannot
survive the turn that set it. They share one predicate, `nothing_in_flight`,
so they cannot disagree about when there is nothing to show.

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


CLEAR = [["progress", "clear"]]


def nothing_in_flight(tasks) -> bool:
    """True when a task list describes no work the bar could honestly show.

    Either there are no tasks at all, or every one of them is finished. The
    single predicate behind both the per-update mapping and the turn-end
    reconciliation, so the two can never disagree about what "done" means.
    """
    total = len(tasks)
    return total == 0 or sum(1 for t in tasks if t.get("status") == "completed") == total


def actions_for(tasks):
    """Map a task list to casper argv.

    Returns CLEAR when there is nothing to show, None when the bar should be
    left exactly as it is, else the progress set call.
    """
    if nothing_in_flight(tasks):
        return CLEAR

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
    completed = sum(1 for t in tasks if t.get("status") == "completed")
    return [["progress", "set",
             "--total", str(len(tasks)),
             "--current", str(completed + 1),
             "--label", label]]


def reconcile(tasks):
    """Map a task list to the calls that make the bar honest at a boundary.

    Called where the agent is known not to be running (turn end). The bar
    claims "step N of M, right now"; with nothing in flight that claim is
    false, so it must go whoever set it — including the bar `actions_for`
    left standing for want of a labelled task, and the one an agent with no
    task tool drove by hand, neither of which any other path clears.

    A task genuinely still in flight keeps its bar, so a turn that ends
    waiting on the user still shows where the work stopped.
    """
    return CLEAR if nothing_in_flight(tasks) else []


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

    One hook process runs per tool call, so several race within a turn.
    Unlinking the .lock mid-turn would let one process create a fresh inode
    while another still holds the old one, so only `discard` removes it — at
    the turn boundary, where no tool call is in flight.
    """
    with open(path + ".lock", "w") as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield


def discard(path) -> None:
    """Delete a session's mirror and its lock. Safe only at a turn boundary.

    Without this the pair outlives every session that ever tracked a task,
    accumulating in the data directory for as long as it survives.
    """
    for target in (path, path + ".lock"):
        try:
            os.unlink(target)
        except OSError:
            pass
