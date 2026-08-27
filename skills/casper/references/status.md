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

A state you set this way stands: the turn-end hook reads the sidebar back
before it reports anything, and never writes over a `blocked` or an `error`.
Both say something about the world outside the turn — you are waiting on
someone, or something failed — which no lifecycle event can infer, so a turn
ending is not allowed to overrule it. What does clear it is the next thing
that genuinely knows better: your next turn, or your next tool call, both of
which report `working` again.

`casper notify` is an attention flag — keep its message to the one thing you
need. If the detail behind it is worth keeping in view (what failed, what you
tried, what's left), publish that in the workspace's info panel as well — see
`references/info.md`. Report it in the conversation too: the panel is
in-memory only and is lost if Casper restarts.
