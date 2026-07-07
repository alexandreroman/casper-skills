---
name: casper-terminal
description: Open, list, and close terminals in a Casper workspace — including opening one on your own judgment when a command should run somewhere the user can see or interact with it (a dev server, a watch/tail command), not just on explicit request. Only useful inside a Casper terminal workspace.
allowed-tools: Bash([ -n "$CASPER_WORKSPACE_ID" ]) Bash(casper terminal new) Bash(casper terminal new *) Bash(casper terminal list) Bash(casper terminal list *) Bash(casper terminal close *)
---

# Casper terminal

Casper workspaces can hold more than one terminal. Use the `casper
terminal` CLI to open, list, and close extra terminals.

## When to open a new terminal

Unlike `casper-browser`/`casper-diff`, this is not limited to explicit user
requests — act on your own judgment. The trigger is **visibility**, not
avoiding a blocking call:

- Open one when the user would benefit from seeing or interacting with a
  running process themselves in the Casper UI: a dev server they'll open
  in a browser, a `watch`/tail command, an interactive process — anything
  long-running that's naturally visible or interactive.
- Do **not** open one as a silent substitute for the Bash tool's own
  background execution (`run_in_background: true`). A long build or test
  run the user has no reason to watch directly stays a normal (optionally
  backgrounded) Bash call.

```bash
casper terminal new --command "npm run dev"
```

prints one line of JSON to stdout:

```json
{"terminal":"3F2A1C4E-...","workspace":"...","command":"npm run dev"}
```

Remember the `terminal` id for the rest of the conversation — you'll need
it to close the terminal later with `casper terminal close <id>` once the
process is no longer needed. `--command` is optional (omit it for an empty
shell); `--working-dir <path>` overrides the default (the workspace's
worktree).

### Launching a new Claude instance with `--command`

Don't pass a bare `claude` — the terminal Casper opens is a non-interactive,
non-login shell that never sources `~/.zshrc`, so it won't have whatever
`PATH` entry makes `claude` resolve interactively (this fails with `exec:
claude: not found`). Use the current instance's own executable path
instead, exposed via `$CLAUDE_CODE_EXECPATH`:

```bash
casper terminal new --command "$CLAUDE_CODE_EXECPATH"
```

This is a fully-qualified path, so it needs no `PATH` lookup at all. Note it
points at the exact running version (e.g.
`~/.local/share/claude/versions/2.1.203`), not a stable "latest" symlink —
that's fine here since the point is to launch the same version as the
current instance.

## Listing and closing

If the id was lost (e.g. after a context compaction), recover it with:

```bash
casper terminal list
```

which prints a JSON array, one entry per open terminal:

```json
[{"id":"3F2A1C4E-...","working-dir":"...","command":"npm run dev"}]
```

Close a terminal you opened once it's no longer needed:

```bash
casper terminal close <id>
```

## Targeting another workspace

All three subcommands accept `--workspace <id-or-name>` to target a
workspace other than the current one — default is `$CASPER_WORKSPACE_ID`.

This only works inside a terminal Casper opened — if the command fails or
`casper` isn't found, fall back to a normal Bash call and continue; never
let it interrupt your actual task.

## Guard rule

Only invoke this skill inside a Casper terminal workspace. The plugin sets
the `CASPER_WORKSPACE_ID` environment variable in each Casper terminal it
opens — check for its presence with the same plain test the plugin's own
hooks use, not by echoing the variable:

```bash
[ -n "$CASPER_WORKSPACE_ID" ]
```

Then call the CLI as its own command.
