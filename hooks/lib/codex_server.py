"""Codex's shared background server, and whose session a hook is running for.

Codex 0.169 runs interactive sessions in one background app-server per
CODEX_HOME, and it is that server that runs the hooks and the agent's shell
commands. Both inherit the server's environment, so CASPER_WORKSPACE_ID names
the workspace of whichever terminal started it, not the one the session was
launched from: left alone, a session in workspace B reports to A's sidebar.

The session's own directory is what the hook can still trust: Codex runs every
hook in it. A session belongs to the workspace in CASPER_WORKSPACE_ID when that
directory lies inside the workspace's path, as `casper workspace list` reports
it. `codex --no-daemon` keeps the session in the terminal's own process and
environment, which is the real fix; this check only keeps a session that was
not launched that way from writing to someone else's sidebar.
"""
import os

WARNING = """\
Casper integration is off for this session. Codex is running it in its shared
background server, which was started from a Casper workspace this session's
directory is not part of, so `casper` — this session's hooks and your own
commands alike — would update that workspace's sidebar instead of this one.

Do not run `casper` in this session. Tell the user, once: to bring Casper's
sidebar to this session, quit Codex and start it again with
`codex --no-daemon` from this workspace's terminal.
"""


def _inside(path: str, root: str) -> bool:
    path, root = os.path.realpath(path), os.path.realpath(root)
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def belongs(workspaces, workspace_id: str, cwd: str):
    """Whether a session in `cwd` belongs to workspace `workspace_id`.

    True or False when `workspaces` (`casper workspace list`'s answer) settles
    it, None when it cannot: no answer, an unknown workspace, or a CLI too old
    to report paths. None lets the hook run, as it did before this check
    existed — a check that cannot be made must not switch the integration off.
    """
    if not isinstance(workspaces, list) or not workspace_id:
        return None
    for ws in workspaces:
        if not isinstance(ws, dict):
            continue
        if workspace_id not in (ws.get("workspace"), ws.get("name")):
            continue
        path = ws.get("path")
        if not isinstance(path, str) or not path:
            return None
        return _inside(cwd, path)
    return None
