---
name: casper
description: Use whenever the session runs inside a Casper terminal workspace — the CASPER_WORKSPACE_ID environment variable is set — and for any Casper surface the agent can drive from there: reporting a blocked or error state, notifying the user, the sidebar progress bar, the workspace info panel, extra terminals, the browser panel, the diff view, creating or closing workspaces, handing a session off to a fresh workspace, and a repository's .casper.json. Read it first in such a session, then load the reference file for the surface at hand.
allowed-tools: AskUserQuestion Read Write Edit Glob Grep Bash([ -n "$CASPER_WORKSPACE_ID" ]) Bash(casper *) Bash(git rev-parse *) Bash(git status --porcelain*) Bash(git -C * status --porcelain*) Bash(git worktree list) Bash(git branch*) Bash(git log *) Bash(git add *) Bash(git commit *) Bash(git rebase *) Bash(git merge *) Bash(mktemp *) Bash(mv *)
---

# Casper

Casper opens terminal workspaces, each one a Git worktree, and surrounds them
with surfaces an agent can drive from the command line: a sidebar state and
progress bar, an info panel, extra terminals, a browser panel, and a diff
view. The `casper` CLI is how you reach all of them.

## Guard rule

Every surface here needs a Casper terminal. Check before calling, and treat a
missing or failing CLI as a no-op:

```bash
[ -n "$CASPER_WORKSPACE_ID" ] || exit 0
```

If `casper` isn't found or a command fails, ignore it and carry on. Casper is
never allowed to interrupt, block, or fail the task at hand.

## Tell the user when you need them

This is the one behaviour that matters most, so it lives here rather than in a
reference file. When you need the user — a decision, a credential, an
interactive login, an approval, or an unrecoverable error — say so out loud
instead of waiting silently. Ending a turn to ask a question or present
options is a blocked state, not a finished one.

```bash
casper notify --message "<what you need from them>"
casper status set blocked   # when you're waiting on them mid-turn
```

## Where to go next

Read the reference file before running that surface's commands rather than
improvising the CLI from memory; each one carries the exact subcommands,
their flags, and the judgment calls around them.

| What you need | Reference |
|---|---|
| Report a blocked or error state no hook can infer | `references/status.md` |
| Keep the sidebar progress bar in sync with multi-step work | `references/progress.md` |
| Publish, replace, or clear the workspace's info panel | `references/info.md` |
| Open a URL, screenshot it, read its console, drive the page | `references/browser.md` |
| Open or close the diff view, in full or for one file | `references/diff.md` |
| Open, list, or close terminals in the workspace | `references/terminal.md` |
| List, create, delete, or close/merge workspaces | `references/workspace.md` |
| Hand this session off to a fresh workspace | `references/handoff.md` |
| Write or update a repository's `.casper.json` | `references/repo-config.md` |
