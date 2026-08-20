---
name: casper-status
description: Report a Casper workspace's agent state (blocked or error) when you judge you're in one of those states — no automatic hook covers them.
allowed-tools: Bash([ -n "$CASPER_WORKSPACE_ID" ]) Bash(casper status set *) Bash(casper notify *)
---

# Casper status (blocked / error)

This plugin's hooks already keep a Casper workspace's sidebar state in sync
for every deterministic lifecycle transition (session start/end, prompt
submitted, response finished, task progress, notifications). Two states are
judgment calls only you can make, and no hook fires for them:

- **`blocked`** — you are waiting on something external mid-turn (a
  long-running background command, a user action outside this conversation),
  not just idle-waiting for the next prompt.
- **`error`** — you hit an unrecoverable failure you want the user to notice
  in the sidebar or via a notification, distinct from simply finishing a turn
  normally.

When you judge you're in one of these states, call the CLI yourself:

```bash
casper status set blocked
casper status set error
casper notify --message "..."
```

`casper notify` is an attention flag — keep its message to the one thing you
need. If the detail behind it is worth keeping in view (what failed, what you
tried, what's left), publish that in the workspace's info panel as well — see
the `casper-info` skill. Report it in the conversation too: the panel is
in-memory only and is lost if Casper restarts.

This only works inside a terminal Casper opened — if the command fails or
`casper` isn't found, ignore the failure and continue; never let it interrupt
your actual task.

## Guard rule

Only invoke this skill inside a Casper terminal workspace. The plugin sets the
`CASPER_WORKSPACE_ID` environment variable in each Casper terminal it opens —
check for its presence with the same plain test the plugin's own hooks use,
not by echoing the variable:

```bash
[ -n "$CASPER_WORKSPACE_ID" ]
```

Then call the CLI as its own command.
