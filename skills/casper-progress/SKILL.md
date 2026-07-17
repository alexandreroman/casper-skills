---
name: casper-progress
description: Track a non-immediate, multi-step activity with the task tools so a Casper workspace's sidebar progress bar reflects it. Use whenever you are about to start work that breaks into several distinct steps and is not over in a single action.
allowed-tools: TaskCreate, TaskUpdate
---

# Casper progress (sidebar progress bar)

This plugin already mirrors Claude's task list into a Casper workspace's
sidebar progress bar: a `PostToolUse` hook watches `TaskCreate` / `TaskUpdate`
and drives `casper progress set` / `casper progress clear` for you. So the
sidebar only advances when you actually use the task tools — nothing else
triggers it.

The judgment call this skill covers is deciding **when** work deserves that
tracking, and using the task tools consistently so the bar stays honest.

## When to track

Track progress whenever the work in front of you:

- breaks into several distinct steps, **and**
- is not over in a single action (implementing a feature, a multi-file
  refactor, a migration, running through a checklist, executing a plan).

Do **not** track a single, immediate action (answering a question, one edit,
one command) — a one-step progress bar is just noise.

## How to track

1. Create every step up front with `TaskCreate`, so the total is known and the
   bar shows real proportions from the start.
2. As you work, use `TaskUpdate` to set a step to `in_progress` when you begin
   it and `completed` when it is truly done. Keep exactly one step
   `in_progress` at a time — the sidebar shows that step's label as the current
   activity.
3. When every step is `completed`, the hook clears the bar automatically.

Never call `casper progress` yourself — let the hook derive it from the task
tools. Calling it by hand would fight the hook's per-session state and desync
the bar.

## Guard rule

The sidebar benefit only exists inside a Casper terminal workspace. The plugin
sets the `CASPER_WORKSPACE_ID` environment variable in each Casper terminal it
opens — check for its presence with the same plain test the plugin's own hooks
use, not by echoing the variable:

```bash
[ -n "$CASPER_WORKSPACE_ID" ]
```

Outside a Casper workspace the task tools still help you organize your work;
there is just no sidebar to update.
