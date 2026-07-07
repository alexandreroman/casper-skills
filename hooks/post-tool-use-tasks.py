#!/usr/bin/env python3
import json, os, re, subprocess, sys

def state_path(session_id):
    data_dir = os.environ.get("CLAUDE_PLUGIN_DATA") or "/tmp/casper-claude-plugin"
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, f"{session_id}.json")

def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_state(path, state):
    with open(path, "w") as f:
        json.dump(state, f)

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
    state = load_state(path)

    if tool_name == "TaskCreate":
        task_id = extract_created_id(tool_response)
        if not task_id:
            return
        state[task_id] = {
            "subject": tool_input.get("subject", ""),
            "activeForm": tool_input.get("activeForm") or tool_input.get("subject", ""),
            "status": "pending",
        }
    elif tool_name == "TaskUpdate":
        task_id = str(tool_input.get("taskId", ""))
        if not task_id:
            return
        status = tool_input.get("status")
        if status == "deleted":
            state.pop(task_id, None)
        else:
            entry = state.setdefault(task_id, {"subject": "", "activeForm": "", "status": "pending"})
            if status:
                entry["status"] = status
            if "subject" in tool_input:
                entry["subject"] = tool_input["subject"]
            if "activeForm" in tool_input:
                entry["activeForm"] = tool_input["activeForm"]
    else:
        return

    save_state(path, state)

    total = len(state)
    completed = sum(1 for t in state.values() if t["status"] == "completed")

    if total == 0 or completed == total:
        # Reset the persisted mirror so the next TaskCreate in this session
        # counts a fresh batch from zero instead of inheriting stale entries.
        save_state(path, {})
        run_casper(["progress", "clear"])
        return

    label = next((t["activeForm"] or t["subject"] for t in state.values() if t["status"] == "in_progress"), None)
    if not label:
        # No in-progress task has a real label to show, so leave the progress
        # bar as-is instead of inventing text Claude never produced.
        return
    # casper treats --current as the 1-based index of the current task, so the
    # in-progress (or next pending) task sits at completed + 1.
    run_casper(["progress", "set", "--total", str(total), "--current", str(completed + 1), "--label", label])

if __name__ == "__main__":
    main()
