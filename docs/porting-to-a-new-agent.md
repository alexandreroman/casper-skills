# Porting this integration to a new agent

This plugin bridges three coding agents — Claude Code, Codex, and opencode —
to the same [`casper`](https://github.com/alexandreroman/casper) CLI surface.
Adding a fourth agent means fitting it into the same shape, not inventing a
new one.

## The two integration shapes

**Shell-hook agents** (Claude Code, Codex today) invoke an external process
per lifecycle event, with the event payload on stdin or in environment
variables, and get nothing back except an exit code and optional stdout. The
entry points live in `hooks/*.sh` and `hooks/*.py`, declared in
`hooks/hooks.json`. Where two shell-hook agents differ only in the shape of
their payload or the name of a field (task tool name, notification type),
the same script branches on it — see `hooks/blocked.py` and `hooks/tasks.py`
for the existing examples. Detect which agent is calling by environment
variable, not by guesswork (Codex sets `PLUGIN_ROOT` in addition to
`CLAUDE_PLUGIN_ROOT`; Claude Code sets only the latter).

**In-process plugin agents** (opencode today) load a module into the agent's
own runtime and subscribe to an event bus directly, with no process boundary
and no stdin contract. `.opencode/plugin/casper.js` is the existing example:
it subscribes to opencode's `event` hook (and lifecycle hooks like
`tool.execute.before`), normalizes what it sees, and calls the `casper` CLI
directly, the same way every shell hook does — there is no Python process
in between, and no stdin contract to look for. The policy mapping is
reimplemented in JavaScript (`progressActions` mirrors
`hooks/lib/progress.py::actions_for`; the fixed-mapping and payload-dependent
cases mirror `hooks/lib/casper.py::EVENT_ACTIONS` and the Python entry
points computing the other three events), and parity between the two
runtimes is what `tests/test_cross_agent_conformance.sh` enforces, by
driving both sides with the same input and comparing recorded argv — not by
sharing a process or a payload contract. A new in-process agent should
follow the same pattern: translate that agent's native events into the
normalized vocabulary below, call the `casper` CLI directly, and add a
conformance test that pins its own computed mapping against the existing
implementation's the same way.

## The normalized event vocabulary

Every entry point, regardless of shape, produces one of seven normalized
events, or nothing:

| Event | Casper action |
|---|---|
| `session-start` | `status set idle`, `progress clear`, `info clear` unless resumed/compacted |
| `turn-start` | `status set working` |
| `tool-activity` | `status set working` (holds the explicit-authority latch) |
| `turn-end` | `status set done` |
| `session-end` | `status set done` |
| `blocked` | `status set blocked`, `notify --message …` |
| `tasks-changed` | `progress set …` or `progress clear` |

**`hooks/lib/casper.py::EVENT_ACTIONS` is the single source of truth** for the
four events whose mapping is a fixed constant (`turn-start`, `tool-activity`,
`turn-end`, `session-end`). `tests/test_event_conformance.sh` and
`tests/test_cross_agent_conformance.sh` pin every agent's argv against this
table automatically, so those four cannot drift apart silently.

The other three — `session-start`, `blocked`, `tasks-changed` — depend on the
event's payload, so their mapping is computed independently by each entry
point (`hooks/session-start.py`, `hooks/blocked.py`,
`hooks/lib/progress.py::actions_for`, and the opencode plugin's own
counterparts), though every call those entry points make still routes
through `casper.py::run()` so the guards (workspace check, timeout, swallowed
errors) apply uniformly. These three are not read from a shared table, so
they are not automatically protected by it; `tests/test_cross_agent_conformance.sh`
covers them by driving each side with matching input and comparing the
recorded argv directly. A new agent's entry points must either read
`EVENT_ACTIONS` (or its computed counterparts) rather than re-deriving the
mapping, or add an equivalent conformance test pinning their own computed
mapping against the existing implementation's — a mapping neither read from
the table nor covered by such a test is the one place drift can happen
silently.

## Required: a conformance test

A new agent's integration is not done until a test proves it emits exactly
the `EVENT_ACTIONS` argv for every event it supports — not an equivalent
call, not a call with the same effect, the same argv. `tests/test_event_conformance.sh`
does this for the Bash hooks by shelling out to Python to read the table and
diffing it against a stub `casper`'s captured calls; `tests/test_cross_agent_conformance.sh`
does the same for the opencode plugin by importing `EVENT_ACTIONS` from
Python and the plugin's exported handlers from Node, in the same process run,
and comparing serialized JSON. Follow whichever pattern fits the new agent's
runtime, but the assertion must read the table at test time rather than
hard-coding a copy of it — a hard-coded copy is exactly the drift this rule
exists to prevent.

## Required: never write into the user's config or project

The integration's own installation is always performed by the target agent's
own installer (a marketplace add, a plugin registry entry, a config array
entry) — never by this repository's code. At runtime, every entry point may
read environment variables and call the `casper` CLI, and nothing else: no
writing to the agent's config file, no writing into the user's repository, no
mutation outside Casper's own workspace state. A new agent's entry point that
needs to leave a marker (a guidance string, a version constant for the
Casper-side installed-version probe) writes it only into files this
repository already ships, never into a path under the user's home directory
or project.

## Required: a missing capability is documented, never faked

Not every agent surfaces every Casper-relevant signal in a form this
integration can reach. When a new agent lacks a mechanism for one of the
normalized events or one of the capability-matrix rows (see the README's
matrix), do not approximate it with a heuristic that will misfire, and do not
silently drop the row. Add the row to the capability matrix and mark what the
new agent actually offers — including "not supported" as an explicit,
documented value — so the gap is visible to anyone comparing agents rather
than discovered by surprise.
