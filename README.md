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
| turn end | `status set done`, plus `progress clear` unless the agent's task list still shows a step in flight — the bar must not outlive the turn that set it |
| session end | `status set done` |
| blocked | `status set blocked` + `notify --message "..."` |
| tasks changed | mirrors the agent's task/plan/todo list into `progress set`/`progress clear` |

One skill covers the judgment calls no hook can infer automatically — either
by reaching for the `casper` CLI directly or by nudging the agent into
behaviour the hooks then pick up. `skills/casper/SKILL.md` is a plain
`SKILL.md`, read natively by all three agents, and it is deliberately small:
the guard rule, the rule for telling the user when you need them, and a
routing table. The per-surface detail sits in reference files the agent loads
only when that surface is in play.

The session guidance injected at `SessionStart` is what gets that skill
loaded, and it is the only component that both runs in every session and knows
for a fact that the session is in a Casper terminal. It names the skill **by
path**, resolved absolutely from whichever plugin-root variable the agent
exports: "read the casper skill" asks the agent to resolve something, and an
agent that does not bother is precisely the failure being designed against.
A path is one file read with nothing to resolve. Description matching is the second
line, not the first — which is why the skill's `description` is written in the
vocabulary of a request ("close, merge, create, delete a workspace or its Git
worktree", "screenshot", "diff view") rather than of this plugin, and why
`tests/test_casper_skill_entry.sh` pins that vocabulary against the routing
table so a new surface cannot be added unfindable.

### Where the plugin knows it lives

Resolving that path needs the plugin's own installation directory, and each
agent answers that question differently:

| Agent | How the plugin root is found |
|---|---|
| Claude Code | `CLAUDE_PLUGIN_ROOT`, exported into the environment of every hook command the plugin declares |
| Codex | `PLUGIN_ROOT` — its own name for the same thing, alongside `PLUGIN_DATA` for writable state. `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` are exported too, as compatibility mirrors |
| opencode | nothing: no plugin-root variable exists. The plugin's `context` carries `directory` and `worktree`, which describe the *project*, not the plugin |

So `hooks/hooks.json` names `${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}` rather than
either variable alone. Both agents expand a command hook through a shell, so
the fallback costs one `:-` and buys independence from a compatibility mirror
that is somebody else's to keep — Codex's native name is the one that cannot
be deprecated out from under this plugin. `hooks/session-start.py` reads the
pair in the same order for the same reason.

opencode never enters into that: nothing there is spawned as a command, so
`.opencode/plugin/casper.js` resolves the guidance file it ships against its
own module URL (`import.meta.url`), not against `process.cwd()` and not
against a path it was told. That is the only reliable answer on an agent that
loads plugins from `~/.config/opencode/plugin/`, a project directory, or an
npm cache, and it is why that file's guidance is a sibling of the plugin
rather than something written into the user's config.

| Reference | Covers |
|---|---|
| `references/status.md` | `casper status set blocked` / `error` for agent states no hook can detect. |
| `references/progress.md` | Tracking a multi-step, non-immediate activity with the agent's own task-tracking tool, so the progress hook keeps the sidebar bar in sync — and driving `casper progress` by hand on a harness that exposes no such tool. |
| `references/info.md` | Publishing, replacing, or clearing the workspace's info panel: one Markdown message per workspace, for a plan, a summary, findings, or the handles of something left running. In-memory only — it displays information, it never stores it. |
| `references/browser.md` | Opening a URL in Casper's browser panel, driving the page (screenshot, console, DOM, clicks, waits), and closing the panel. |
| `references/diff.md` | Opening Casper's diff view, in full or for one file, and closing it. |
| `references/terminal.md` | Opening, listing, and closing terminals in the workspace, on explicit request and on the agent's own judgment when a command should run somewhere visible or interactive. |
| `references/workspace.md` | Listing workspaces or resolving the current one anytime; creating, deleting, or closing/merging one (Git worktree) only on explicit request. |
| `references/handoff.md` | Handing the current in-progress session to a fresh workspace so a new agent instance continues this session's work with no loss of information (WIP commit + a self-contained handoff document). |
| `references/repo-config.md` | Generating or updating a repo's `.casper.json` (the files copied into new workspaces and the named `workspace.scripts`, including the reserved setup/teardown hooks); authoring works in any Git repo. |

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
/plugin marketplace add alexandreroman/casper-skills
/plugin install casper@casper
```

### Codex

```
codex plugin marketplace add alexandreroman/casper-skills
codex plugin add casper@casper
```

The `@casper` suffix is the marketplace, not decoration: `codex plugin add`
refuses a bare plugin name and wants either `PLUGIN@MARKETPLACE` or
`--marketplace`. Both names come out `casper` here — the plugin's, and the one
`.claude-plugin/marketplace.json` declares.

> [!IMPORTANT]
> Codex hashes every non-managed command hook. After installing, open the
> Codex TUI and run `/hooks` to review and trust this plugin's hooks — until
> they are trusted, the integration is installed but **completely inert**: no
> sidebar updates, no progress bar, no notifications. This is the single most
> likely reason the integration will look broken on Codex, so do not skip it.
> Trust is recorded against each hook's current hash, so an upgrade that
> changes `hooks/hooks.json` sends them back for review — check `/hooks` again
> after every update, not only the first install.

Three more Codex specifics this repository relies on rather than works
around, all verified against `codex-cli 0.149.0`:

- **The manifest.** Codex's own manifest path is `.codex-plugin/plugin.json`,
  and it falls back to `.claude-plugin/plugin.json` (then
  `.cursor-plugin/plugin.json`). This repository ships only the Claude Code
  one and Codex installs from it, so there is no second manifest to keep in
  sync. `.claude-plugin/marketplace.json` is likewise a marketplace location
  Codex reads.
- **Component discovery.** `hooks/hooks.json` and `skills/` are found by
  default discovery; the manifest's `hooks` and `skills` fields only
  *supplement* it. Nothing Codex-shaped has to be declared for the hooks to
  load — and the skill arrives namespaced as `casper:casper`.
- **The `SessionEnd` budget.** Codex defaults that event to a 1-second timeout
  and refuses more than 3, so the uniform `"timeout": 3` declared here is
  already its ceiling — worth knowing before editing `hooks/hooks.json`.

### opencode

Add `casper-skills` to the `plugin` array in `~/.config/opencode/opencode.json`:

```json
{
  "plugin": ["casper-skills"]
}
```

opencode also auto-loads plugins dropped into `~/.config/opencode/plugin/`
or a project's `plugins/` directory, if a local checkout is preferred over
the packaged name.

## Local development / testing

No marketplace or install step is needed for local development. For Claude
Code:

```bash
claude --plugin-dir /path/to/casper-skills
```

loads this plugin for that session only. Run it from inside a Casper
workspace terminal to see the hooks fire for real.

Codex has no such flag. Point a marketplace at the checkout instead, and
reinstall after each edit — the install snapshots the source into
`$CODEX_HOME/plugins/cache/`, so a running session never sees a change and a
new session only sees the last install:

```bash
codex plugin marketplace add /path/to/casper-skills
codex plugin add casper@casper   # again after every edit; it does refresh
                                 # the cache at an unchanged version
```

`codex exec --dangerously-bypass-hook-trust` skips the `/hooks` trust prompt
for one non-interactive run, which is what makes this loop bearable.

opencode picks up a checkout dropped into `~/.config/opencode/plugin/` or
`plugins/`.

## Running the tests

```bash
for t in tests/test_*.sh tests/lib/test_*.sh; do bash "$t"; done
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m unittest discover -s tests/lib -p 'test_*.py' -v
node --test 'tests/opencode/*.test.js'
```

Use the quoted glob form for the opencode tests, not a bare directory —
`node --test tests/opencode` reports a phantom failure on Node 24.

`tests/test_cli_surface.py` is the one test that talks to the real `casper`
CLI, because the failure it exists for cannot be caught any other way: a
reference that understates the CLI reads as a complete description, so an
agent believes the part that is missing does not exist. It pins what
`references/workspace.md` claims — its synopses, the subcommands it documents,
the ones it says do not exist — against `casper help`. It skips itself when
`casper` is not on `PATH`, so run the suite from inside a Casper terminal to
get its coverage.

## Porting to a new agent

Fit the new agent into the shape above rather than inventing a new one.
`hooks/lib/casper.py::EVENT_ACTIONS` is the single source of truth for the
events whose mapping is a fixed constant; the payload-dependent ones
(session start, blocked, tasks changed) are computed by each entry point, and
`tests/test_cross_agent_conformance.sh` is what keeps every agent's argv
identical. A new agent's integration is not done until a test pins its
mapping by reading those tables at test time rather than copying them.

Two rules beyond that: the integration never writes into the user's config or
project — installation is always the target agent's own installer — and a
capability the new agent lacks is recorded as "not supported" in the matrix
above, never approximated with a heuristic that will misfire.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
