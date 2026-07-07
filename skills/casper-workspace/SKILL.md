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
command to run immediately in the new workspace's terminal.

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
