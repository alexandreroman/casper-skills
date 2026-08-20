Casper is available in this workspace. When you need my intervention — a
decision, a credential, an interactive login, an approval, or an
unrecoverable error you want me to notice — be explicit and tell me instead
of silently waiting. This includes ending a turn to ask me a question or
present options: that is a blocked state, not a finished one, so notify me.
Use the Casper notification mechanism:

  casper notify --message "<what you need from me>"
  casper status set blocked   # when you're waiting on me mid-turn

If your work breaks into several distinct steps and isn't over in a single
action, track it with your todo or plan tool — this keeps the workspace's
sidebar progress bar in sync. See the casper-progress skill for when and how.

If `casper` isn't found or a command fails, ignore it and continue — never
let it interrupt your task.
