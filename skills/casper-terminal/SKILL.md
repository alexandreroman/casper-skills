---
name: casper-terminal
description: Open, list, and close terminals in a Casper workspace — always when the user explicitly asks to run or launch something in a terminal, and also on your own judgment when a command should run somewhere the user can see or interact with it (a dev server, a watch/tail command). Only useful inside a Casper terminal workspace.
allowed-tools: Bash([ -n "$CASPER_WORKSPACE_ID" ]) Bash(casper terminal new) Bash(casper terminal new *) Bash(casper terminal list) Bash(casper terminal list *) Bash(casper terminal close *)
---

# Casper terminal

Casper workspaces can hold more than one terminal. Use the `casper
terminal` CLI to open, list, and close extra terminals.

## When to open a new terminal

- **Explicit request — always.** If the user asks to run or launch
  something in a terminal ("lance ça dans un terminal", "run this in a
  terminal", "launch this in a new terminal/window"), open one with
  `casper terminal new`. The request itself is sufficient — don't further
  judge whether the command is long-running, interactive, or worth
  watching; that judgment call only applies to the case below.
- **Your own judgment — beyond explicit requests.** Unlike
  `casper-browser`/`casper-diff`, this skill isn't limited to explicit
  requests. Open a terminal on your own initiative too, whenever the user
  would benefit from seeing or interacting with a running process
  themselves in the Casper UI: a dev server they'll open in a browser, a
  `watch`/tail command, an interactive process — anything long-running
  that's naturally visible or interactive. The trigger here is
  **visibility**, not avoiding a blocking call — do **not** open one as a
  silent substitute for the Bash tool's own background execution
  (`run_in_background: true`). A long build or test run the user has no
  reason to watch directly stays a normal (optionally backgrounded) Bash
  call.

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
casper terminal new --command \
  "/bin/sh -c $(printf '%q' "PATH=$(printf '%q' "$PATH") exec $(printf '%q' "$CLAUDE_CODE_EXECPATH")")"
```

Note `$CLAUDE_CODE_EXECPATH` points at the exact running version (e.g.
`~/.local/share/claude/versions/2.1.203`), not a stable "latest" symlink —
that's fine here since the point is to launch the same version as the
current instance.

To have that instance start on a specific task right away (e.g. "run a
code review here") instead of opening an empty Claude prompt, add the task
as one more nested `printf '%q'` argument — `claude [prompt]` accepts one
and starts the interactive session with it as the first message:

```bash
casper terminal new --command \
  "/bin/sh -c $(printf '%q' "PATH=$(printf '%q' "$PATH") exec $(printf '%q' "$CLAUDE_CODE_EXECPATH") $(printf '%q' "Review the diff in this workspace for bugs.")")"
```

Keep it as one nested expression (no intermediate `inner=...`/`outer=...`
variables in separate statements) so the actual tool invocation still
starts with `casper terminal new` and matches this skill's pre-authorized
`allowed-tools` prefix.

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
