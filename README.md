# Casper integration for coding agents

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Wires Claude Code's, Codex's, and opencode's own hook/plugin lifecycle to the
[`casper`](https://github.com/alexandreroman/casper) CLI, so a Casper
workspace's sidebar state, progress bar, info panel, and notifications update
automatically while the agent works — no changes to Casper itself required,
and no changes to the agent's own configuration or the user's project either.

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

> [!IMPORTANT]
> Codex hashes every non-managed command hook. After installing, open the
> Codex TUI and run `/hooks` to review and trust this plugin's hooks — until
> they are trusted, the integration is installed but **completely inert**: no
> sidebar updates, no progress bar, no notifications. This is the single most
> likely reason the integration will look broken on Codex, so do not skip it.
> Trust is recorded against each hook's current hash, so an upgrade that
> changes a hook sends it back for review — check `/hooks` again after every
> update, not only the first install.

### opencode

opencode installs a plugin straight from a Git repository, so this one is
distributed exactly like the other two — no npm registry in the picture:

```
opencode plugin github:alexandreroman/casper-skills -g
```

That is opencode's own installer: it fetches the repository and writes the
config entry itself (drop `-g` to install into the project's config instead).
By hand, the same thing is:

```json
{
  "plugin": ["github:alexandreroman/casper-skills"]
}
```

Any Git spec works in that slot — `github:owner/repo`, `git+https://…`,
`git+ssh://…` for a private clone, or a local path — and it tracks the branch
head, so a new commit is picked up the next time opencode starts. The skill
arrives with the plugin; there is nothing to install alongside it.

## What it does

Once it is installed there is nothing to run by hand. The agent's own
lifecycle drives the workspace:

| What the workspace shows | When |
|---|---|
| sidebar **working** | the turn starts, and again on every tool call — and it holds when a turn ends with the progress bar still up, which is what work left running in the background looks like |
| sidebar **done** | the turn ends with no bar up, or the session ends |
| sidebar **blocked**, plus a notification | the agent needs a decision, a credential, a login or an approval from you — a state it reported itself is never written over by the end of the turn |
| progress bar | the agent's own task, plan or todo list, mirrored step by step and cleared when the work is over — an agent whose harness has no such list drives the bar itself, and that bar stands until it clears it |
| bar cleared | the session ends, whatever set the bar |
| state, bar and info panel reset | a new session starts — a resume or a compact keeps the bar and the info panel, since that work is still the same |
| sidebar **error** | opencode only; neither Claude Code nor Codex reports a state that means this |

Apart from that last row the three agents behave identically.

Outside a Casper terminal the integration does nothing at all, and it never
blocks or fails a turn even when Casper isn't running.

## What the agent can do with it

The rest is judgment no hook can infer, so it ships as a skill — `casper` —
that every session in a Casper workspace is pointed at, and that the agent
loads when a request calls for it:

- tell you it is **blocked** and notify you, instead of ending a turn quietly
  waiting on an answer
- keep the **progress bar** honest on multi-step work
- publish a plan, findings, or a summary in the **info panel**
- open a URL in the **browser panel**, screenshot it, click or type on the
  page, read its console
- open or close the **diff view**, in full or for one file
- open, list, or close extra **terminals**
- list, create, delete, or close/merge **workspaces** and their Git worktrees
- **hand this session off** to a fresh workspace, so another agent instance
  picks the work up with nothing lost
- write a repository's **`.casper.json`**

Each surface has its own reference that the agent reads only when that surface
is in play, so a session loads what it needs and no more.

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

opencode picks up a plugin file dropped into `~/.config/opencode/plugin/` or a
project's `.opencode/plugin/`; a symlink to the checkout is enough, and it
brings its skill with it.

## Running the tests

```bash
for t in tests/test_*.sh tests/lib/test_*.sh; do bash "$t"; done
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m unittest discover -s tests/lib -p 'test_*.py' -v
node --test 'tests/opencode/*.test.js'
```

Use the quoted glob form for the opencode tests, not a bare directory —
`node --test tests/opencode` reports a phantom failure on Node 24.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
