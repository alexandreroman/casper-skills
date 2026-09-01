# Casper status (blocked / error)

This plugin's hooks already keep a Casper workspace's sidebar state in sync
for every deterministic lifecycle transition (session start/end, prompt
submitted, response finished, task progress, notifications, and a turn killed
by an API error). Two states are still judgment calls:

- **`blocked`** — you are waiting on something external mid-turn (a
  long-running background command, a user action outside this conversation),
  not just idle-waiting for the next prompt. No hook fires for it at all.
- **`error`** — you hit an unrecoverable failure you want the user to notice
  in the sidebar or via a notification, distinct from simply finishing a turn
  normally. Half of this one is automatic now: a turn the API kills — rate
  limit, auth, billing, overload — reports `error` without you. What is left
  is every failure that looks from the outside exactly like a good run: a
  refusal, a wrong conclusion, a loop, a tool failure you could not work
  around. No event tells those apart, so they stay yours.

A tool call that fails is deliberately not one of the automatic ones. A grep
with no match, a red test under TDD, a deliberate `|| true` are all routine,
and because a turn ending never writes over an `error` (below), one of them
landing last in a turn would suppress the `done` you actually finished on. A
failure matters because you judged it did — so say so.

When you judge you're in one of these states, call the CLI yourself:

```bash
casper status set blocked
casper status set error
casper status get           # what the sidebar is showing right now
casper notify --message "..."
```

A state you set this way stands: the turn-end hook reads the sidebar back
before it reports anything, and never writes over a `blocked` or an `error`.
Both say something about the world outside the turn — you are waiting on
someone, or something failed — that the turn ending cannot see for itself, so
it is not allowed to overrule them. What does clear it is the next thing that
genuinely knows better: your next turn, or your next tool call, both of which
report `working` again.

So a `blocked` lasts until you act again, and no longer. From there the
progress bar decides what the end of that turn reports — a bar still up says
`working`, no bar says `done` (see `references/progress.md`) — so a hold that
outlasts a turn has to be re-stated, and a bar left standing over finished
work reads as `working` rather than the `blocked` you meant.

`casper notify` is an attention flag — keep its message to the one thing you
need. If the detail behind it is worth keeping in view (what failed, what you
tried, what's left), publish that in the workspace's info panel as well — see
`references/info.md`. Report it in the conversation too: the panel is
in-memory only and is lost if Casper restarts.
