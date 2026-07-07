---
name: casper-workspace
description: List Casper workspaces, resolve the current one, or create/delete a workspace (Git worktree) — list/current are safe to use anytime, new/delete only on explicit user request. Only useful inside a Casper terminal workspace.
allowed-tools: Bash([ -n "$CASPER_WORKSPACE_ID" ]) Bash(casper workspace list) Bash(casper workspace current) Bash(casper workspace new *) Bash(casper workspace delete) Bash(casper workspace delete *)
---

# Casper workspace

Manage Casper workspaces (each one is a Git worktree) with the `casper
workspace` CLI.

## Read-only: use anytime

```bash
casper workspace list
```

prints a JSON array of every workspace:

```json
[{"id":"...","name":"...","branch":"...","path":"..."}]
```

```bash
casper workspace current
```

prints the current workspace (from `$CASPER_WORKSPACE_ID`):

```json
{"workspace":"...","path":"..."}
```

Use these to answer questions like "which workspaces are open", or to
resolve an id/name/path to pass as `--workspace` to this or other Casper
skills.

## Creating a workspace: explicit request only

```bash
casper workspace new --branch <name> [--base <ref>] [--command <cmd>]
```

creates a new Git worktree workspace on a new branch (a sibling of the
current workspace's Space), printing:

```json
{"workspace":"<new-id>","name":"...","branch":"...","path":"..."}
```

`--base` defaults to the Space's primary workspace's branch if omitted.
`--command` is optional — omit it for an empty initial terminal, or pass a
command to run immediately in the new workspace's terminal. **If omitted,
the new workspace's terminal stays an empty shell — nothing runs in it
automatically.**

### Default to launching a new Claude instance there

If the request implies work should actually happen in the new
workspace — "explore X in a new workspace", "fix this in a new worktree",
"spin up a workspace and look into Y" — creating the workspace alone does
**not** satisfy that; an empty terminal can't explore or fix anything.
Always add `--command` to start a new Claude instance there in the same
call, unless the user explicitly only wants the workspace/worktree itself
with nothing running in it.

`--command`'s value is **not** run through a real shell — Casper tokenizes
it on whitespace itself (backslash-escaping is honored to keep spaces
inside one token, e.g. from `printf '%q'`) and directly execs the first
token, with no `$PATH` search when it contains a `/` and no understanding
of shell syntax like `VAR=value cmd` prefixes. Two consequences:

- A bare `claude` fails with `exec: claude: not found`, because the new
  terminal's shell never sources `~/.zshrc` (non-interactive, non-login),
  so it starts with a minimal system `PATH` missing wherever `claude` is
  installed. Use `$CLAUDE_CODE_EXECPATH` — the current instance's own
  fully-qualified executable path — instead of a bare `claude`.
- Even with that fixed, the spawned Claude instance still only has that
  same minimal `PATH` in its own environment, so **its own** tool calls
  fail to find things like `gh` or `rtk` (hook/tool errors, "command not
  found") despite them working fine in your own session.

Fix both by wrapping the whole thing in an explicit `/bin/sh -c` that
re-exports the current session's full `$PATH` before exec'ing Claude —
build it with nested `printf '%q'` calls (one layer for what real
`/bin/sh` needs to parse, one more so Casper's own tokenizer keeps that as
a single opaque argument):

```bash
casper workspace new --branch <name> --command \
  "/bin/sh -c $(printf '%q' "PATH=$(printf '%q' "$PATH") exec $(printf '%q' "$CLAUDE_CODE_EXECPATH")")"
```

Note `$CLAUDE_CODE_EXECPATH` points at the exact running version (e.g.
`~/.local/share/claude/versions/2.1.203`), not a stable "latest" symlink —
that's fine here since the point is to launch the same version as the
current instance.

After creating it, use `casper terminal list --workspace <id>` to confirm
the terminal actually has a `"command"` field — if it's missing, no command
was launched and the workspace is just sitting there empty.

### Giving that instance a task to work on

To have the new instance start on a specific task right away (e.g. "run a
code review in a new workspace") rather than opening an empty Claude
prompt, add the task as one more nested `printf '%q'` argument —
`claude [prompt]` accepts one and starts the interactive session with it
as the first message:

```bash
casper workspace new --branch <name> --command \
  "/bin/sh -c $(printf '%q' "PATH=$(printf '%q' "$PATH") exec $(printf '%q' "$CLAUDE_CODE_EXECPATH") $(printf '%q' "Review the diff in this workspace for bugs.")")"
```

Keep it as one nested expression (no intermediate `inner=...`/`outer=...`
variables in separate statements) so the actual tool invocation still
starts with `casper workspace new` and matches this skill's
pre-authorized `allowed-tools` prefix.

Only run this when the user explicitly asks for a new workspace/worktree —
never on your own judgment. This mirrors the existing rule not to create a
Git branch without being asked: `workspace new` always creates one.

## Deleting a workspace: explicit request only, and irreversible

```bash
casper workspace delete [--workspace <id-or-name>]
```

deletes a workspace — its worktree folder, its Git branch, and its UI
entry — **immediately**. There is no confirmation prompt and no
`--force`/`-y` gate anywhere in the CLI; calling the command is the only
confirmation there is, and it cannot be undone.

Only run this when the user explicitly asks, and if there's any ambiguity
about *which* workspace, confirm the id or name with the user before
calling it — the CLI itself won't stop a mistaken call. (It refuses to
delete a Space's primary workspace on its own: `"cannot delete the primary
workspace"`.)

## Targeting another workspace

`new` and `delete` accept `--workspace <id-or-name>` to target a workspace
other than the current one — default is `$CASPER_WORKSPACE_ID`. `list` has
no target (it's global); `current` has no override (it's specifically
about `$CASPER_WORKSPACE_ID`).

This only works inside a terminal Casper opened — if the command fails or
`casper` isn't found, tell the user and continue; never let it interrupt
your actual task.

## Guard rule

Only invoke this skill inside a Casper terminal workspace. The plugin sets
the `CASPER_WORKSPACE_ID` environment variable in each Casper terminal it
opens — check for its presence with the same plain test the plugin's own
hooks use, not by echoing the variable:

```bash
[ -n "$CASPER_WORKSPACE_ID" ]
```

Then call the CLI as its own command.
