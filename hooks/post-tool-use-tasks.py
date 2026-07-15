#!/usr/bin/env python3
import fcntl, json, os, re, subprocess, sys, tempfile

def state_path(session_id):
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA") or "/tmp/casper-claude-plugin"
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, f"{session_id}.json")

def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        # Corrupt file (e.g. left over from before locking/atomic writes were in
        # place). Treat it as recoverable and reset, so a single past corruption
        # can never permanently wedge the progress bar for the session.
        return {}

def save_state(path, state):
    # Atomic write: dump to a temp file in the same directory, then os.replace
    # (atomic on POSIX). A reader — or a racing writer that somehow slips past
    # the lock — can only ever see a complete file, never a half-written or
    # byte-interleaved one.
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

def run_casper(args):
    try:
        subprocess.run(["casper"] + args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
    except Exception:
        pass

def extract_created_id(tool_response):
    if isinstance(tool_response, dict):
        task = tool_response.get("task")
        if isinstance(task, dict) and "id" in task:
            return str(task["id"])
    match = re.search(r"#(\d+)", str(tool_response))
    return match.group(1) if match else None

def main():
    payload = json.load(sys.stdin)
    session_id = payload.get("session_id", "default")
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input", {})
    tool_response = payload.get("tool_response", "")

    path = state_path(session_id)

    # Claude Code fires one PostToolUse process per tool call, so several of
    # these run concurrently within a single turn. Hold an exclusive
    # inter-process lock across the whole read-modify-write so their writes can
    # never interleave and clobber each other. The casper call is computed here
    # but run after the lock is released, to keep the lock hold time to file I/O.
    with open(path + ".lock", "w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        action = update_state(path, tool_name, tool_input, tool_response)

    if action is not None:
        run_casper(action)

def update_state(path, tool_name, tool_input, tool_response):
    """Apply one tool call to the persisted state and return the casper args to
    run (or None for a no-op). Must be called while holding the session lock."""
    state = load_state(path)

    if tool_name == "TaskCreate":
        task_id = extract_created_id(tool_response)
        if not task_id:
            return None
        state[task_id] = {
            "subject": tool_input.get("subject", ""),
            "activeForm": tool_input.get("activeForm") or tool_input.get("subject", ""),
            "status": "pending",
        }
    elif tool_name == "TaskUpdate":
        task_id = str(tool_input.get("taskId", ""))
        if not task_id:
            return None
        status = tool_input.get("status")
        if status == "deleted":
            state.pop(task_id, None)
        elif task_id in state:
            # Only mutate a task we already track. A legitimate TaskUpdate is
            # always preceded by the TaskCreate the hook recorded.
            entry = state[task_id]
            if status:
                entry["status"] = status
            if "subject" in tool_input:
                entry["subject"] = tool_input["subject"]
            if "activeForm" in tool_input:
                entry["activeForm"] = tool_input["activeForm"]
        else:
            # Unknown id: a PostToolUse hook fires even when the TaskUpdate
            # failed ("Task not found"). Ignore it so no phantom entry is
            # created that would wedge the progress bar open.
            return None
    else:
        return None

    save_state(path, state)

    total = len(state)
    completed = sum(1 for t in state.values() if t["status"] == "completed")

    if total == 0 or completed == total:
        # Reset the persisted mirror so the next TaskCreate in this session
        # counts a fresh batch from zero instead of inheriting stale entries.
        save_state(path, {})
        return ["progress", "clear"]

    label = next(
        (lbl for t in state.values()
         if t["status"] == "in_progress" and (lbl := (t["activeForm"] or t["subject"]))),
        None,
    )
    if not label:
        # No in-progress task has a real label to show, so leave the progress
        # bar as-is instead of inventing text Claude never produced.
        return None
    # casper treats --current as the 1-based index of the current task, so the
    # in-progress (or next pending) task sits at completed + 1.
    return ["progress", "set", "--total", str(total), "--current", str(completed + 1), "--label", label]

if __name__ == "__main__":
    main()
