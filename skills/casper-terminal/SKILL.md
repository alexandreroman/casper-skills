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

### Launching a new agent instance with `--command`

To launch a coding agent in the new terminal, default to a fresh instance
of **your own agent CLI** — the same one you're running as. The examples
below use `claude` as a concrete stand-in; substitute whatever CLI
actually applies (`claude`, `codex`, `gemini`, `aider`, …), and if the
user names a specific agent, use that one.

`--command`'s value is **typed as literal keystrokes into the new
terminal's real interactive login shell** (whatever `$SHELL` resolves to
for the user — zsh, bash, etc.), followed by Enter — it is not tokenized
or exec'd by Casper itself. Because it's the user's actual login shell, it
already re-sources that shell's own profile (`~/.zshrc`, `~/.bash_profile`,
...) and rebuilds `PATH` on its own, exactly like a normal (commandless)
Casper terminal. That means a bare invocation of the agent CLI just
works — no need to re-export `$PATH` and no `/bin/sh -c` wrapping:

```bash
casper terminal new --command <agent-cli>   # e.g. claude, codex, gemini
```

To have that instance start on a specific task right away (e.g. "run a
code review here") instead of opening an empty agent prompt, give it an
initial prompt. **Write the prompt/context to a temporary file and have
the agent read it in — do not pass it inline on the command line.** The
`--command` value is retyped verbatim as literal keystrokes into the
target shell, so any non-trivial context (multi-line, quotes, backticks,
`$`, long text) is fragile that way; a temp file sidesteps all of it and
keeps the launch command short.

Put the file **outside any repository** — use `mktemp` under the system
temp dir — so it can never be staged or committed. Never place it inside
the workspace/worktree, and never commit it. Prefer **Markdown** for the
file (give it a `.md` extension) so the context stays well-structured and
readable. Write the full context to the file, then give the agent a **very
short** inline prompt that just tells it to read that file — do **not**
`cat` the file into the prompt:

```bash
# mktemp only substitutes trailing Xs (BSD/macOS), so add the .md after.
prompt_file="$(mktemp /tmp/casper-agent-prompt.XXXXXX)" && mv "$prompt_file" "$prompt_file.md" && prompt_file="$prompt_file.md"
cat > "$prompt_file" <<'EOF'
Review the diff in this workspace for bugs.
<...the full, self-contained context goes here...>
EOF
casper terminal new --command "<agent-cli> \"Read the instructions in $prompt_file and follow them.\""   # e.g. claude "Read the instructions in /tmp/… and follow them."
```

The `$prompt_file` path is expanded in your shell, so the launched agent
receives a short instruction naming the file and reads the real context in
itself. The file must still exist when that instance starts; it lives in
the temp dir, stays out of version control, and the OS reclaims it later.

## Listing and closing

If the id was lost (e.g. after a context compaction), recover it with:

```bash
casper terminal list
```

which prints a JSON array, one entry per open terminal:

```json
[{"terminal":"3F2A1C4E-...","working-dir":"..."}]
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
