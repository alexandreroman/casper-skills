---
name: casper
description: Read this at the start of any session where CASPER_WORKSPACE_ID is set — the session is running in a Casper terminal workspace — and before the first `casper` command, whatever it is for. Triggers include: close, merge, create, delete, or list a workspace or its Git worktree; hand this session off to a fresh workspace; tell the user you are blocked, or that you need a decision, a credential, a login, or an approval, and notify them; keep the sidebar progress bar in step with multi-step work; publish a plan, findings, or a summary in the workspace info panel; open an extra terminal; open a URL in the browser panel, screenshot it, click or type on the page, read its console; open or close the diff view; write a repository's .casper.json.
allowed-tools: AskUserQuestion Read Write Edit Glob Grep Bash([ -n "$CASPER_WORKSPACE_ID" ]) Bash(casper *) Bash(git rev-parse *) Bash(git status --porcelain*) Bash(git -C * status --porcelain*) Bash(git worktree list) Bash(git branch*) Bash(git log *) Bash(git add *) Bash(git commit *) Bash(git rebase *) Bash(git merge *) Bash(mktemp *) Bash(mv *)
user-invocable: false
---

# Casper

Casper opens terminal workspaces, each one a Git worktree, with surfaces the
`casper` CLI drives: a sidebar state and progress bar, an info panel, extra
terminals, a browser panel, and a diff view.

## Guard rule

Every surface here needs a Casper terminal. Check before calling, and treat a
missing or failing CLI as a no-op:

```bash
[ -n "$CASPER_WORKSPACE_ID" ] || exit 0
```

If `casper` isn't found or a command fails, ignore it and carry on. Casper is
never allowed to interrupt, block, or fail the task at hand.

## Codex socket access

`casper` reaches the app through a socket outside Codex's sandbox, which
`allowed-tools` cannot open: request `sandbox_permissions: require_escalated`,
and `prefix_rule: ["casper"]`, never broader. Run the guard on its own: with it
in front of the `casper` call, no rule matches and every call asks again.

## Tell the user when you need them

When you need the user — a decision, a credential, a login, an approval, or
an unrecoverable error — say so instead of waiting silently. Ending a turn to
ask a question or present options is a blocked state, not a finished one. A
notification cannot be answered: ask the question itself in the conversation,
and let the message say only what you need them for, never the question.

```bash
casper notify --message="<that you need them, and what for>"
casper status set blocked   # when you're waiting on them mid-turn
```

## Check workspaces before you report them

Workspaces get merged, deleted or finished behind your back. Before saying
which exist, are open, or what their instances are doing, check in that same
turn (`casper workspace list`; see `references/workspace.md`) and report only
what it shows. Anything else is history ("I launched X"), not state: a session
listed five instances "running in parallel" from memory, and three were gone.

## Progress tracking

Check your tool list first: a plan, todo, or task tool there *is* the
progress bar — the hook mirrors it to the sidebar without a permission prompt,
so a `casper progress` call of your own fights that mirror. Only a harness
without one drives the bar by hand: read `references/progress.md` first.

## Where to go next

`casper --help` is not a substitute for reading the reference first. It lists
subcommands and flags, and stops there: it cannot tell you that an operation
is a multi-step procedure with a stop rule, that another is irreversible, or
that what you reach for is a procedure rather than a subcommand, and a
rejected guess says only that the argument was unexpected. Every one of those
has already cost a session real work.

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
