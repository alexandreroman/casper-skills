Casper is available in this workspace. When you need my intervention — a
decision, a credential, an interactive login, an approval, or an
unrecoverable error you want me to notice — be explicit and tell me instead
of silently waiting. This includes ending a turn to ask me a question or
present options: that is a blocked state, not a finished one, so notify me.
Both commands, together, are the notification — the flag tells me something
needs me, the state is what makes the sidebar say so:

  casper notify --message "<what you need from me>"
  casper status set blocked   # every time you end a turn waiting on me

If your work breaks into several distinct steps and isn't over in a single
action, track it with your task, plan, or todo tool — that tool is how the
workspace's sidebar progress bar gets filled in. Create every step up front
and keep exactly one in progress; the bar follows along on its own, so do not
run `casper progress` as well — a hand-written bar and a mirrored one
overwrite each other and the sidebar ends up showing neither.

Check your own tool list rather than assuming, in either direction. Only if
you genuinely have no such tool is driving the bar yourself the right move,
and then it is not optional — it is how that work gets tracked here:

  casper progress set --total <n> --current <i> --label "<current step>"
  casper progress clear

Whichever fills it, the bar is also how the workspace knows whether the work
is over. A bar still up when your turn ends says the work outlives the turn —
which is right when you left background work running, and it holds the
sidebar at "working" instead of announcing a finish that has not happened.
The other half of that is yours: clear the bar the moment the work is done,
or the workspace stays "working" until the session ends. Nothing else knows
that it is done.

Read the `casper` skill now, before your first `casper` command — load it as
a skill if your harness has skills, otherwise just read the file:

  skills/casper/SKILL.md

It is the entry point for every surface this workspace exposes — sidebar
state, progress bar, info panel, terminals, browser panel, diff view,
workspaces, session handoff, and a repo's .casper.json — and it routes to one
reference file per surface, so you load only what you need. It is short, and
reading it is a single action; skipping it has already cost a session an
unwanted merge and a false answer to me.

Do not reconstruct the CLI from `casper --help` instead. `--help` lists
subcommands and flags; it does not tell you that some operations are
multi-step procedures with stop rules, that some are irreversible, or that
the thing you are looking for isn't a subcommand at all. Reading the
reference for a surface is what tells you that, and it costs one file.

If `casper` isn't found or a command fails, ignore it and continue — never
let it interrupt your task.
