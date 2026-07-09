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

`--command`'s value is **typed as literal keystrokes into the new
terminal's real interactive login shell** (zsh), followed by Enter — it is
not tokenized or exec'd by Casper itself. Because it's the user's actual
login shell, it already re-sources `~/.zshrc` and rebuilds `PATH` on its
own, exactly like a normal (commandless) Casper terminal. That means a
bare `claude` just works — no `$CLAUDE_CODE_EXECPATH`, no `$PATH`
re-export, no `/bin/sh -c` wrapping:

```bash
casper terminal new --command claude
```

To have that instance start on a specific task right away (e.g. "run a
code review here") instead of opening an empty Claude prompt, pass the
task as `claude`'s prompt argument. Quote it normally, the way you'd type
it at a shell prompt — no `printf '%q'` gymnastics needed, since the whole
`--command` value is a single already-expanded CLI argument that gets
retyped verbatim into the target shell, which parses the quotes itself:

```bash
casper terminal new --command 'claude "Review the diff in this workspace for bugs."'
```

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
