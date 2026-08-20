# Casper integration for coding agents

Wires Claude Code's, Codex's, and opencode's own hook/plugin lifecycle to the
[`casper`](https://github.com/alexandreroman/casper) CLI, so a Casper
workspace's sidebar state, progress bar, info panel, and notifications update
automatically while the agent works — no changes to Casper itself required,
and no changes to the agent's own configuration or the user's project either.

## What it does

Every Casper surface Claude Code and Codex expose is available on opencode
too: the three agents expose the same lifecycle through different
mechanisms, and this plugin normalizes the difference away. opencode also
reports an `error` state neither Claude Code nor Codex has a counterpart
for, so that row is asymmetric the other way — see below.

| Casper surface | Claude Code | Codex | opencode |
|---|---|---|---|
| session start | `SessionStart` | `SessionStart` | `session.created` (root session only) |
| turn start | `UserPromptSubmit` | `UserPromptSubmit` | `session.status` → `busy` |
| tool activity | `PreToolUse` | `PreToolUse` | `tool.execute.before` |
| turn end | `Stop` | `Stop` | `session.status` → `idle`, `session.idle` |
| session end | `SessionEnd` | `SessionEnd` | `session.deleted` |
| blocked / notifications | `Notification` (type allowlist) | `PermissionRequest` | `permission.asked` |
| progress bar | `PostToolUse` on `TaskCreate`\|`TaskUpdate` | `PostToolUse` on `update_plan` | `todo.updated` |
| info panel & guidance injection | `SessionStart` stdout | `SessionStart` stdout | in-process `config` hook → `instructions[]` |
| error state | not supported | not supported | `session.error` → `status set error` |

Each row lands on the same normalized action regardless of which agent fired
it:

| Normalized event | Casper action |
|---|---|
| session start | `status set idle` + `progress clear`, plus `info clear` for a genuinely new session (skipped on resume/compact, which continue an existing one) |
| turn start | `status set working` |
| tool activity | `status set working` (holds the explicit-authority latch for the whole turn, so turn end can safely report `done`) |
| turn end | `status set done` |
| session end | `status set done` |
| blocked | `status set blocked` + `notify --message "..."` |
| tasks changed | mirrors the agent's task/plan/todo list into `progress set`/`progress clear` |

Fallback skills cover the judgment calls no hook can infer automatically —
either by reaching for the `casper` CLI directly or by nudging the agent into
behaviour the hooks then pick up. They are plain `SKILL.md` files, read
natively by all three agents:

- `casper-status` — call `casper status set blocked` / `casper status set
  error` for agent states no hook can detect.
- `casper-progress` — track a multi-step, non-immediate activity with the
  agent's own task-tracking tool so the progress hook keeps the sidebar
  progress bar in sync.
- `casper-browser` — open a URL in Casper's browser panel when the user
  asks to see something in a browser, or close the panel when asked.
- `casper-diff` — open Casper's diff view when the user asks to see a diff,
  in full or for one file, or close it when asked.
- `casper-info` — publish, replace, or clear the workspace's info panel: one
  Markdown message per workspace, for a plan, a summary, findings, or the
  handles of something left running. In-memory only — it displays
  information, it never stores it.
- `casper-terminal` — open, list, and close terminals in the workspace,
  always when the user explicitly asks to run something in a terminal, and
  also on the agent's own judgment when a command should run somewhere
  visible or interactive rather than in the background.
- `casper-workspace` — list workspaces or resolve the current one anytime;
  create or delete a workspace (Git worktree) only on explicit request.
- `casper-handoff` — hand off the current in-progress session to a fresh
  workspace so a new agent instance continues this session's work with no
  loss of information (WIP commit + a self-contained handoff document).
- `casper-config` — generate or update a repo's `.casper.json` (the files
  copied into new workspaces and the named `workspace.scripts`, including the
  reserved setup/teardown hooks); authoring works in any Git repo.

Every hook and the opencode plugin are a no-op outside a Casper terminal —
they check for `$CASPER_WORKSPACE_ID` before doing anything, and never block
or fail a turn even if Casper isn't running.

## Requirements

- [Casper](https://github.com/alexandreroman/casper) — the `casper` CLI is
  only reachable inside a terminal Casper opened.
- `python3` (ships with Xcode Command Line Tools) — needed by the Claude Code
  and Codex hooks.
- Node — needed by the opencode plugin; opencode itself ships with a Node
  runtime, so nothing extra to install there.

## Installation

Each agent installs the integration through its own installer. None of them
writes into another agent's configuration or into a user's project.

### Claude Code

This repository self-hosts a plugin marketplace:

```
/plugin marketplace add alexandreroman/casper-agents
/plugin install casper@casper-agents
```

### Codex

```
codex plugin marketplace add alexandreroman/casper-agents
codex plugin add casper
```

> [!IMPORTANT]
> Codex hashes every non-managed command hook. After installing, open the
> Codex TUI and run `/hooks` to review and trust this plugin's hooks — until
> they are trusted, the integration is installed but **completely inert**: no
> sidebar updates, no progress bar, no notifications. This is the single most
> likely reason the integration will look broken on Codex, so do not skip it.

### opencode

Add `casper-agents` to the `plugin` array in `~/.config/opencode/opencode.json`:

```json
{
  "plugin": ["casper-agents"]
}
```

opencode also auto-loads plugins dropped into `~/.config/opencode/plugin/`
or a project's `plugins/` directory, if a local checkout is preferred over
the packaged name.

## Local development / testing

No marketplace or install step is needed for local development. For Claude
Code:

```bash
claude --plugin-dir /path/to/casper-agents
```

loads this plugin for that session only. Run it from inside a Casper
workspace terminal to see the hooks fire for real. Codex accepts an
equivalent local flag; opencode picks up a checkout dropped into
`~/.config/opencode/plugin/` or `plugins/`.

## Running the tests

```bash
for t in tests/test_*.sh tests/lib/test_*.sh; do bash "$t"; done
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m unittest discover -s tests/lib -p 'test_*.py' -v
node --test 'tests/opencode/*.test.js'
```

Use the quoted glob form for the opencode tests, not a bare directory —
`node --test tests/opencode` reports a phantom failure on Node 24.

## Porting to a new agent

See [`docs/porting-to-a-new-agent.md`](docs/porting-to-a-new-agent.md) for the
integration shapes, the normalized event vocabulary, and the conformance
rules a new agent must satisfy.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
