---
name: casper
description: Read this at the start of any session where CASPER_WORKSPACE_ID is set — the session is running in a Casper terminal workspace — and before the first `casper` command, whatever it is for. Triggers include: close, merge, create, delete, or list a workspace or its Git worktree; hand this session off to a fresh workspace; tell the user you are blocked, or that you need a decision, a credential, a login, or an approval, and notify them; keep the sidebar progress bar in step with multi-step work; publish a plan, findings, or a summary in the workspace info panel; open an extra terminal; open a URL in the browser panel, screenshot it, click or type on the page, read its console; open or close the diff view; write a repository's .casper.json.
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

## Codex socket access

Casper controls the current app through `$CASPER_CONTROL_SOCKET`, a Unix-domain
socket outside Codex's workspace sandbox. When calling `casper` from Codex,
request `sandbox_permissions: require_escalated`; `allowed-tools` authorizes
the command but does not grant that socket access. When requesting persistent
approval, use `prefix_rule: ["casper"]`; never broaden it beyond that command
prefix.

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

## Progress tracking

If the harness exposes a plan, todo, or task tool, update that tool and never
duplicate its updates with `casper progress`: the hook mirrors it to the
sidebar without an extra permission prompt. Only when no such tool exists do
you drive the bar yourself — read `references/progress.md` first.

## Where to go next

Read the reference file before running that surface's commands rather than
improvising the CLI from memory; each one carries the exact subcommands,
their flags, and the judgment calls around them.

`casper --help` is not a substitute. It lists subcommands and flags, and
stops there: it cannot tell you that an operation is a multi-step procedure
with a stop rule, that another is irreversible, or that the thing you are
reaching for is a procedure rather than a subcommand. When it rejects a
guess, it says only that the argument was unexpected — never what to do
instead. Every one of those has already cost a session real work.

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
