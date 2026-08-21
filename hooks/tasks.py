#!/usr/bin/env python3
"""PostToolUse: mirror the agent's task list into the sidebar progress bar.

Two dialects arrive here. Claude Code reports one change at a time through
TaskCreate/TaskUpdate, so its changes accumulate in a per-session mirror.
Codex's update_plan carries the whole plan every time, so it needs no mirror
at all and takes the same path opencode does.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hooks.lib import casper, progress

INCREMENTAL = {"TaskCreate", "TaskUpdate"}
WHOLE_LIST = {"update_plan"}


def _created_id(tool_response):
    if isinstance(tool_response, dict):
        task = tool_response.get("task")
        if isinstance(task, dict) and "id" in task:
            return str(task["id"])
    match = re.search(r"#(\d+)", str(tool_response))
    return match.group(1) if match else None


def _tasks_from_update_plan(tool_input):
    """Codex sends {"plan": [{"step": ..., "status": ...}, ...]}."""
    plan = tool_input.get("plan")
    if not isinstance(plan, list):
        return None
    return [{"label": s.get("step", ""), "status": s.get("status", "pending")}
            for s in plan if isinstance(s, dict)]


def _apply_incremental(path, tool_name, tool_input, tool_response):
    """Fold one change into the mirror. Returns the task list, or None."""
    state = progress.load(path)

    if tool_name == "TaskCreate":
        task_id = _created_id(tool_response)
        if not task_id:
            return None
        state[task_id] = {
            "label": tool_input.get("activeForm") or tool_input.get("subject", ""),
            "status": "pending",
        }
    else:  # TaskUpdate
        task_id = str(tool_input.get("taskId", ""))
        if not task_id:
            return None
        status = tool_input.get("status")
        if status == "deleted":
            state.pop(task_id, None)
        elif task_id in state:
            if status:
                state[task_id]["status"] = status
            label = tool_input.get("activeForm") or tool_input.get("subject")
            if label:
                state[task_id]["label"] = label
        else:
            # PostToolUse fires even when the TaskUpdate itself failed. Ignore
            # the unknown id rather than create a phantom that wedges the bar.
            return None

    tasks = list(state.values())
    # Reset the mirror once the batch is done, so the next TaskCreate counts
    # from zero instead of inheriting stale entries.
    progress.save(path, {} if progress.nothing_in_flight(tasks) else state)
    return tasks


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}

    if tool_name in WHOLE_LIST:
        tasks = _tasks_from_update_plan(tool_input)
    elif tool_name in INCREMENTAL:
        try:
            path = progress.state_path(payload.get("session_id", "default"))
            # Hold the lock across the whole read-modify-write; compute the
            # casper call inside, run it after releasing, so the lock covers
            # file I/O only.
            with progress.locked(path):
                tasks = _apply_incremental(path, tool_name, tool_input,
                                           payload.get("tool_response", ""))
        except Exception:
            # An unusable state directory (e.g. CLAUDE_PLUGIN_DATA pointing at
            # a file, or a path this process cannot write to) must not fail
            # the turn. Skipping the mirror costs one progress update;
            # raising here would error every tool call in the session.
            return
    else:
        return

    if tasks is None:
        return
    for args in progress.actions_for(tasks) or []:
        casper.run(args, timeout=2)


if __name__ == "__main__":
    main()
