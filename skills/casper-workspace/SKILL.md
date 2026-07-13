---
name: casper-workspace
description: List Casper workspaces, resolve the current one, create a workspace (Git worktree) — including to offload or delegate a task to a dedicated coding-agent instance running isolated in its own worktree instead of the current session — delete one outright (discards its work, no merge), or close/merge one back into its origin branch first (rebase, merge commit, then delete). list/current are safe anytime; new/delete/close/merge only on explicit request, and both delete and close/merge are destructive and irreversible. Only useful inside a Casper terminal workspace.
allowed-tools: AskUserQuestion Bash([ -n "$CASPER_WORKSPACE_ID" ]) Bash(casper workspace list) Bash(casper workspace current) Bash(casper workspace new *) Bash(casper workspace delete) Bash(casper workspace delete *) Bash(git worktree list) Bash(git status --porcelain*)
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
[{"workspace":"...","name":"...","branch":"...","path":"..."}]
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
casper workspace new <name> [--base <ref>] [--command <cmd>]
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

### Default to launching a new agent instance there

If the request implies work should actually happen in the new
workspace — "explore X in a new workspace", "fix this in a new worktree",
"spin up a workspace and look into Y" — creating the workspace alone does
**not** satisfy that; an empty terminal can't explore or fix anything.
Always add `--command` to start a new coding-agent instance there in the
same call, unless the user explicitly only wants the workspace/worktree
itself with nothing running in it.

By default, launch a fresh instance of **your own agent CLI** — the same
one you're running as — so the new workspace continues in the same kind of
agent. The examples below use `claude` as a concrete stand-in; substitute
whatever CLI actually applies (`claude`, `codex`, `gemini`, `aider`, …),
and if the user names a specific agent, use that one.

`--command`'s value is **typed as literal keystrokes into the new
terminal's real interactive login shell** (whatever `$SHELL` resolves to
for the user — zsh, bash, etc.), followed by Enter — it is not tokenized
or exec'd by Casper itself. Because it's the user's actual login shell, it
already re-sources that shell's own profile (`~/.zshrc`, `~/.bash_profile`,
...) and rebuilds `PATH` on its own, exactly like a normal (commandless)
Casper terminal. That means a bare invocation of the agent CLI just
works — no need to re-export `$PATH` and no `/bin/sh -c` wrapping:

```bash
casper workspace new <name> --command <agent-cli>   # e.g. claude, codex, gemini
```

### Giving that instance a task to work on

