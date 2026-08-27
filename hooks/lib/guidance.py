"""The session guidance injected into an agent's context.

One source, three renderings: stdout for Claude Code and Codex, an
instructions file for opencode, and this constant for the tests. Kept free of
any specific agent or tool name so all three read naturally.

This text is the only component that both runs in every session and knows for
a fact that the session is in a Casper terminal, so it carries the whole
weight of getting the skill loaded. It names the skill file by path rather
than by name: "read the casper skill" asks the agent to resolve something,
and an agent that cannot (or does not bother to) is exactly the failure this
guidance exists to prevent. A path is one file read, with nothing to resolve.
"""
import os

TEXT = """\
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
and then it is not optional — it is how that work gets tracked here. A bar
you set by hand stays up until you clear it or the session ends, so move it
on as each step begins and clear it the moment the work is done — nothing
else knows that it is:

  casper progress set --total <n> --current <i> --label "<current step>"
  casper progress clear

Read the `casper` skill now, before your first `casper` command — load it as
a skill if your harness has skills, otherwise just read the file:

  {skill_path}

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
"""

# Where the skill lives inside this repository. `render` fills it in absolutely
# when the plugin root is known, which is the whole point of naming a path.
SKILL_PATH = "skills/casper/SKILL.md"


def render(root: str = "") -> str:
    """The guidance with the skill's path resolved.

    `str.replace`, not `str.format`: this runs inside a hook whose stdout is
    the session's only guidance, so a stray brace in the text above must not
    be able to raise and cost the session all of it.
    """
    path = os.path.join(root, SKILL_PATH) if root else SKILL_PATH
    return TEXT.replace("{skill_path}", path)
