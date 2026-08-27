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

## First, find out which path you are on

There are two ways to drive the bar and they are mutually exclusive. Which one
applies is decided by a single fact: whether your own tool list contains a
task-tracking tool. Look — do not assume, and do not guess from the harness's
name:

| Harness | The tool | Path |
|---|---|---|
| Claude Code | its task tools | task tool |
| Codex | its plan tool | task tool |
| opencode | its todo list tool (write + read) | task tool |
| anything with no such tool | — | by hand |

On the task-tool path you **never run `casper progress` yourself**. The
integration watches that tool and mirrors it into the bar for you, keeping its
own per-session state; a hand-written `casper progress set` on top of that
overwrites what the mirror just wrote, and the next tool update overwrites you
straight back. The two fight, and the bar ends up describing neither. The CLI
below is for the *other* path only.

## How to track: with a task tool

The bar advances as a side effect of using the tool, so all you do is use it
well:

1. Create every step up front, so the total is known and the bar shows real
   proportions from the start.
2. Mark a step in progress when you begin it and completed when it is truly
   done. Keep **exactly one** step in progress at a time — the bar takes its
   label from that step, so with none in progress the previous label stands
   until the next update, and with two the first one wins arbitrarily.
3. Do not batch the updates. A list updated only at the end of the work is a
   bar that was wrong for the whole of it.

A step you decide not to do is marked cancelled, not left pending: cancelled
counts as finished, so the bar advances past it and clears once the last live
step is gone. Leaving it pending strands the bar on work that will never run.

Every step of this helps you outside a Casper workspace too — there is simply
no bar there. Nothing to guard, nothing to skip.

## How to track: with no task tool

Only when the table above put you on this path. No mirror can derive the bar,
so driving it yourself is the only option:

```bash
casper progress set --total 6 --current 5 --label "Splitting AppModel.swift"
casper progress clear
```

`--current` is the 1-based index of the step running now, `--total` the number
of steps, `--label` what that step is doing.

Two rules make hand-driving safe:

- **Clear it as soon as the work is done**, in the turn that finishes it.
  Nothing else knows your work finished. A hand-driven bar stands until you
  clear it or the session ends — it outlives a turn boundary on purpose
  (below) — so this one rule is the whole of what keeps it honest.
- **Move it as each step begins**, with the same command and a new
  `--current` and `--label`. Set once and never touched, it describes step
  one for the whole of the work.

## When the bar clears

- **Every step finished**, on the task-tool path — completed or cancelled, the
  mirror clears the bar the moment the last live step is gone.
- **The end of a turn whose task tool shows no step in flight.** The turn-end
  hook consults the same task state the mirror maintains and drops the bar
  when nothing in it is live. A step genuinely still in flight keeps its bar,
  so a turn that ends waiting on the user still shows where the work stopped.
  A hand-driven bar has no task state behind it, so the hook leaves it exactly
  as it is — it survives the turn boundary for the same reason an in-flight
  step does. Work outlives turns routinely: subagents dispatched to run in the
  background, a turn ended to put a question to the user. The sidebar is not
  lying about activity in the meantime, because the agent-state icon reports
  done or idle independently of the bar.
- **Session end**, whatever set the bar. The backstop for the hand-driven one
  the agent never got around to clearing.
- **Session start**, along with the rest of the workspace surfaces — though a
  resume or a compact keeps the bar, since that work is still the same.