To have the new instance start on a specific task right away (e.g. "run a
code review in a new workspace") rather than opening an empty agent
prompt, pass the task as the agent CLI's prompt argument. Quote it
normally, the way you'd type it at a shell prompt — no `printf '%q'`
gymnastics needed, since the whole `--command` value is a single
already-expanded CLI argument that gets retyped verbatim into the target
shell, which parses the quotes itself:

```bash
casper workspace new <name> --command \
  '<agent-cli> "Review the diff in this workspace for bugs."'   # e.g. claude "…"
```

`--command` is a one-shot instruction, not part of the persisted terminal
state — `casper terminal list` never reports a `"command"` field (for this
or any terminal), so don't use its absence to infer the launch failed.

### Offloading a topic to an isolated instance instead of doing it here

The strongest use of a new workspace is to hand a whole topic off to a
separate agent instance in its own worktree, keeping the current session
free. Two ways it starts:

- **The user asks** — "traite ça dans un worktree séparé", "lance une
  instance dédiée", "handle X in isolation". Primary path: create the
  workspace and launch the instance with the task, as above.
- **You may propose it** — on your own judgment, when the topic fits the
  criteria below. Proposing is not launching: you may *suggest* offloading,
  but you may **not** create the workspace or start the instance until the
  user says go.

Propose offloading when the topic is:
- **substantial and self-contained** — a distinct feature, fix, or
  investigation, not a quick inline edit;
- **long-running or parallel** — doing it here would block this session or
  interleave badly with what you're already working on;
- **disposable or experimental** — you want a throwaway sandbox worktree
  that can't touch the current one;
- **tangential** — chasing it here would derail this session's focus.

Do **not** propose it for trivial or inline work, or for work that depends
on this workspace's **uncommitted** state: `workspace new` branches from a
committed ref (`--base`), so your current dirty tree won't be in the new
worktree.

When you do offload, remember the launched instance starts with a **blank
context window** — it can't see this conversation. Make the agent's prompt
self-contained: name the files, the decisions already settled, and the
constraints it must respect.

Whatever the trigger, only *create the workspace or launch the instance*
once the user has explicitly agreed — never act on your own judgment
(propose, don't act). This mirrors the existing rule not to create a Git
branch without being asked: `workspace new` always creates one.

## Deleting a workspace: explicit request only, and irreversible

```bash
casper workspace delete [--workspace <id-or-name>]
```

deletes a workspace — its worktree folder, its Git branch, and its UI
entry — **immediately**. There is no confirmation prompt and no
`--force`/`-y` gate anywhere in the CLI; calling the command is the only
confirmation there is, and it cannot be undone.

This is a plain, unconditional delete: it does **not** merge or otherwise
preserve the branch's commits anywhere first — once the branch and
worktree are gone, that work is gone with them. Use this when the user
wants to discard the workspace's work entirely; use the "Closing
(merging)" procedure below when they want to keep it.

Only run this when the user explicitly asks. Because this discards the
workspace's work with no undo, **confirm with the `AskUserQuestion` tool
before calling `delete`** — don't settle for a free-text prompt and don't
proceed on implied agreement. Ask a single question whose `header` is
something like "Delete workspace" and whose body names the exact workspace
(id or name) about to be deleted and makes clear its branch and commits go
with it. Offer a "Delete" option first and a "Cancel" option; only run the
command if the user picks the confirming option (or answers "Other" with an
unambiguous go-ahead). This matters most when there's any ambiguity about
*which* workspace — the CLI itself won't stop a mistaken call. (It refuses
to delete a Space's primary workspace on its own: `"cannot delete the
primary workspace"`.)

## Closing (merging) a workspace: explicit request only, destructive, and irreversible

"Close this workspace" or "merge this workspace/worktree" means running
this exact five-step procedure — not just `casper workspace delete`. If
the user instead wants to throw the workspace's work away without merging
it anywhere, that's the plain delete described above, not this procedure —
confirm which one they mean if it's unclear.

1. Identify the origin branch (the branch this workspace's branch forked
   from — most often `main`).
2. Verify the current branch **and** the origin branch are both clean.
   Stop if either has uncommitted or untracked changes.
3. `git rebase` the current branch onto the origin branch.
4. Merge the current branch into the origin branch with an explicit merge
   commit.
5. Close (delete) the current workspace.

**Confirm the plan with the user before running any of steps 3-5** by
asking with the `AskUserQuestion` tool — don't settle for a free-text
prompt and don't proceed on implied agreement. Ask a single question whose
`header` is something like "Close workspace" and whose body states the
origin branch, both worktree paths, and which workspace will be deleted.
Offer a "Confirm" option first (so it reads as the recommended path) and a
"Cancel" option; only run steps 3-5 if the user picks the confirming
option (or answers "Other" with an unambiguous go-ahead). This applies even
if the request ("close this workspace") sounded unambiguous — the user
needs to see the plan and actively confirm before history gets rewritten
and a workspace gets deleted.

**If any step fails, stop the whole procedure immediately.** Don't attempt
the remaining steps, don't auto-resolve conflicts, and don't delete the
workspace unless Step 4's merge actually succeeded — a conflict that looks
trivial still means stop and let the user decide.

### Step 1: identify the origin branch

```bash
git worktree list
```

The first line is the Space's primary worktree — its branch is the origin
branch (usually `main`). Record its path as `<origin-path>` and its branch
as `<origin-branch>`.

### Step 2: verify both branches are clean

```bash
git -C <current-workspace-path> status --porcelain
git -C <origin-path> status --porcelain
```

Any output (staged, unstaged, or untracked) means that tree is dirty.
**Stop here and report which branch is dirty** — never rebase or merge a
dirty tree.

### Step 3: rebase

```bash
cd <current-workspace-path>
git rebase <origin-branch>
```

On conflict: **stop**, report the conflicting files, and leave the rebase
in progress for the user to resolve (or run `git rebase --abort` if they'd
rather cancel). Do not proceed to Step 4.

### Step 4: merge with a merge commit

```bash
cd <origin-path>
git merge --no-ff <current-branch>
```

`--no-ff` is required — a fast-forward merge would satisfy "merge" but not
"with a merge commit". On conflict: **stop**, report the conflicting files,
and leave the merge in progress for the user to resolve (or
`git merge --abort`). Do not proceed to Step 5.

### Step 5: close the workspace

```bash
casper workspace delete --workspace <current-workspace-id-or-name>
```

Run this from `<origin-path>` (or any workspace other than the one being
closed) — deleting removes that worktree folder out from under the shell's
CWD if run from inside it. Only run this after Step 4's merge succeeded.

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
