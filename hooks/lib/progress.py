"""Progress-bar computation, shared by every agent.

Three mappings live here: `actions_for`, run on every task change,
`reconcile`, run at the turn boundary so a bar the task list says the work is
done with cannot outlive that turn, and `turn_end_actions`, the whole of what
a turn ending emits. The first two share one predicate, `nothing_in_flight`,
so they cannot disagree about what "done" means — but only `actions_for` reads
an empty list as done. At the turn boundary an empty list means no task tool
ever reported anything, not that the work finished.

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

# A step the bar will never advance to again. "completed" is universal;
# "cancelled" exists only in opencode's todo tool, and counting it as live
# work is what used to strand the bar: a list whose remaining steps were all
# cancelled had nothing in progress to relabel it with and nothing finished
# enough to clear it, so the last label stood over work that had stopped.
FINISHED = frozenset({"completed", "cancelled"})


def _finished(tasks) -> int:
    return sum(1 for t in tasks if t.get("status") in FINISHED)


def nothing_in_flight(tasks) -> bool:
    """True when a task list describes no work the bar could honestly show.

    Either there are no tasks at all, or every one of them is finished. The
    single predicate behind both the per-update mapping and the turn-end
    reconciliation, so the two can never disagree about what "done" means.
    """
    total = len(tasks)
    return total == 0 or _finished(tasks) == total


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
    # in-progress one sits just past everything the bar is done with.
    return [["progress", "set",
             "--total", str(len(tasks)),
             "--current", str(_finished(tasks) + 1),
             "--label", label]]


def reconcile(tasks):
    """Map a task list to the calls that make the bar honest at a boundary.

    Called where the agent is known not to be running (turn end), and it
    judges the bar only by task state it can actually read. A non-empty list
    with every task finished describes work that is over, so its bar goes —
    including the one `actions_for` left standing for want of a labelled task.
    A task still in flight keeps its bar, so a turn that ends waiting on the
    user still shows where the work stopped.

    An empty list is not "nothing to show" here: it means no task tool ever
    reported anything, which is the agent that has none and drove `casper
    progress` by hand. Its bar is left alone, and for the same reason an
    in-flight task keeps its own — work routinely outlives a turn boundary
    (background agents still running, a turn ended to ask the user a
    question), and the sidebar does not lie about activity in the meantime
    because the agent-state icon reports done/idle on its own. What clears
    that bar is the agent's own `progress clear` when the work is done, and
    session end as the backstop for the one it forgets.
    """
    if not tasks:
        return []
    return CLEAR if nothing_in_flight(tasks) else []


# States an agent reached on its own, about something outside the turn: it is
# waiting on the user, or it failed. No hook can infer either from a turn
# boundary, so turn end reports nothing over them — it would only ever replace
# a verdict with a guess. Every other state is fair game: `working`, `idle` and
# `done` are exactly what turn end is there to decide between.
ASSERTED = frozenset({"blocked", "error"})


def turn_end_actions(tasks, state, bar_up):
    """Everything a turn ending emits, given what the workspace is showing.

    `state` is the sidebar's current state and `bar_up` whether a bar is on
    screen, both read back over the CLI (`casper.py::agent_state`,
    `casper.py::bar_is_up`); `tasks` is the agent's task state, as `reconcile`
    reads it. The rule in one line: a turn ends `working` when a bar is still
    up once this hook is done with it, and `done` otherwise.

    That makes the bar the shared account of whether work is over, which is
    what the turn boundary on its own cannot tell. An agent that dispatches
    background subagents and ends its turn to let them run leaves its bar up
    on purpose; reporting `done` there put the sidebar at odds with the bar
    beside it, and cost the user a completion notification for work still
    running. The other side of that bargain is the agent's: a bar left up over
    finished work now holds the workspace at `working` until session end, so
    clearing it the moment the work is done is what keeps the state honest.

    Reads that fail come back as None/False, and a turn with no bar reports
    `done` — the behaviour this had before either read existed.
    """
    clears = reconcile(tasks)
    if state in ASSERTED:
        return clears
    still_up = bool(bar_up) and not clears
    return [["status", "set", "working" if still_up else "done"]] + clears


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
