# Casper progress (sidebar progress bar)

The bar answers exactly one question: which step is this workspace on **right
now**. A bar left standing over work that has stopped is worse than no bar at
all — it makes the sidebar lie — so everything below is in service of keeping
it honest.

## When to track

Track progress whenever the work in front of you:

- breaks into several distinct steps, **and**
- is not over in a single action (implementing a feature, a multi-file
  refactor, a migration, running through a checklist, executing a plan).

Do **not** track a single, immediate action (answering a question, one edit,
one command) — a one-step progress bar is just noise.

## How to track: with a task tool

Most harnesses give you one — Claude Code's task tools, Codex's plan tool,
opencode's todo list. This plugin watches whichever applies and mirrors it
into the bar, so the bar advances as a side effect of using the tool and you
never call `casper progress` yourself. Calling it by hand on this path would
fight the hook's per-session state and desync the bar.

1. Create every step up front, so the total is known and the bar shows real
   proportions from the start.
2. As you work, mark a step in progress when you begin it and completed when
   it is truly done. Keep exactly one step in progress at a time — the sidebar
   shows that step's label as the current activity.

## How to track: with no task tool

Some harnesses expose no todo, plan, or task tool at all. Check your own tool
list rather than assuming; when there is none, no hook can derive the bar, and
driving it yourself is the only option:

```bash
casper progress set --total 6 --current 5 --label "Splitting AppModel.swift"
casper progress clear
```

`--current` is the 1-based index of the step running now, `--total` the number
of steps, `--label` what that step is doing.

Two rules make hand-driving safe:

- **Clear it as soon as the work is done**, in the same turn. Nothing else
  knows your work finished.
- **Re-set it each turn** if the work spans several. A hand-driven bar does
  not survive the end of a turn (below), and re-setting it is one command.

## When the bar clears

- **Every step completed**, on the task-tool path — the hook clears it the
  moment the last step is marked done.
- **The end of every turn**, unless your task tool still shows a step in
  flight. Between turns the agent is not running, so a bar describing a step
  "in progress" would be false; the `Stop` hook consults the same task state
  the progress hook maintains and drops the bar when nothing is live. A task
  genuinely still in flight keeps its bar, so a turn that ends waiting on the
  user still shows where the work stopped. With no task state to consult — the
  hand-driven case — there is nothing to distinguish live work from stale, so
  the bar goes.
- **Session start**, along with the rest of the workspace surfaces.

## Outside a Casper workspace

The sidebar benefit only exists inside a Casper terminal workspace, but the
task-tracking tool still helps you organize your work there — there is just
no bar to update. Nothing to skip, nothing to guard.
